# -*- coding: utf-8 -*-
{
    'name': 'Punto de Venta Nave',
    'version': '18.0.1.5.1',
    'category': 'Sales/Point of Sale',
    'summary': 'Cobros presenciales de Nave (Naranja X / Galicia) en el Punto de Venta de Odoo: terminal Nave Point y QR interoperable.',
    'description': """
        Este módulo integra los cobros presenciales de Nave con el Punto de Venta de Odoo 18.0.
        Soporta:
        - Terminal física Nave Point: la solicitud de cobro se envía directamente al equipo.
        - QR interoperable: el cliente paga escaneando el QR físico con cualquier billetera o app bancaria.
        - Polling de estado para confirmación de pago en tiempo real.
        - Datos del cobro en la línea de pago y en el ticket (marca, últimos dígitos, cupón, billetera).
        - Soporte multi-compañía nativo.

        Cada dispositivo (terminal o QR) tiene su propio pos_id en Nave, que se descarga desde
        Nave > Integraciones > Sistema de gestión y se carga en el método de pago del POS.
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
