# -*- coding: utf-8 -*-
# [ADD] payment_nave: Tests funcionales para el proveedor de pago Nave.
# Cubre: autenticación (caché de token), creación de intención de pago,
# procesamiento de webhooks, reembolsos y el wizard de link de pago.

from unittest.mock import patch, MagicMock

from odoo.tests import tagged
from odoo.addons.payment.tests.common import PaymentCommon


@tagged('post_install', '-at_install', 'payment_nave')
class TestNaveProvider(PaymentCommon):
    """Tests funcionales para el proveedor de pago Nave."""

    # ──────────────────────────────────────────────
    # SETUP
    # ──────────────────────────────────────────────

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.nave_provider = cls.env['payment.provider'].create({
            'name': 'Nave Test',
            'code': 'nave',
            'state': 'test',
            'company_id': cls.env.company.id,
            'nave_client_id': 'test_client_id_12345',
            'nave_client_secret': 'test_client_secret_xyz',
            'nave_pos_id': 'pos-test-uuid-001',
            'payment_method_ids': [
                (6, 0, [cls.env.ref('payment.payment_method_card').id]),
            ],
        })

        cls.currency_ars = cls.env.ref('base.ARS')
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Test Nave',
            'email': 'cliente@test.com',
            'vat': '20055361682',
            'country_id': cls.env.ref('base.ar').id,
        })

    # ──────────────────────────────────────────────
    # 1. AUTENTICACIÓN Y CACHÉ DE TOKEN
    # ──────────────────────────────────────────────

    @patch('odoo.addons.payment_nave.models.payment_provider.requests.post')
    def test_01_auth_token_fresh_request(self, mock_post):
        """Verifica que se solicita un token nuevo cuando no hay token cacheado."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'access_token': 'test_bearer_token_abc',
            'expires_in': 86400,
            'token_type': 'Bearer',
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # Limpiar caché
        self.nave_provider.write({
            'nave_access_token': False,
            'nave_token_expiry': False,
        })

        token = self.nave_provider._nave_get_access_token()

        self.assertEqual(token, 'test_bearer_token_abc')
        self.assertTrue(mock_post.called, "Debería haberse llamado al endpoint de Auth0")
        self.assertEqual(self.nave_provider.nave_access_token, 'test_bearer_token_abc')
        self.assertTrue(self.nave_provider.nave_token_expiry)

    def test_02_auth_token_cached_reuse(self):
        """Verifica que se reutiliza el token cacheado si aún es válido."""
        from odoo import fields
        from datetime import timedelta

        future_expiry = fields.Datetime.now() + timedelta(hours=10)
        self.nave_provider.write({
            'nave_access_token': 'cached_token_xyz',
            'nave_token_expiry': future_expiry,
        })

        with patch('odoo.addons.payment_nave.models.payment_provider.requests.post') as mock_post:
            token = self.nave_provider._nave_get_access_token()
            mock_post.assert_not_called()

        self.assertEqual(token, 'cached_token_xyz',
                         "Debería haberse devuelto el token cacheado sin llamar a Auth0")

    def test_03_api_url_sandbox_vs_prod(self):
        """Verifica que las URLs de API son correctas según el estado del proveedor."""
        self.nave_provider.state = 'test'
        self.assertIn('sandbox', self.nave_provider._nave_get_api_url())
        self.assertIn('homoservices', self.nave_provider._nave_get_auth_url())

        self.nave_provider.state = 'enabled'
        self.assertEqual('https://api.ranty.io', self.nave_provider._nave_get_api_url())
        # Restaurar
        self.nave_provider.state = 'test'

    # ──────────────────────────────────────────────
    # 2. TRANSACCIONES — CREACIÓN DE INTENCIÓN
    # ──────────────────────────────────────────────

    @patch('odoo.addons.payment_nave.models.payment_provider.PaymentProvider._nave_make_request')
    def test_04_checkout_creates_payment_intent(self, mock_make_request):
        """Verifica que _get_specific_rendering_values crea correctamente una intención en Nave."""
        mock_make_request.return_value = {
            'id': 'pr-nave-001',
            'checkout_url': 'https://checkout.ranty.io/pay/pr-nave-001',
        }
        self.nave_provider.write({
            'nave_access_token': 'tok_test',
            'nave_token_expiry': '2099-01-01 00:00:00',
        })

        tx = self.env['payment.transaction'].create({
            'provider_id': self.nave_provider.id,
            'payment_method_id': self.payment_method_id,
            'amount': 1500.00,
            'currency_id': self.currency_ars.id,
            'reference': 'TEST-NAVE-001',
            'partner_id': self.partner.id,
            'operation': 'online_redirect',
        })

        rendering_values = tx._get_specific_rendering_values({})

        self.assertIn('api_url', rendering_values)
        self.assertEqual(rendering_values['api_url'], 'https://checkout.ranty.io/pay/pr-nave-001')
        self.assertEqual(tx.nave_payment_request_id, 'pr-nave-001')

    # ──────────────────────────────────────────────
    # 3. WEBHOOKS — PROCESAMIENTO SEGURO
    # ──────────────────────────────────────────────

    @patch('odoo.addons.payment_nave.models.payment_provider.PaymentProvider._nave_make_request')
    def test_05_webhook_approved_sets_done(self, mock_make_request):
        """Verifica que un webhook APPROVED con GET de validación concilia la transacción."""
        mock_make_request.return_value = {
            'id': 'pay-nave-approved-001',
            'status': {'name': 'APPROVED', 'reason_code': 'transaction_successful'},
            'wallet': {'name': 'mercado pago'},
            'amount': {'currency': 'ARS', 'value': '1500.00'},
        }
        self.nave_provider.write({
            'nave_access_token': 'tok_test',
            'nave_token_expiry': self.env['payment.provider']._fields['nave_token_expiry'].from_string('2099-01-01 00:00:00'),
        })

        tx = self.env['payment.transaction'].create({
            'provider_id': self.nave_provider.id,
            'payment_method_id': self.payment_method_id,
            'amount': 1500.00,
            'currency_id': self.currency_ars.id,
            'reference': 'TEST-NAVE-WH-001',
            'partner_id': self.partner.id,
            'operation': 'online_redirect',
            'nave_payment_request_id': 'pr-nave-001',
        })

        webhook_data = {
            'payment_id': 'pay-nave-approved-001',
            'external_payment_id': 'TEST-NAVE-WH-001',
        }
        tx._process_notification_data(webhook_data)

        self.assertEqual(tx.state, 'done',
                         "La transacción debería pasar a 'done' tras un webhook APPROVED verificado.")
        self.assertEqual(tx.nave_payment_id, 'pay-nave-approved-001')
        self.assertEqual(tx.provider_reference, 'pay-nave-approved-001')

    @patch('odoo.addons.payment_nave.models.payment_provider.PaymentProvider._nave_make_request')
    def test_06_webhook_rejected_cancels_tx(self, mock_make_request):
        """Verifica que un webhook REJECTED cancela la transacción en Odoo."""
        mock_make_request.return_value = {
            'id': 'pay-nave-rejected-001',
            'status': {'name': 'REJECTED', 'reason_code': 'insufficient_funds'},
            'amount': {'currency': 'ARS', 'value': '1500.00'},
        }
        self.nave_provider.write({
            'nave_access_token': 'tok_test',
            'nave_token_expiry': self.env['payment.provider']._fields['nave_token_expiry'].from_string('2099-01-01 00:00:00'),
        })

        tx = self.env['payment.transaction'].create({
            'provider_id': self.nave_provider.id,
            'payment_method_id': self.payment_method_id,
            'amount': 1500.00,
            'currency_id': self.currency_ars.id,
            'reference': 'TEST-NAVE-WH-002',
            'partner_id': self.partner.id,
            'operation': 'online_redirect',
        })

        webhook_data = {
            'payment_id': 'pay-nave-rejected-001',
            'external_payment_id': 'TEST-NAVE-WH-002',
        }
        tx._process_notification_data(webhook_data)

        self.assertEqual(tx.state, 'cancel',
                         "La transacción debería cancelarse tras un webhook REJECTED.")

    # ──────────────────────────────────────────────
    # 4. REEMBOLSOS
    # ──────────────────────────────────────────────

    @patch('odoo.addons.payment_nave.models.payment_provider.PaymentProvider._nave_make_request')
    def test_07_refund_calls_nave_delete(self, mock_make_request):
        """Verifica que _send_refund_request invoca DELETE /api/payments/{id} en Nave."""
        mock_make_request.return_value = {'status': 'CANCELLING'}
        self.nave_provider.write({
            'nave_access_token': 'tok_test',
            'nave_token_expiry': self.env['payment.provider']._fields['nave_token_expiry'].from_string('2099-01-01 00:00:00'),
        })

        tx = self.env['payment.transaction'].create({
            'provider_id': self.nave_provider.id,
            'payment_method_id': self.payment_method_id,
            'amount': 1500.00,
            'currency_id': self.currency_ars.id,
            'reference': 'TEST-NAVE-REF-001',
            'partner_id': self.partner.id,
            'operation': 'online_redirect',
            'nave_payment_id': 'pay-nave-to-refund',
        })

        tx._send_refund_request()

        mock_make_request.assert_called_once()
        call_args = mock_make_request.call_args
        self.assertEqual(call_args[1]['method'], 'DELETE')
        self.assertIn('pay-nave-to-refund', call_args[0][0])

    # ──────────────────────────────────────────────
    # 5. WIZARD DE LINK DE PAGO
    # ──────────────────────────────────────────────

    @patch('odoo.addons.payment_nave.models.payment_provider.PaymentProvider._nave_make_request')
    def test_08_link_wizard_generates_nave_url(self, mock_make_request):
        """Verifica que el wizard crea payment.transaction y genera el link en Nave."""
        mock_make_request.return_value = {
            'id': 'pr-link-001',
            'checkout_url': 'https://checkout.ranty.io/link/pr-link-001',
        }
        self.nave_provider.write({
            'nave_access_token': 'tok_test',
            'nave_token_expiry': self.env['payment.provider']._fields['nave_token_expiry'].from_string('2099-01-01 00:00:00'),
        })

        wizard = self.env['nave.payment.link.wizard'].create({
            'provider_id': self.nave_provider.id,
            'company_id': self.env.company.id,
            'partner_id': self.partner.id,
            'amount': 2500.00,
            'currency_id': self.currency_ars.id,
            'external_reference': 'INV-2026-0001',
            'duration_hours': 48,
        })

        wizard.action_generate_link()

        self.assertEqual(wizard.nave_link, 'https://checkout.ranty.io/link/pr-link-001')
        self.assertTrue(wizard.link_generated)
        self.assertTrue(wizard.payment_transaction_id)
        self.assertEqual(
            wizard.payment_transaction_id.reference,
            'INV-2026-0001',
        )

        mock_make_request.assert_called_once()
        self.assertIn(
            'payment_link',
            mock_make_request.call_args[0][0],
            "El wizard debe usar el endpoint /payment_link, no /ecommerce",
        )

    def test_09_link_wizard_amount_validation(self):
        """Verifica que el wizard rechaza montos menores o iguales a 0."""
        wizard = self.env['nave.payment.link.wizard'].create({
            'provider_id': self.nave_provider.id,
            'company_id': self.env.company.id,
            'amount': 0.0,
            'currency_id': self.currency_ars.id,
            'external_reference': 'INV-2026-0002',
        })

        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            wizard.action_generate_link()

    def test_10_nave_payload_amount_format(self):
        """Verifica que el monto se formatea siempre como string con 2 decimales."""
        wizard = self.env['nave.payment.link.wizard'].create({
            'provider_id': self.nave_provider.id,
            'company_id': self.env.company.id,
            'amount': 999.5,
            'currency_id': self.currency_ars.id,
            'external_reference': 'INV-2026-0003',
        })
        products = wizard._nave_build_products_payload()
        formatted_value = products[0]['unit_price']['value']
        self.assertEqual(formatted_value, '999.50',
                         "El monto debe tener exactamente 2 decimales en formato string")
