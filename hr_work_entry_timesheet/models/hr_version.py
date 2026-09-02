import pytz

from odoo import fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    work_entry_source = fields.Selection(
        selection_add=[('timesheet', 'Hoja de horas')],
        ondelete={'timesheet': 'set default'},
    )

    def generate_work_entries(self, date_start, date_stop, force=False):
        timesheet_versions = self.filtered(lambda version: version.work_entry_source == 'timesheet')
        other_versions = self - timesheet_versions
        work_entries = super(HrVersion, other_versions).generate_work_entries(date_start, date_stop, force=force) if other_versions else self.env['hr.work.entry']
        if timesheet_versions:
            work_entries |= super(HrVersion, timesheet_versions).generate_work_entries(date_start, date_stop, force=True)
        return work_entries

    def _get_work_entries_values(self, date_start, date_stop):
        timesheet_versions = self.filtered(lambda version: version.work_entry_source == 'timesheet')
        other_versions = self - timesheet_versions
        vals_list = super(HrVersion, other_versions)._get_work_entries_values(date_start, date_stop) if other_versions else []
        for version in timesheet_versions:
            vals_list.extend(version._get_timesheet_work_entries_values(date_start, date_stop))
        return vals_list

    def _get_timesheet_work_entries_values(self, date_start, date_stop):
        self.ensure_one()
        date_from, date_to = self._get_timesheet_work_entry_date_range(date_start, date_stop)
        timesheet_groups = self.env['account.analytic.line'].sudo()._read_group(
            domain=[
                ('employee_id', '=', self.employee_id.id),
                ('date', '>=', date_from),
                ('date', '<=', date_to),
                ('unit_amount', '>', 0),
                '|',
                ('company_id', '=', False),
                ('company_id', '=', self.company_id.id),
            ],
            groupby=['date:day'],
            aggregates=['unit_amount:sum'],
        )
        work_entry_type = self.env.ref('hr_work_entry.work_entry_type_attendance')
        return [{
            'name': "%s: %s" % (work_entry_type.name, self.employee_id.name),
            'date': timesheet_date,
            'duration': duration,
            'work_entry_type_id': work_entry_type.id,
            'employee_id': self.employee_id.id,
            'version_id': self.id,
            'company_id': self.company_id.id,
        } for timesheet_date, duration in timesheet_groups]

    def _get_timesheet_work_entry_date_range(self, date_start, date_stop):
        self.ensure_one()
        tz = pytz.timezone(self._get_tz() or 'UTC')
        date_start = fields.Datetime.to_datetime(date_start)
        date_stop = fields.Datetime.to_datetime(date_stop)
        start = pytz.UTC.localize(date_start) if not date_start.tzinfo else date_start
        stop = pytz.UTC.localize(date_stop) if not date_stop.tzinfo else date_stop
        return start.astimezone(tz).date(), stop.astimezone(tz).date()
