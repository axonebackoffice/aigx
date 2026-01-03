# -*- coding: utf-8 -*-
from odoo import models, fields, _


class ImportInvoiceWizardHeader(models.TransientModel):
    _name = 'import.invoice.wizard.header'
    _description = 'Wizard Line for Importing Invoices'

    name = fields.Char(string='Name')
    invoice_wizard_line_ids = fields.Many2many('import.invoice.wizard.line', string="Lineas de facturas")

    def action_save(self):
        datas = []
        facturas = self.env['account.move']
        for line in self.invoice_wizard_line_ids.filtered(lambda x: x.error == False):
            fact_id = self.env['account.move'].sudo().create(line.data_create)
            #fact_id.action_post()
            if line.file_xml:
                attachment_id = self.env['ir.attachment'].sudo().create({
                    'type': 'binary',
                    'mimetype': 'text/plain',
                    'name': line.name_xml,
                    'datas': line.file_xml,
                    'res_model': fact_id._name,
                    'res_id': fact_id.id,
                    'company_id': fact_id.company_id.id,
                })
                edi_document_id = self.env['account.edi.document'].sudo().create({
                    'name': line.name_xml,
                    'state': 'sent',
                    'move_id': fact_id.id,
                    'attachment_id': attachment_id.id,
                    'edi_format_id': self.env['account.edi.format'].sudo().search([('name', 'ilike', '4.0')],
                                                                                  limit=1).id,
                })
            if line.file_pdf:
                attachment_id = self.env['ir.attachment'].sudo().create({
                    'type': 'binary',
                    'mimetype': 'application/pdf',
                    'name': line.name_pdf,
                    'datas': line.file_pdf,
                    'res_model': fact_id._name,
                    'res_id': fact_id.id,
                    'company_id': fact_id.company_id.id,
                })
            facturas |= fact_id

        return {
            'name': _('Facturas creadas'),
            'view_mode': 'list,form',
            'res_model': 'account.move',
            'search_view_id': [self.env.ref('account.view_account_move_filter').id, 'search'],
            'views': [(self.env.ref('account.view_move_tree').id, 'list'), (False, 'form')],
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', facturas.ids)],
            'context': dict(self._context, create=False),
        }
