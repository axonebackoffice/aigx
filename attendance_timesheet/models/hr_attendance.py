
from odoo import models, fields,_
from odoo.exceptions import UserError, ValidationError, AccessError, RedirectWarning
import pytz

class AccountAnaliticLineInherit(models.Model):
    _inherit = 'account.analytic.line'

    attendance_id = fields.Many2one('hr.attendance',string="Asistencia")


class HrAttendanceInherit(models.Model):
    _inherit = 'hr.attendance'

    x_studio_many2one_field_4mc3P = fields.Many2one('project.project',string="Proyecto")
    x_studio_many2one_field_mqKkU = fields.Many2one('project.task',string="Tarea")

    def action_add_timesheet(self):
        def get_date_attendance(rec):
            if rec.check_in:
                return rec.check_in.astimezone(pytz.timezone('America/Mexico_City')).replace(hour=0, minute=5).astimezone(pytz.utc).strftime('%Y-%m-%d')
            elif rec.check_out:
                return rec.check_out.astimezone(pytz.timezone('America/Mexico_City')).replace(hour=0, minute=5).astimezone(pytz.utc).strftime('%Y-%m-%d')
            raise ValidationError(_("Advertencia la asistencia no tiene configurara la entrada ni la salida, debe tener almenos 1"))

        for rec in self:
            tarea_id = rec.x_studio_many2one_field_mqKkU

            if not rec.x_studio_many2one_field_mqKkU:
                raise ValidationError(_(f"El resgistro seleccionado no tiene una tarea asignada"))

            if not rec.x_studio_many2one_field_4mc3P:
                raise ValidationError(_(f"El resgistro seleccionado no tiene un proyecto asignado"))

            if not rec.employee_id:
                raise ValidationError(_(f"El registro seleccionado no tiene un empleado"))

            timesheet_data = {
                'date': get_date_attendance(rec),
                'x_studio_turno': "Turno 1",
                'employee_id': rec.employee_id.id,
                'name': rec.x_studio_many2one_field_4mc3P.name,
                'unit_amount': rec.worked_hours,
                'company_id':tarea_id.company_id.id if tarea_id and tarea_id.company_id else False,
                'attendance_id':rec.id
            }

            timesheet_id = tarea_id.timesheet_ids.filtered(lambda x: x.attendance_id and x.attendance_id.id ==  rec.id)
            if timesheet_id:
                timesheet_id.write(timesheet_data)
            else:
                tarea_id.write({
                    'timesheet_ids': [(0,0, timesheet_data)]
                })

