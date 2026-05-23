# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class NavePaymentLinkWizard(models.TransientModel):
    """Generate Nave payment links from invoices or sale orders with Odoo reconciliation."""

    _name = 'nave.payment.link.wizard'
    _description = 'Generador de Link de Pago Nave'

    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    provider_id = fields.Many2one(
        'payment.provider',
        string='Proveedor Nave',
        domain="[('code', '=', 'nave'), ('state', '!=', 'disabled'), "
               "('company_id', '=', company_id)]",
        required=True,
        check_company=True,
    )
    move_id = fields.Many2one(
        'account.move',
        string='Factura',
        readonly=True,
    )
    sale_id = fields.Many2one(
        'sale.order',
        string='Pedido de Venta',
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        readonly=True,
    )
    amount = fields.Monetary(
        string='Monto a Cobrar',
        currency_field='currency_id',
        required=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        readonly=True,
        default=lambda self: self.env.ref('base.ARS', raise_if_not_found=False),
    )
    duration_hours = fields.Integer(
        string='Validez del Link (horas)',
        default=24,
        help='Tiempo en horas durante el cual el link de pago estará activo.',
    )
    external_reference = fields.Char(
        string='Referencia Externa',
        readonly=True,
        help='Referencia enviada a Nave como external_payment_id (máx. 36 caracteres).',
    )
    payment_transaction_id = fields.Many2one(
        'payment.transaction',
        string='Transacción de Pago',
        readonly=True,
    )
    nave_link = fields.Char(
        string='Link de Pago Nave',
        readonly=True,
    )
    nave_payment_request_id = fields.Char(
        string='Nave Payment Request ID',
        readonly=True,
    )
    link_generated = fields.Boolean(default=False)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        if not active_model or not active_id:
            return res

        if active_model == 'account.move':
            move = self.env['account.move'].browse(active_id)
            if move.exists() and move.move_type in ('out_invoice', 'out_refund'):
                res.update({
                    'move_id': move.id,
                    'partner_id': move.partner_id.id,
                    'amount': move.amount_residual,
                    'currency_id': move.currency_id.id,
                    'company_id': move.company_id.id,
                    'external_reference': (move.name or f'MOVE-{move.id}')[:36],
                })
        elif active_model == 'sale.order':
            sale = self.env['sale.order'].browse(active_id)
            if sale.exists():
                res.update({
                    'sale_id': sale.id,
                    'partner_id': sale.partner_id.id,
                    'amount': sale.amount_total,
                    'currency_id': sale.currency_id.id,
                    'company_id': sale.company_id.id,
                    'external_reference': (sale.name or f'SO-{sale.id}')[:36],
                })

        company_id = res.get('company_id', self.env.company.id)
        nave_provider = self.env['payment.provider'].search([
            ('code', '=', 'nave'),
            ('state', '!=', 'disabled'),
            ('company_id', '=', company_id),
        ], limit=1)
        if nave_provider:
            res['provider_id'] = nave_provider.id
        return res

    def action_generate_link(self):
        """Create a payment transaction and a Nave payment_link intent."""
        self.ensure_one()

        if self.amount <= 0:
            raise UserError(_('El monto a cobrar debe ser mayor a cero.'))
        if not self.external_reference:
            raise UserError(_('La referencia externa es obligatoria.'))

        provider = self.provider_id.with_company(self.company_id)
        payment_method = provider.payment_method_ids[:1]
        if not payment_method:
            raise UserError(_(
                'No hay métodos de pago configurados en el proveedor Nave.'
            ))

        tx_vals = {
            'provider_id': provider.id,
            'payment_method_id': payment_method.id,
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'partner_id': self.partner_id.id,
            'operation': 'online_redirect',
            'reference': self.external_reference,
        }
        if self.move_id:
            tx_vals['invoice_ids'] = [(6, 0, [self.move_id.id])]
        if self.sale_id:
            tx_vals['sale_order_ids'] = [(6, 0, [self.sale_id.id])]

        tx = self.env['payment.transaction'].create(tx_vals)

        payload = {
            'external_payment_id': self.external_reference,
            'seller': {
                'pos_id': provider.nave_pos_id,
            },
            'transactions': [
                {
                    'amount': {
                        'currency': 'ARS',
                        'value': f"{self.amount:.2f}",
                    },
                    'products': self._nave_build_products_payload(),
                }
            ],
            'buyer': self._nave_build_buyer_payload(),
            'duration_time': self.duration_hours * 3600,
        }

        _logger.info(
            "[payment_nave] Generating payment link for '%s' (company %s).",
            self.external_reference,
            self.company_id.name,
        )
        data = provider._nave_make_request(
            '/api/payment_request/payment_link',
            payload=payload,
        )

        checkout_url = data.get('checkout_url')
        payment_request_id = data.get('id')
        if not checkout_url:
            raise UserError(_(
                "Nave processed the request but did not return a valid payment URL."
            ))

        tx.write({
            'nave_payment_request_id': payment_request_id,
            'nave_checkout_url': checkout_url,
        })
        self.write({
            'payment_transaction_id': tx.id,
            'nave_link': checkout_url,
            'nave_payment_request_id': payment_request_id,
            'link_generated': True,
        })
        self._post_link_to_chatter(checkout_url)

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def _nave_build_products_payload(self):
        """Build the products list from the source document."""
        self.ensure_one()
        products = []

        if self.move_id:
            for line in self.move_id.invoice_line_ids.filtered(
                lambda inv_line: not inv_line.display_type
            ):
                products.append({
                    'name': (line.product_id.name or line.name or 'Item')[:100],
                    'description': (line.name or '')[:150],
                    'quantity': int(line.quantity) or 1,
                    'unit_price': {
                        'currency': 'ARS',
                        'value': f"{line.price_unit:.2f}",
                    },
                })
        elif self.sale_id:
            for line in self.sale_id.order_line.filtered(
                lambda sale_line: not sale_line.display_type
            ):
                products.append({
                    'name': (line.product_id.name or line.name or 'Item')[:100],
                    'description': (line.name or '')[:150],
                    'quantity': int(line.product_uom_qty) or 1,
                    'unit_price': {
                        'currency': 'ARS',
                        'value': f"{line.price_reduce_taxexcl:.2f}",
                    },
                })

        if not products:
            products.append({
                'name': f"Payment {self.external_reference}"[:100],
                'description': 'Payment link generated from Odoo',
                'quantity': 1,
                'unit_price': {
                    'currency': 'ARS',
                    'value': f"{self.amount:.2f}",
                },
            })
        return products

    def _nave_build_buyer_payload(self):
        """Map the partner to the Nave buyer object."""
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            return {}

        doc_number = partner.vat or '00000000'
        doc_type = 'CUIT' if len(doc_number) > 8 else 'DNI'
        return {
            'doc_type': doc_type,
            'doc_number': doc_number,
            'name': (partner.name or '')[:50],
            'user_email': partner.email or '',
            'user_id': str(partner.id),
            'billing_address': {
                'street_1': (partner.street or 'S/D')[:100],
                'street_2': (partner.street2 or '')[:100],
                'city': partner.city or 'S/D',
                'region': partner.state_id.name or 'S/D',
                'country': 'AR',
                'zipcode': partner.zip or '0000',
            },
        }

    def _post_link_to_chatter(self, checkout_url):
        """Log the generated link on the source document chatter."""
        self.ensure_one()
        msg = _(
            "Link de pago Nave generado: "
            "<a href='%(url)s' target='_blank'>%(url)s</a><br/>"
            "<small>Referencia: %(ref)s | Monto: %(amount)s ARS</small>",
            url=checkout_url,
            ref=self.external_reference,
            amount=f"{self.amount:.2f}",
        )
        doc = self.move_id or self.sale_id
        if doc and hasattr(doc, 'message_post'):
            doc.message_post(
                body=msg,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
