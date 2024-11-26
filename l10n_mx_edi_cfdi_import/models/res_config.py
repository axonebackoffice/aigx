import logging
import decimal
from collections import defaultdict

from odoo import _, api, Command, fields, models
from lxml import etree
import logging
_logger = logging.getLogger(__name__)

class CompanySettingsInherit(models.Model):
    _inherit = 'res.company'

    cfdi_import_create_products = fields.Boolean("Crear productos")
    cfdi_import_detailed_type = fields.Selection([
        ('product', 'Producto almacenable'),('consu', 'Consumible'),
        ('service', 'Servicio')
    ],"Tipo de producto")
    cfdi_import_categ_id = fields.Many2one("product.category", string="Categoria de producto")



class ResConfigSettingsInherit(models.TransientModel):
    _inherit = 'res.config.settings'


    cfdi_import_create_products = fields.Boolean("Crear productos", related='company_id.cfdi_import_create_products',
                                  readonly=False)

    cfdi_import_detailed_type = fields.Selection([
        ('product', 'Producto almacenable'), ('consu', 'Consumible'),
        ('service', 'Servicio')
    ], related='company_id.cfdi_import_detailed_type',readonly=False)

    cfdi_import_categ_id = fields.Many2one("product.category", string="Categoria de producto", related='company_id.cfdi_import_categ_id',
                                  readonly=False)
