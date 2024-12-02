# -*- coding: utf-8 -*-
from odoo import models, fields

class ImportInvoiceWizardLine(models.TransientModel):
    _name = 'import.invoice.wizard.line'
    _description = 'Wizard Line for Importing Invoices'

    serie = fields.Char(string="Serie")
    folio = fields.Char(string="Folio")
    rfc_emisor = fields.Char(string="RFC Emisor")
    rfc_receptor = fields.Char(string="RFC Receptor")
    uuid = fields.Char(string="UUID")
    total = fields.Float(string="Total")
    data_create = fields.Json(string="Data Create account.move")
    error = fields.Char(string="Error")

    file_xml = fields.Binary(string="Archivo XML", required=True)
    name_xml = fields.Char(string="Nombre del Archivo XML")

    file_pdf = fields.Binary(string="Archivo PDF", required=True)
    name_pdf = fields.Char(string="Nombre del Archivo PDF")