# -*- coding: utf-8 -*-
{
    'name': 'Simulador Cuotas Nave',
    'version': '18.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Simulador de cuotas y listas de precio para Nave',
    'description': """
        Módulo para simular los recargos financieros de las cuotas de Nave
        y calcular precios finales a partir de reglas de comisión.
    """,
    'author': 'Martin',
    'depends': ['sale_management', 'product', 'payment_nave'],
    'data': [
        'security/ir.model.access.csv',
        'security/nave_commission_rule_security.xml',
        'views/nave_commission_rule_views.xml',
        'views/product_pricelist_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
