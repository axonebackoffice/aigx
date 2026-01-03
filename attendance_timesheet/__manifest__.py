# -*- coding: utf-8 -*-

{
    'name': 'Hojas de horas en asistencias',
    'version': '19.0.0.1',
    'category': 'stock',
    'author': 'Ing. Alejandro Garcia Magaña',
    'website': '',
    'license': 'LGPL-3',
    'summary': 'Hojas de horas en asistencias',

    'depends': [
        'hr_attendance',
        'hr_timesheet',
        'project',
        'website_studio',
    ],
    'data': [
        'security/hr_attendance_security.xml',
        'views/hr_attendance_views.xml',
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
