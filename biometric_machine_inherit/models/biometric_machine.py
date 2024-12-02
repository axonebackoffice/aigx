# -*- coding: utf-8 -*-

import pytz
import datetime
from odoo.addons.hr_biometric_machine_zk.models.base import ZK

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo import models, fields, api, exceptions, SUPERUSER_ID, _
from odoo.exceptions import UserError
from itertools import groupby

import logging

_logger = logging.getLogger(__name__)


class zkMachineInherit(models.Model):
    _inherit = 'zk.machine'

    def download_attendance2(self):
        user = self.env.user
        if not user.partner_id.tz:
            raise exceptions.ValidationError("Timezone is not defined on this %s user." % user.name)
        for machine in self:
            machine_ip = machine.name
            port = machine.port
            zk = ZK(machine_ip, port=port, timeout=50, password=0, force_udp=False, ommit_ping=False)
            conn = ''
            try:
                conn = zk.connect()
                attendances = conn.get_attendance()
            except Exception as e:
                raise UserError('The connection has not been achieved: %s' % (e))
            finally:
                if conn:
                    conn.disconnect()
                    filtered_and_sorted = sorted(
                        (att for att in attendances if att.punch == 255),
                        key=lambda att: att.timestamp
                    )
                    _logger.info("ATTENDANCES %s", filtered_and_sorted)
                    self.get_pairs_attendances(attendances, machine)
                    raise UserError(_('Successful connection:  "%s".') %
                                    (attendances))

    def check_attendances_exist(self, field, employee_id, attendance):
        user = self.env.user
        tz = pytz.timezone(user.partner_id.tz) or False

        attendance_obj = self.env["hr.attendance"]
        employee_location_line_obj = self.env["zk.employee.location.line"]

        date = attendance.timestamp
        date1 = datetime.datetime.strptime(str(date), DEFAULT_SERVER_DATETIME_FORMAT)
        date = tz.normalize(tz.localize(date1)).astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M:%S")
        return attendance_obj.search([
            ('employee_id', '=', employee_id.id),
            (field, '=', str(date))
        ])

    def get_pairs_attendances(self, attendances, machine):
        user = self.env.user
        tz = pytz.timezone(user.partner_id.tz) or False
        tiempo_minimo_minutos = 2
        attendance_obj = self.env["hr.attendance"]
        employee_location_line_obj = self.env["zk.employee.location.line"]
        # Primero, ordenar por `user_id` y `timestamp` para preparar el agrupamiento
        filtered_and_sorted = sorted(
            (att for att in attendances if att.punch == 255),
            key=lambda att: att.timestamp
        )

        # Agrupar por `user_id`
        grouped_attendances = {user_id: list(group) for user_id, group in
                               groupby(filtered_and_sorted, key=lambda x: x.user_id)}

        # Crear tuplas de 2 objetos por grupo de `user_id`
        grouped_pairs = {}
        for user_id, group in grouped_attendances.items():
            pairs = []
            i = 0
            while i <= len(group) - 1:
                current = group[i]
                next_item = group[i + 1] if i + 1 <= (len(group) - 1) else False
                # Calculamos la diferencia en minutos
                if next_item:
                    diff_minutes = (next_item.timestamp - current.timestamp).total_seconds() / 60
                    if diff_minutes >= tiempo_minimo_minutos:
                        pairs.append((current, next_item))
                        i += 2  # Saltamos al siguiente par
                    else:
                        i += 1  # Ignoramos el siguiente y avanzamos solo uno
                else:
                    pairs.append((current, next_item))
                    i += 1
            grouped_pairs[user_id] = pairs

        # Mostrar resultados
        for user_id, pairs in grouped_pairs.items():
            _logger.info(f"User ID: {user_id}")
            employee_location_line = employee_location_line_obj.search([
                ("zk_num", "=", int(user_id)),
                ('location_id', '=', machine.location_id.id),
                ('machine_id', '=', machine.id)
            ])
            if employee_location_line:
                employee_id = employee_location_line.employee_id
                for pair in pairs:
                    attendace_1 = pair[0]
                    attendace_2 = pair[1]
                    attendance_in_id = self.check_attendances_exist('check_in', employee_id, attendace_1)
                    #_logger.info("ATTENDANCE EXISTS %s", attendance_in_id)
                    if attendance_in_id:
                        if attendace_2:
                            date2 = datetime.datetime.strptime(str(attendace_2.timestamp),
                                                               DEFAULT_SERVER_DATETIME_FORMAT)
                            date2 = tz.normalize(tz.localize(date2)).astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M:%S")
                            attendance_in_id.check_out = date2
                    else:
                        date1 = datetime.datetime.strptime(str(attendace_1.timestamp), DEFAULT_SERVER_DATETIME_FORMAT)
                        date1 = tz.normalize(tz.localize(date1)).astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M:%S")
                        data_create = {
                            'check_in': date1,
                            'employee_id': employee_id.id}

                        if attendace_2:
                            date2 = datetime.datetime.strptime(str(attendace_2.timestamp),
                                                               DEFAULT_SERVER_DATETIME_FORMAT)
                            date2 = tz.normalize(tz.localize(date2)).astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M:%S")
                            data_create['check_out'] = date2
                        _logger.info("ATTENDANCE create %s", data_create)
                        attendance_obj.create(data_create)

    def download_attendance(self):
        users = self.env['res.users']
        attendance_obj = self.env["hr.attendance"]
        employee_location_line_obj = self.env["zk.employee.location.line"]
        user = self.env.user
        if not user.partner_id.tz:
            raise exceptions.ValidationError("Timezone is not defined on this %s user." % user.name)
        tz = pytz.timezone(user.partner_id.tz) or False
        for machine in self:
            machine_ip = machine.name
            port = machine.port
            zk = ZK(machine_ip, port=port, timeout=10, password=0, force_udp=False, ommit_ping=False)
            conn = ''

            conn = zk.connect()
            conn.disable_device()
            attendances = conn.get_attendance()
            # Primero, ordenar por `user_id` y `timestamp` para preparar el agrupamiento
            filtered_and_sorted = self.get_pairs_attendances(attendances, machine)

            for attendance in attendances:
                employee_location_line = employee_location_line_obj.search([
                    ("zk_num", "=", int(attendance.user_id)),
                    ('location_id', '=', machine.location_id.id),
                    ('machine_id', '=', machine.id)
                ])
                if employee_location_line:
                    _logger.info("Attendances %s", attendances)
                    employee_id = employee_location_line.employee_id
                    date = attendance.timestamp
                    date1 = datetime.datetime.strptime(str(date), DEFAULT_SERVER_DATETIME_FORMAT)
                    date = tz.normalize(tz.localize(date1)).astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M:%S")
                    if attendance.punch == 0:
                        attendance_id = attendance_obj.search([
                            ('employee_id', '=', employee_id.id),
                            ('check_in', '=', str(date))
                        ])
                        if not attendance_id:
                            attendance_obj.create({'check_in': date, 'employee_id': employee_id.id})
                    if attendance.punch == 1:
                        attendance_id = attendance_obj.search([
                            ('employee_id', '=', employee_id.id),
                            ('check_out', '=', str(date))
                        ])
                        if not attendance_id:
                            attendance_ids = attendance_obj.search([
                                ('employee_id', '=', employee_id.id),
                                ('check_in', '<', str(date)),
                                ('check_out', '=', False)
                            ], order='check_in desc', limit=1)
                            attendance_last = attendance_obj.search([
                                ('employee_id', '=', employee_id.id),
                                ('check_in', '!=', False)
                            ], order='check_in desc', limit=1)
                            if (attendance_last.check_in and attendance_ids.check_in and
                                attendance_ids.check_in >= attendance_last.check_in) or \
                                    not attendance_last.check_in or not attendance_ids.check_in:
                                if attendance_ids:
                                    attendance_ids.write({'check_out': date})
                                else:
                                    attendance_obj.create({'check_out': date, 'employee_id': employee_id.id})
                            else:
                                attendance_obj.create({'check_out': date, 'employee_id': employee_id.id})


        if conn:
            conn.enable_device()
            conn.disconnect()
