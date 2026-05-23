# -*- coding: utf-8 -*-

import json
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.payment.tests.http_common import PaymentHttpCommon


@tagged('post_install', '-at_install', 'payment_nave')
class TestNaveHttp(PaymentHttpCommon):
    """HTTP tests for Nave payment controllers."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.nave_provider = cls.env['payment.provider'].create({
            'name': 'Nave Test HTTP',
            'code': 'nave',
            'state': 'test',
            'company_id': cls.env.company.id,
            'nave_client_id': 'test_client_id_http',
            'nave_client_secret': 'test_client_secret_http',
            'nave_pos_id': 'pos-test-http-001',
            'payment_method_ids': [
                (6, 0, [cls.env.ref('payment.payment_method_card').id]),
            ],
        })
        cls.currency_ars = cls.env.ref('base.ARS')
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente HTTP Nave',
            'email': 'http@test.com',
            'vat': '20055361682',
            'country_id': cls.env.ref('base.ar').id,
        })

    @patch('odoo.addons.payment_nave.models.payment_provider.PaymentProvider._nave_make_request')
    def test_webhook_controller_acknowledges_and_sets_done(self, mock_make_request):
        """POST /payment/nave/webhook must acknowledge and reconcile the transaction."""
        mock_make_request.return_value = {
            'id': 'pay-http-001',
            'status': {'name': 'APPROVED', 'reason_code': 'transaction_successful'},
            'wallet': {'name': 'visa'},
        }
        self.nave_provider.write({
            'nave_access_token': 'tok_http',
            'nave_token_expiry': '2099-01-01 00:00:00',
        })

        tx = self.env['payment.transaction'].create({
            'provider_id': self.nave_provider.id,
            'payment_method_id': self.env.ref('payment.payment_method_card').id,
            'amount': 500.00,
            'currency_id': self.currency_ars.id,
            'reference': 'TEST-NAVE-HTTP-001',
            'partner_id': self.partner.id,
            'operation': 'online_redirect',
        })

        url = self._build_url('/payment/nave/webhook')
        payload = {
            'payment_id': 'pay-http-001',
            'external_payment_id': 'TEST-NAVE-HTTP-001',
        }
        response = self.opener.post(
            url,
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.provider_reference, 'pay-http-001')

    @patch('odoo.addons.payment_nave.models.payment_provider.PaymentProvider._nave_make_request')
    def test_return_route_processes_notification(self, mock_make_request):
        """GET /payment/nave/return must process payment data before redirecting."""
        mock_make_request.return_value = {
            'id': 'pay-return-001',
            'status': {'name': 'APPROVED', 'reason_code': 'transaction_successful'},
            'wallet': {'name': 'mastercard'},
        }
        self.nave_provider.write({
            'nave_access_token': 'tok_return',
            'nave_token_expiry': '2099-01-01 00:00:00',
        })

        tx = self.env['payment.transaction'].create({
            'provider_id': self.nave_provider.id,
            'payment_method_id': self.env.ref('payment.payment_method_card').id,
            'amount': 750.00,
            'currency_id': self.currency_ars.id,
            'reference': 'TEST-NAVE-RET-001',
            'partner_id': self.partner.id,
            'operation': 'online_redirect',
        })

        url = self._build_url('/payment/nave/return')
        response = self.opener.get(url, params={
            'payment_id': 'pay-return-001',
            'external_payment_id': 'TEST-NAVE-RET-001',
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('/payment/status', response.url)
        self.assertEqual(tx.state, 'done')
