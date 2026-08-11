# -*- coding: utf-8 -*-
{
    'name': 'Proveedor de Pago Nave',
    'version': '18.0.1.4.2',
    'category': 'Accounting/Payment Providers',
    'summary': 'Integración oficial con Nave para cobros online en e-commerce y links de pago.',
    'description': """
        Este módulo permite integrar Nave (Galicia/Naranja X) como proveedor de pagos en Odoo 18.0.
        Soporta:
        - Pasarela de Checkout de Nave (Redirección).
        - Generación manual de Links de Pago desde facturas o presupuestos.
        - Webhooks automáticos (S2S) para confirmación y conciliación asíncrona de transacciones.
        - Sistema de caché para optimizar la vigencia del Access Token de Auth0.
        - Soporte multi-compañía nativo.
    """,
    'author': 'Be onlyone',
    'website': 'https://onlyone.odoo.com',
    'license': 'LGPL-3',
    'depends': [
        'payment',
        'account',
        'sale',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/payment_provider_views.xml',
        'views/nave_link_wizard_views.xml',
        'data/payment_method_data.xml',
        'data/payment_provider_data.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
}
