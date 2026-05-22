# -*- coding: utf-8 -*-

from odoo import api, fields, models


class NaveCommissionRule(models.Model):
    _name = 'nave.commission.rule'
    _description = 'Regla de Comisión de Nave'
    _order = 'installments asc, name'

    name = fields.Char(string='Nombre', required=True)
    active = fields.Boolean(default=True)
    
    payment_method_type = fields.Selection([
        ('credit', 'Tarjeta de Crédito'),
        ('debit', 'Tarjeta de Débito'),
        ('transfer', 'Transferencia'),
    ], string='Tipo de Medio de Pago', required=True, default='credit')
    
    bank_id = fields.Many2one('res.bank', string='Banco Emisor (Opcional)')
    installments = fields.Integer(string='Cantidad de Cuotas', required=True, default=1)
    
    # Tasas
    interest_rate = fields.Float(string='Tasa Directa (%)', help="Tasa de recargo financiero directo", default=0.0)
    tax_rate = fields.Float(string='IVA sobre Intereses (%)', default=21.0)
    fixed_fee = fields.Float(string='Costo Fijo Adicional ($)', default=0.0)
    
    total_cost_percentage = fields.Float(
        string='Costo Financiero Total (%)', 
        compute='_compute_total_cost_percentage',
        store=True,
        help="Costo total sumando interés + IVA."
    )

    @api.depends('interest_rate', 'tax_rate')
    def _compute_total_cost_percentage(self):
        for rule in self:
            # Fórmula simple: Interés + (Interés * IVA / 100)
            rule.total_cost_percentage = rule.interest_rate * (1 + (rule.tax_rate / 100.0))

    def calculate_price_for_payout(self, target_payout):
        """
        Calcula el precio bruto que se le debe cobrar al cliente
        para que el comercio reciba exactamente el `target_payout` (neto).
        
        Fórmula:
        Precio Bruto = (Target Payout + Costo Fijo) / (1 - (Costo Financiero Total / 100))
        """
        self.ensure_one()
        percentage_decimal = self.total_cost_percentage / 100.0
        
        if percentage_decimal >= 1.0:
            return 0.0 # Evitar división por cero o negativa
            
        gross_price = (target_payout + self.fixed_fee) / (1.0 - percentage_decimal)
        return gross_price
