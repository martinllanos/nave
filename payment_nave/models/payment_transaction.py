# -*- coding: utf-8 -*-

import logging

from werkzeug import urls

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.payment_nave import const
from odoo.addons.payment_nave.controllers.main import PaymentNaveController

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    nave_payment_request_id = fields.Char(
        string="Nave Intención ID",
        readonly=True,
    )
    nave_checkout_url = fields.Char(
        string="Nave Checkout URL",
        readonly=True,
    )
    nave_payment_id = fields.Char(
        string="Nave Pago ID",
        readonly=True,
    )

    def _get_specific_rendering_values(self, processing_values):
        """Create a Nave payment intent and return the checkout redirect URL."""
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'nave':
            return res

        return_url = urls.url_join(self.get_base_url(), PaymentNaveController._return_url)
        payload = {
            'external_payment_id': self.reference,
            'seller': {
                'pos_id': self.provider_id.nave_pos_id,
            },
            'transactions': [
                {
                    'amount': {
                        'currency': 'ARS',
                        'value': f"{self.amount:.2f}",
                    },
                    'products': self._nave_get_products_payload(),
                }
            ],
            'buyer': self._nave_get_buyer_payload(),
            'additional_info': {
                'callback_url': return_url,
            },
            'duration_time': 3000,
        }

        _logger.info(
            "Sending payment intent to Nave for transaction %s.", self.reference
        )
        data = self.provider_id._nave_make_request(
            '/api/payment_request/ecommerce',
            payload=payload,
        )

        checkout_url = data.get('checkout_url')
        payment_request_id = data.get('id')
        if not checkout_url or not payment_request_id:
            _logger.error("Nave did not return checkout_url or id. Response keys: %s", data.keys())
            raise UserError(_("Nave could not process this payment request."))

        self.write({
            'nave_payment_request_id': payment_request_id,
            'nave_checkout_url': checkout_url,
        })
        return {'api_url': checkout_url}

    def _nave_get_products_payload(self):
        """Build the products list from linked sale orders or invoices."""
        self.ensure_one()
        products = []

        if self.sale_order_ids:
            order_lines = self.sale_order_ids.mapped('order_line').filtered(
                lambda line: not line.display_type
            )
            for line in order_lines:
                products.append({
                    'name': line.product_id.name[:100],
                    'description': (line.name or '')[:150],
                    'quantity': int(line.product_uom_qty) or 1,
                    'unit_price': {
                        'currency': 'ARS',
                        'value': f"{line.price_reduce_taxexcl:.2f}",
                    },
                })
        elif self.invoice_ids:
            invoice_lines = self.invoice_ids.mapped('invoice_line_ids').filtered(
                lambda line: not line.display_type
            )
            for line in invoice_lines:
                products.append({
                    'name': (line.product_id.name if line.product_id else line.name)[:100],
                    'description': (line.name or '')[:150],
                    'quantity': int(line.quantity) or 1,
                    'unit_price': {
                        'currency': 'ARS',
                        'value': f"{line.price_unit:.2f}",
                    },
                })

        if not products:
            products.append({
                'name': f"Payment {self.reference}"[:100],
                'description': f"Odoo reference: {self.reference}",
                'quantity': 1,
                'unit_price': {
                    'currency': 'ARS',
                    'value': f"{self.amount:.2f}",
                },
            })
        return products

    def _nave_get_buyer_payload(self):
        """Map the Odoo partner to the Nave buyer object."""
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
                'street_2': (partner.street2 or 'N/A')[:100],
                'city': partner.city or 'S/D',
                'region': partner.state_id.name or 'S/D',
                'country': 'AR',
                'zipcode': partner.zip or '0000',
            },
        }

    @api.model
    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Find the transaction from Nave notification data."""
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'nave' or len(tx) == 1:
            return tx

        reference = notification_data.get('external_payment_id')
        if not reference:
            raise ValidationError(
                "Nave: " + _("Received data with missing external payment reference.")
            )

        tx = self.search([
            ('reference', '=', reference),
            ('provider_code', '=', 'nave'),
        ])
        if not tx:
            raise ValidationError(
                "Nave: " + _("No transaction found matching reference %s.", reference)
            )
        return tx

    def _process_notification_data(self, notification_data):
        """Verify payment status with Nave API and update the transaction state."""
        super()._process_notification_data(notification_data)
        if self.provider_code != 'nave':
            return

        payment_id = notification_data.get('payment_id')
        if not payment_id:
            raise ValidationError("Nave: " + _("Received data with missing payment id."))

        self.write({
            'nave_payment_id': payment_id,
            'provider_reference': payment_id,
        })

        payment_data = self.provider_id._nave_make_request(
            f'/ranty-payments/payments/{payment_id}',
            method='GET',
        )

        status_name = payment_data.get('status', {}).get('name')
        reason_code = payment_data.get('status', {}).get('reason_code', 'transaction_successful')

        _logger.info(
            "Nave payment verification for %s: status=%s (%s)",
            self.reference, status_name, reason_code,
        )

        if not status_name:
            raise ValidationError("Nave: " + _("Received data with missing payment status."))

        if status_name in const.TRANSACTION_STATUS_MAPPING['pending']:
            self._set_pending()
        elif status_name in const.TRANSACTION_STATUS_MAPPING['done']:
            wallet_name = payment_data.get('wallet', {}).get('name', 'N/A')
            self._set_done(state_message=_(
                "Payment approved via Nave. Wallet: %s. Nave ID: %s",
                wallet_name.upper(),
                payment_id,
            ))
        elif status_name in const.TRANSACTION_STATUS_MAPPING['canceled']:
            if status_name in ('REFUNDED', 'PURCHASE_REVERSED'):
                self._set_canceled(state_message=_(
                    "The payment was refunded or reversed in Nave."
                ))
            else:
                self._set_canceled(state_message=_(
                    "Payment rejected or cancelled in Nave. Reason: %s", reason_code
                ))
        else:
            _logger.warning(
                "Invalid payment status from Nave for %s: %s",
                self.reference, status_name,
            )
            self._set_error(
                "Nave: " + _("Received data with invalid status: %s", status_name)
            )

    def _send_refund_request(self, amount_to_refund=None, **kwargs):
        """Request a refund through Nave DELETE /api/payments/{id}."""
        res = super()._send_refund_request(amount_to_refund=amount_to_refund, **kwargs)
        if self.provider_code != 'nave':
            return res

        payment_id = self.nave_payment_id or self.provider_reference
        if not payment_id:
            raise UserError(_(
                "Nave: No payment id is recorded for this transaction; cannot refund."
            ))

        _logger.info("Requesting Nave refund for payment %s.", payment_id)
        data = self.provider_id._nave_make_request(
            f'/api/payments/{payment_id}',
            method='DELETE',
        )
        if data.get('status') == 'CANCELLING':
            self._set_canceled(state_message=_(
                "The refund is being processed ('CANCELLING') in Nave."
            ))
        return res
