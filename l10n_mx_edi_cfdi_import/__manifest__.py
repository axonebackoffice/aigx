# -*- coding: utf-8 -*-

{
    'name': 'Importacion CFDI facturas MX',
    'version': '19.0.0.1',
    'category': 'account',
    'author': 'Ing. Alejandro Garcia Magaña',
    'website': '',
    'license': 'LGPL-3',
    'summary': 'Importacion CFDI facturas MX',

    'depends': [
        'account',
        'accountant',
        'account_accountant',
        'l10n_mx_edi',
    ],
    'data': [
        'security/import_invoice_security.xml',
        'security/ir.model.access.csv',
        'views/res_config_views.xml',
        'wizard/import_invoice_wizard_views.xml',
        'wizard/import_invoice_wizard_header_views.xml',
    ],
    'demo': [],
    'external_dependencies': {
    },
    'assets': {
    },
    'support': '',
    'application': False,
    'installable': True,
    'auto_install': False,
}
