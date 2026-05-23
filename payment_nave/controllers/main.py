# -*- coding: utf-8 -*-

import logging
import pprint

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class PaymentNaveController(http.Controller):
    _return_url = '/payment/nave/return'
    _webhook_url = '/payment/nave/webhook'

    @http.route(_return_url, type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def nave_return_from_checkout(self, **data):
        """Process notification data after the customer returns from Nave checkout."""
        _logger.info("Handling redirection from Nave with data:\n%s", pprint.pformat(data))
        notification_data = self._normalize_notification_data(data)
        if notification_data:
            try:
                request.env['payment.transaction'].sudo()._handle_notification_data(
                    'nave', notification_data
                )
            except ValidationError:
                _logger.exception(
                    "Unable to handle the notification data from Nave return; continuing redirect"
                )
        return request.redirect('/payment/status')

    @http.route(_webhook_url, type='http', auth='public', methods=['POST'], csrf=False)
    def nave_webhook(self):
        """Process asynchronous payment notifications sent by Nave (S2S)."""
        data = request.get_json_data()
        _logger.info("Notification received from Nave with data:\n%s", pprint.pformat(data))

        if not data.get('external_payment_id') or not data.get('payment_id'):
            _logger.warning(
                "Nave webhook skipped: missing external_payment_id or payment_id."
            )
            return ''

        try:
            request.env['payment.transaction'].sudo()._handle_notification_data('nave', data)
        except ValidationError:
            _logger.exception(
                "Unable to handle the notification data; skipping to acknowledge"
            )
        return ''

    @staticmethod
    def _normalize_notification_data(data):
        """Build notification data dict from return query parameters."""
        payment_id = data.get('payment_id')
        external_payment_id = data.get('external_payment_id') or data.get('external_reference')
        if not payment_id or payment_id in ('null', 'None', ''):
            return None
        if not external_payment_id:
            return None
        return {
            'payment_id': payment_id,
            'external_payment_id': external_payment_id,
        }
