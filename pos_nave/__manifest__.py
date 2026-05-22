# -*- coding: utf-8 -*-
{
    'name': 'Punto de Venta Nave',
    'version': '18.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Integración oficial con terminales físicas de Nave (Naranja X / Galicia) en Odoo POS.',
    'description': """
        Este módulo permite integrar las terminales físicas (Smart POS) de Nave con el Punto de Venta de Odoo 18.0.
        Soporta:
        - Cobros presenciales enviando la solicitud de pago directamente a la terminal.
        - Polling de estado para confirmación de pago en tiempo real.
        - Reembolsos / devoluciones en la terminal.
        - Soporte multi-compañía nativo.
    """,
    'author': 'Be onlyone',
    'website': 'https://onlyone.odoo.com',
    'license': 'LGPL-3',
    'depends': [
        'point_of_sale',
        'payment_nave',
    ],
    'data': [
        'views/pos_payment_method_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'pos_nave/static/src/app/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': True,
}
