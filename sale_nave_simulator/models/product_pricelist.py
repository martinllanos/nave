# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    nave_commission_rule_id = fields.Many2one(
        'nave.commission.rule',
        string='Regla de Comisión Nave',
        check_company=True,
        help='Si se selecciona una regla, esta lista de precios se calculará dinámicamente para absorber el costo financiero de Nave.'
    )

    is_nave_simulator = fields.Boolean(
        string='Usa Simulador Nave',
        compute='_compute_is_nave_simulator',
        store=True
    )

    @api.depends('nave_commission_rule_id')
    def _compute_is_nave_simulator(self):
        for pricelist in self:
            pricelist.is_nave_simulator = bool(pricelist.nave_commission_rule_id)
