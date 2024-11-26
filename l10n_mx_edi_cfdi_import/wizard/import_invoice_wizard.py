# -*- coding: utf-8 -*-
from pickletools import floatnl

from odoo import models, fields, api, _
import zipfile
import base64
from lxml import etree
import io
from odoo.osv import expression


from odoo.exceptions import ValidationError


class ImportInvoiceWizard(models.TransientModel):
    _name = 'import.invoice.wizard'
    _description = 'Importar Facturas desde XML o ZIP'

    type = fields.Selection([
        ('customer', 'Factura de Cliente'),
        ('supplier', 'Factura de Proveedor')
    ], string="Tipo", required=True)

    @api.onchange('type')
    def onchange_type(self):
        for rec in self:
            rec.journal_id = False
            rec.line_account_id = False

    payment_reference = fields.Char(string="Referencia de Pago", required=True)
    journal_id = fields.Many2one('account.journal', string="Diario", domain="[('id','in',journal_permitted_ids)]",required=True)
    journal_permitted_ids = fields.Many2many('account.journal', string="Permitidos", compute="_compute_journal_permitted_ids")

    @api.depends('journal_permitted_ids','type','company_id')
    def _compute_journal_permitted_ids(self):
        type = "sale" if self.type == 'customer' else "purchase"
        journals = self.env['account.journal'].sudo().search([('company_id','=',self.company_id.id),('type','=',type)])
        self.write({
            'journal_permitted_ids': [(6,0,journals.ids)]
        })

    line_account_id = fields.Many2one('account.account', string="Cuenta de Líneas", required=True)
    file = fields.Binary(string="Archivo ZIP/XML", required=True)
    file_name = fields.Char(string="Nombre del Archivo")
    create_missing_customers = fields.Boolean(string="Crear Clientes No Encontrados")
    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True, index=True,
                                 default=lambda self: self.env.company,
                                 help="Company related to this journal")
    payment_terms = fields.Selection([
        ('immediate', 'Pago Inmediato'),
        ('credit', 'A Crédito')
    ], string="Condiciones de Pago")

    def confirm_action(self):
        """Procesar el archivo y extraer datos"""
        if not self.file or not self.file_name:
            raise ValueError("Debe cargar un archivo.")

        file_data = base64.b64decode(self.file)
        tipo_impuesto = 'sale' if self.type == 'customer' else 'purchase'
        move_type = 'out_invoice' if self.type == 'customer' else 'in_invoice'
        impuesto_ids = self.env['account.tax'].search([('type_tax_use', '=', tipo_impuesto)])
        invoice_uuid_ids = self.env['account.move'].search([('move_type', '=', move_type),('state','!=','cancel')]).mapped('l10n_mx_edi_cfdi_uuid')
        data_lines = []
        if self.file_name.endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(file_data), 'r') as zf:
                for filename in zf.namelist():
                    if filename.endswith('.xml'):
                        data = {}
                        try:
                            self._fill_data_registers_inv(zf.read(filename), data)
                            if 'uuid' in data and data['uuid'] in invoice_uuid_ids:
                                raise ValidationError(_("Ya existe una factura con este folio fiscal"))
                            if '4AD4D6E1-893C-4644-B658-E9DE22059DC1' in filename:
                                pass
                            data_create = self._process_xml(zf.read(filename),impuesto_ids)
                            data['data_create'] = data_create
                            data['file_xml'] = base64.b64encode(zf.read(filename)).decode('utf-8')
                            data['name_xml'] = filename
                            pdf_file = filename[:-4] + '.pdf'
                            if pdf_file in zf.namelist():
                                data['file_pdf'] = base64.b64encode(zf.read(pdf_file)).decode('utf-8')
                                data['name_pdf'] = pdf_file

                        except ValidationError as e:
                            data['error'] = e.args[0]
                        data_lines.append((0,0,data))

        elif self.file_name.endswith('.xml'):
            self._process_xml(file_data, impuesto_ids)
            data = {}
            try:
                self._fill_data_registers_inv(file_data,data)
                if 'uuid' in data and data['uuid'] in invoice_uuid_ids:
                    raise ValidationError(_("Ya existe una factura con este folio fiscal"))
                data_create = self._process_xml(file_data, impuesto_ids)
                data['data_create'] = data_create
                data['file_xml'] = base64.b64encode(file_data).decode('utf-8')
                data['name_xml'] = self.file_name
            except ValidationError as e:
                data['error'] = e.args[0]
            data_lines.append((0, 0, data))
        else:
            raise ValueError("Formato de archivo no soportado.")

        wizard_view = self.env['import.invoice.wizard.header'].sudo().create({
            'name':"WIZARD",
            "invoice_wizard_line_ids": data_lines,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Facturas a importar',
            'res_model': 'import.invoice.wizard.header',
            'view_mode': 'form',
            'target': 'new',
            'res_id': wizard_view.id,
        }

    def _fill_data_registers_inv(self,xml_content,data):
        """Extraer información de un archivo XML"""

        def get_node(node, xpath):
            nodes = node.xpath(xpath)
            return nodes[0] if nodes else None

        def get_value(node, key):
            if node is None:
                return None
            upper_key = key[0].upper() + key[1:]
            lower_key = key[0].lower() + key[1:]
            return node.get(upper_key) or node.get(lower_key)

        try:
            cfdi_node = etree.fromstring(xml_content)
            comp_node = get_node(cfdi_node, "//*[local-name()='Comprobante']")
            emisor_node = get_node(comp_node, "//*[local-name()='Emisor']")
            receptor_node = get_node(comp_node, "//*[local-name()='Receptor']")

            conceptos_node = get_node(comp_node, "//*[local-name()='Conceptos']")
            timbre_fiscal = get_node(comp_node, "//*[local-name()='TimbreFiscalDigital']")
            partner_nodo = receptor_node
        except etree.XMLSyntaxError:
            # Not an xml
            return {}
        except AttributeError:
            # Not a CFDI
            return {}
        data.update({
            'serie':get_value(comp_node, "Serie"),
            'folio':get_value(comp_node, "Folio"),
            'rfc_emisor':get_value(emisor_node, "Rfc"),
            'rfc_receptor':get_value(receptor_node, "Rfc"),
            'uuid':get_value(timbre_fiscal, "UUID"),
            'total':get_value(comp_node, "Total"),
        })

    def _process_line_xml(self,line_concepto,impuesto_ids):
        def get_node(node, xpath):
            nodes = node.xpath(xpath)
            return nodes[0] if nodes else None

        def get_value(node, key):
            if node is None:
                return None
            upper_key = key[0].upper() + key[1:]
            lower_key = key[0].lower() + key[1:]
            return node.get(upper_key) or node.get(lower_key)

        unspsc_code = get_value(line_concepto, "ClaveProdServ")
        clave_unidad = get_value(line_concepto, "ClaveUnidad")
        cantidad = get_value(line_concepto, "Cantidad")
        unidad = get_value(line_concepto, "Unidad")
        default_code = get_value(line_concepto, "NoIdentificacion")
        name = get_value(line_concepto, "Descripcion")
        precio_unit_w_discount = float(get_value(line_concepto, "ValorUnitario"))
        price_unit = precio_unit_w_discount
        importe_total = get_value(line_concepto, "Importe")
        descuento = get_value(line_concepto, "Descuento")
        desc_porcentage = 0
        if descuento:
            descuento = float(descuento)
            price_unit = precio_unit_w_discount - descuento
            desc_porcentage = (descuento / precio_unit_w_discount) * 100 if precio_unit_w_discount != 0 else 0

        domain = []
        if default_code:
            domain = expression.OR(
                [domain, ['|',('default_code', '=', default_code),('barcode', '=', default_code)]])

        if name:
            domain = expression.OR(
                [domain, [('name', '=', name)]])
        product_id = self.env['product.product'].sudo().search(domain, limit=1)
        # unidad = self.env['uom.uom'].sudo().search([('name', 'ilike', unidad)],limit=1)
        impuestos_line = self.env['account.tax']
        if not product_id:
            if self.env.company.cfdi_import_create_products:
                product_id = self.env['product.product'].sudo().create({
                    'detailed_type':self.env.company.cfdi_import_detailed_type,
                    'categ_id':self.env.company.cfdi_import_categ_id.id or False,
                    'default_code': default_code,
                    'name': name,
                })
            else:
                raise ValidationError(_(f"No se encontro el producto con referencia {default_code}"))
        namespaces = {'cfdi': 'http://www.sat.gob.mx/cfd/4'}
        traslados_nodo = line_concepto.findall(".//cfdi:Traslado",namespaces)
        for traslado in traslados_nodo:
            tasa = float(get_value(traslado, "TasaOCuota") or 0) * 100
            impuesto = impuesto_ids.filtered_domain([('amount', '=', float(tasa))])
            if not impuesto:
                raise ValidationError(_(f"No se encontro el impuesto {tasa}"))
            impuestos_line |= impuesto[0]

        retenciones_nodo = line_concepto.findall(".//cfdi:Retencion",namespaces)

        for retencion in retenciones_nodo:
            tasa = float(get_value(retencion, "TasaOCuota")) * 100
            impuesto = impuesto_ids.filtered_domain([('amount', '=', -float(tasa))])
            if not impuesto:
                raise ValidationError(_(f"No se encontro la retencion {tasa}"))
            impuestos_line |= impuesto[0]

        return (0, 0, {
            'name': name,
            'product_id': product_id.id,
            'account_id': self.line_account_id.id,
            'quantity': cantidad,
            'price_unit': price_unit,
            'discount': desc_porcentage,
            'tax_ids': [(6, 0, impuestos_line.ids)]
        })

    def _process_xml(self, xml_content, impuesto_ids):
        """Extraer información de un archivo XML"""

        def get_node(node, xpath):
            nodes = node.xpath(xpath)
            return nodes[0] if nodes else None

        def get_value(node, key):
            if node is None:
                return None
            upper_key = key[0].upper() + key[1:]
            lower_key = key[0].lower() + key[1:]
            return node.get(upper_key) or node.get(lower_key)

        try:
            cfdi_node = etree.fromstring(xml_content)
            comp_node = get_node(cfdi_node, "//*[local-name()='Comprobante']")

            emisor_node = get_node(comp_node, "//*[local-name()='Emisor']")
            receptor_node = get_node(comp_node, "//*[local-name()='Receptor']")

            conceptos_node = get_node(comp_node, "//*[local-name()='Conceptos']")
            timbre_fiscal = get_node(comp_node, "//*[local-name()='TimbreFiscalDigital']")
            partner_nodo = receptor_node if self.type =='customer' else emisor_node
        except etree.XMLSyntaxError:
            # Not an xml
            return {}
        except AttributeError:
            # Not a CFDI
            return {}


        if "pago20" in cfdi_node.nsmap.keys():
            raise ValidationError(_(f"Es un XML de un Pago "))

        rfc_company = self.env.company.partner_id.vat
        name_company = self.env.company.partner_id.name



        # Procesar las líneas de la factura (ejemplo)
        line_items = []
        for line_concepto in conceptos_node.xpath('//*[local-name()="Concepto"]'):
            line_items.append(self._process_line_xml(line_concepto, impuesto_ids))

        rfc_partner = get_value(partner_nodo, "Rfc")
        nombre_partner = get_value(partner_nodo, "Nombre")

        if rfc_company == rfc_partner:
            type = "Proveedor" if self.type == 'supplier' else "Cliente"
            type_inverse = "Cliente" if self.type == 'supplier' else "Proveedor"
            raise ValidationError(_(f"Es un xml de {type_inverse}"))
        regimen_fiscal = get_value(partner_nodo, "RegimenFiscalReceptor")
        dom_fiscal = get_value(partner_nodo, "DomicilioFiscalReceptor")
        uso_cfdi = get_value(partner_nodo, "UsoCFDI")

        partner_id = self.env['res.partner'].sudo().search(['|', ('vat', '=', rfc_partner), ('name', '=', nombre_partner)],
                                                           limit=1)
        if not partner_id:

            if self.create_missing_customers:
                try:
                    partner_id = self.env['res.partner'].sudo().create({
                        'name':nombre_partner,
                        'vat':rfc_partner,
                        'zip':dom_fiscal,
                        'l10n_mx_edi_fiscal_regime':regimen_fiscal or False,
                    })
                except ValidationError as e:
                    partner_id = self.env['res.partner'].sudo().search(
                        ['|', ('vat', '=', rfc_partner), ('name', '=', nombre_partner)],
                        limit=1)
                    if not partner_id:
                        raise ValidationError(_(f"{e.args[0]}"))
            else:
                raise ValidationError(_(f"No se encontro el partner con RFC {rfc_partner} o nombre {nombre_partner}"))
        moneda =get_value(comp_node,"Moneda")
        currency_id = self.env['res.currency'].sudo().search([('name','=',moneda)])
        if not currency_id:
            raise ValidationError(_(f"No se encontro la moneda {moneda}"))
        metodopago = get_value(comp_node,"MetodoPago")

        if metodopago =='PUE':
            invoice_payment_term_id = self.env['account.payment.term'].sudo().search([('name','in',['Immediate Payment','Pago inmediato'])],limit=1)
            if not invoice_payment_term_id:
                raise ValidationError(_(f"No se encontro el metodo de pago inmediato"))
        elif metodopago =="PPD":
            condiciones_pago = get_value(comp_node, "CondicionesDePago")
            if condiciones_pago:
                invoice_payment_term_id = self.env['account.payment.term'].sudo().search(
                    [('name', 'ilike', condiciones_pago)], limit=1)
                if not invoice_payment_term_id:
                    raise ValidationError(_(f"No se encontro el metodo de pago {condiciones_pago}"))
            else:
                raise ValidationError(_(f"No se encontro el metodo de pago {condiciones_pago}"))

        if not currency_id:
            raise ValidationError(_(f"No se encontro la moneda {moneda}"))

        forma_pago = get_value(comp_node, "FormaPago")
        if not forma_pago:
            raise ValidationError(_(f"No se encontro el forma de pago {forma_pago}"))

        l10n_mx_edi_payment_method_id = self.env["l10n_mx_edi.payment.method"].sudo().search([('code','=',forma_pago)],limit=1)
        if not l10n_mx_edi_payment_method_id:
            raise ValidationError(_(f"No se encontro la forma de pago {forma_pago}"))
        uuid = get_value(timbre_fiscal, "UUID")
        data_factura = {
            'ref':str(get_value(comp_node,"Serie") or '')+str(get_value(comp_node,"Folio") or ''),
            'move_type':'out_invoice' if self.type =='customer' else 'in_invoice',
            'partner_id':partner_id.id,
            'invoice_date':get_value(comp_node,"Fecha"),
            'l10n_mx_edi_usage':uso_cfdi or False,
            'date':get_value(comp_node,"Fecha"),
            'currency_id':currency_id.id,
            'journal_id':self.journal_id.id,
            'invoice_payment_term_id':invoice_payment_term_id.id,
            'invoice_line_ids':line_items,
            'company_id':self.company_id.id,
            'payment_reference':self.payment_reference

            ## folio fiscal
        }

        return data_factura

