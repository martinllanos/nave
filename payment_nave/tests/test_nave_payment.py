# -*- coding: utf-8 -*-
# [ADD] payment_nave: Tests funcionales para el proveedor de pago Nave.
# Cubre: autenticación (caché de token), creación de intención de pago,
# procesamiento de webhooks, reembolsos y el wizard de link de pago.

from unittest.mock import patch, MagicMock

from odoo import Command
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

        # El proveedor real queda vinculado a sus métodos de pago por el XML del módulo; el de
        # los tests se crea a mano, así que hay que asociarlos igual o el wizard no puede armar
        # la transacción (payment_method_id es obligatorio).
        cls.nave_qr_method = cls.env.ref('payment_nave.payment_method_nave_qr')
        cls.nave_provider = cls.env['payment.provider'].create({
            'name': 'Nave Test',
            'code': 'nave',
            'state': 'test',
            'company_id': cls.env.company.id,
            'nave_client_id': 'test_client_id_12345',
            'nave_client_secret': 'test_client_secret_xyz',
            'nave_pos_id': 'pos-test-uuid-001',
            'payment_method_ids': [Command.set([cls.nave_qr_method.id])],
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

    @patch('odoo.addons.payment_nave.models.payment_provider.requests.post')
    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.post')
    def test_04_checkout_creates_payment_intent(self, mock_tx_post, mock_auth_post):
        """Verifica que _get_specific_rendering_values crea correctamente una intención en Nave."""

        def mock_post_side_effect(url, *args, **kwargs):
            if 'auth0' in url:
                return MagicMock(
                    json=MagicMock(return_value={'access_token': 'tok_test', 'expires_in': 3600}),
                    raise_for_status=MagicMock(return_value=None),
                )
            else:
                return MagicMock(
                    json=MagicMock(return_value={'id': 'pr-nave-001', 'checkout_url': 'https://checkout.ranty.io/pay/pr-nave-001'}),
                    raise_for_status=MagicMock(return_value=None),
                )

        mock_tx_post.side_effect = mock_post_side_effect
        mock_auth_post.side_effect = mock_post_side_effect

        self.nave_provider.write({
            'nave_access_token': False,
            'nave_token_expiry': False,
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

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_05_webhook_approved_sets_done(self, mock_get):
        """Verifica que un webhook APPROVED con GET de validación concilia la transacción."""
        mock_get.return_value = MagicMock(
            json=MagicMock(return_value={
                'id': 'pay-nave-approved-001',
                'status': {'name': 'APPROVED', 'reason_code': 'transaction_successful'},
                'wallet': {'name': 'mercado pago'},
                'amount': {'currency': 'ARS', 'value': '1500.00'},
            }),
            raise_for_status=MagicMock(return_value=None),
        )
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

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_06_webhook_rejected_cancels_tx(self, mock_get):
        """Verifica que un webhook REJECTED cancela la transacción en Odoo."""
        mock_get.return_value = MagicMock(
            json=MagicMock(return_value={
                'id': 'pay-nave-rejected-001',
                'status': {'name': 'REJECTED', 'reason_code': 'insufficient_funds'},
                'amount': {'currency': 'ARS', 'value': '1500.00'},
            }),
            raise_for_status=MagicMock(return_value=None),
        )
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

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.delete')
    def test_07_refund_calls_nave_delete(self, mock_delete):
        """Verifica que _execute_refund invoca DELETE /api/payments/{id} en Nave."""
        mock_delete.return_value = MagicMock(
            json=MagicMock(return_value={'status': 'CANCELLING'}),
            raise_for_status=MagicMock(return_value=None),
        )
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

        self.assertTrue(mock_delete.called, "Debería haberse llamado al endpoint DELETE de Nave")
        call_url = mock_delete.call_args[0][0]
        self.assertIn('pay-nave-to-refund', call_url)

    # ──────────────────────────────────────────────
    # 5. WIZARD DE LINK DE PAGO
    # ──────────────────────────────────────────────

    @patch('odoo.addons.payment_nave.models.nave_link_wizard.requests.post')
    def test_08_link_wizard_generates_nave_url(self, mock_post):
        """Verifica que el wizard genera un link real de Nave invocando la API correcta."""
        mock_post.return_value = MagicMock(
            json=MagicMock(return_value={
                'id': 'pr-link-001',
                'checkout_url': 'https://checkout.ranty.io/link/pr-link-001',
            }),
            raise_for_status=MagicMock(return_value=None),
        )
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

        # Verificar que se llamó al endpoint correcto (payment_link, no ecommerce)
        call_url = mock_post.call_args[0][0]
        self.assertIn('payment_link', call_url,
                      "El wizard debe usar el endpoint /payment_link, no /ecommerce")

        # El link debe quedar respaldado por una transacción, o el webhook no lo encuentra.
        tx = self.env['payment.transaction'].search([
            ('provider_id', '=', self.nave_provider.id),
            ('nave_payment_request_id', '=', 'pr-link-001'),
        ])
        self.assertEqual(len(tx), 1, "El wizard debe crear exactamente una transacción")
        self.assertEqual(tx.state, 'pending')
        self.assertEqual(tx.amount, 2500.00)
        self.assertEqual(tx.nave_checkout_url, 'https://checkout.ranty.io/link/pr-link-001')

        # La referencia enviada a Nave y la de la transacción tienen que ser idénticas.
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['external_payment_id'], tx.reference)

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

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    @patch('odoo.addons.payment_nave.models.nave_link_wizard.requests.post')
    def test_11_link_wizard_webhook_reconciles(self, mock_post, mock_get):
        """El webhook del pago de un link encuentra su transacción y la concilia.

        Es el circuito completo que antes se cortaba: el wizard no creaba transacción, el webhook
        no la encontraba, el controller devolvía 500 y la factura quedaba impaga para siempre.
        """
        mock_post.return_value = MagicMock(
            json=MagicMock(return_value={
                'id': 'pr-link-011',
                'checkout_url': 'https://checkout.ranty.io/link/pr-link-011',
            }),
            raise_for_status=MagicMock(return_value=None),
        )
        mock_get.return_value = MagicMock(
            json=MagicMock(return_value={
                'id': 'pay-link-011',
                'status': {'name': 'APPROVED', 'reason_code': 'transaction_successful'},
                'wallet': {'name': 'modo'},
            }),
            raise_for_status=MagicMock(return_value=None),
        )
        self.nave_provider.write({
            'nave_access_token': 'tok_test',
            'nave_token_expiry': self.env['payment.provider']._fields['nave_token_expiry'].from_string('2099-01-01 00:00:00'),
        })

        wizard = self.env['nave.payment.link.wizard'].create({
            'provider_id': self.nave_provider.id,
            'company_id': self.env.company.id,
            'partner_id': self.partner.id,
            'amount': 3300.00,
            'currency_id': self.currency_ars.id,
            'external_reference': 'INV-2026-0011',
        })
        wizard.action_generate_link()

        # Nave notifica con el external_payment_id que le mandamos.
        external_payment_id = mock_post.call_args[1]['json']['external_payment_id']
        tx = self.env['payment.transaction']._get_tx_from_notification_data(
            'nave', {'external_payment_id': external_payment_id, 'payment_id': 'pay-link-011'}
        )

        self.assertTrue(tx, "El webhook debe poder encontrar la transacción del link")
        tx._process_notification_data({
            'external_payment_id': external_payment_id,
            'payment_id': 'pay-link-011',
        })
        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.nave_payment_id, 'pay-link-011')

    @patch('odoo.addons.payment_nave.models.nave_link_wizard.requests.post')
    def test_12_link_wizard_reference_is_unique(self, mock_post):
        """Dos links con la misma referencia externa producen transacciones distintas."""
        mock_post.return_value = MagicMock(
            json=MagicMock(return_value={
                'id': 'pr-link-012',
                'checkout_url': 'https://checkout.ranty.io/link/pr-link-012',
            }),
            raise_for_status=MagicMock(return_value=None),
        )
        self.nave_provider.write({
            'nave_access_token': 'tok_test',
            'nave_token_expiry': self.env['payment.provider']._fields['nave_token_expiry'].from_string('2099-01-01 00:00:00'),
        })

        references = []
        for _i in range(2):
            wizard = self.env['nave.payment.link.wizard'].create({
                'provider_id': self.nave_provider.id,
                'company_id': self.env.company.id,
                'partner_id': self.partner.id,
                'amount': 1000.00,
                'currency_id': self.currency_ars.id,
                'external_reference': 'INV-2026-0012',
            })
            wizard.action_generate_link()
            references.append(mock_post.call_args[1]['json']['external_payment_id'])

        self.assertEqual(references[0], 'INV-2026-0012')
        self.assertNotEqual(references[0], references[1],
                            "Regenerar el link no puede reusar el mismo external_payment_id")

    def test_13_link_wizard_rejects_long_reference(self):
        """Una referencia que excede el tope de Nave se rechaza en vez de truncarse.

        Truncar rompería la conciliación: el webhook llega con el id truncado y la búsqueda por
        referencia completa no lo encuentra.
        """
        from odoo.exceptions import UserError
        wizard = self.env['nave.payment.link.wizard'].create({
            'provider_id': self.nave_provider.id,
            'company_id': self.env.company.id,
            'partner_id': self.partner.id,
            'amount': 1000.00,
            'currency_id': self.currency_ars.id,
            'external_reference': 'X' * 40,
        })
        with self.assertRaises(UserError):
            wizard.action_generate_link()

    # ──────────────────────────────────────────────
    # 6. SEGURIDAD DEL WEBHOOK
    # ──────────────────────────────────────────────

    def _nave_make_tx(self, reference):
        return self.env['payment.transaction'].create({
            'provider_id': self.nave_provider.id,
            'payment_method_id': self.payment_method_id,
            'amount': 1500.00,
            'currency_id': self.currency_ars.id,
            'reference': reference,
            'partner_id': self.partner.id,
            'operation': 'online_redirect',
        })

    def _nave_arm_token(self):
        self.nave_provider.write({
            'nave_access_token': 'tok_test',
            'nave_token_expiry': self.env['payment.provider']._fields['nave_token_expiry'].from_string('2099-01-01 00:00:00'),
        })

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_14_webhook_check_url_outside_nave_is_ignored(self, mock_get):
        """Una payment_check_url de otro dominio no se consulta: el webhook no viene firmado.

        Sin esta restricción, quien adivine una referencia puede apuntar la verificación a un
        servidor propio que responda APPROVED y dar por pagada una factura ajena.
        """
        mock_get.return_value = MagicMock(
            json=MagicMock(return_value={'id': 'pay-evil', 'status': {'name': 'APPROVED'}}),
            raise_for_status=MagicMock(return_value=None),
        )
        self._nave_arm_token()
        tx = self._nave_make_tx('TEST-NAVE-SSRF-001')

        tx._process_notification_data({
            'payment_id': 'pay-evil',
            'external_payment_id': 'TEST-NAVE-SSRF-001',
            'payment_check_url': 'https://atacante.example.com/ranty-payments/payments/pay-evil',
        })

        called_url = mock_get.call_args[0][0]
        self.assertNotIn('atacante.example.com', called_url,
                         "Nunca se debe consultar un host ajeno a Nave")
        self.assertEqual(
            called_url,
            'https://api-sandbox.ranty.io/ranty-payments/payments/pay-evil',
            "Debe caer al fallback construido localmente",
        )

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_15_webhook_check_url_lookalike_is_ignored(self, mock_get):
        """Un dominio que sólo se parece al de Nave tampoco se acepta."""
        mock_get.return_value = MagicMock(
            json=MagicMock(return_value={'id': 'pay-x', 'status': {'name': 'APPROVED'}}),
            raise_for_status=MagicMock(return_value=None),
        )
        self._nave_arm_token()
        tx = self._nave_make_tx('TEST-NAVE-SSRF-002')

        tx._process_notification_data({
            'payment_id': 'pay-x',
            'external_payment_id': 'TEST-NAVE-SSRF-002',
            'payment_check_url': 'https://ranty.io.atacante.example.com/payments/pay-x',
        })

        self.assertNotIn('atacante', mock_get.call_args[0][0])

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_16_webhook_check_url_from_nave_is_used(self, mock_get):
        """La URL legítima de Nave sí se usa, y se normaliza a https.

        Nave la documenta sin esquema; es además la que destrabó el checkout, porque el host que
        construimos localmente no siempre es el que corresponde.
        """
        mock_get.return_value = MagicMock(
            json=MagicMock(return_value={
                'id': 'pay-ok',
                'status': {'name': 'APPROVED', 'reason_code': 'transaction_successful'},
                'wallet': {'name': 'modo'},
            }),
            raise_for_status=MagicMock(return_value=None),
        )
        self._nave_arm_token()
        tx = self._nave_make_tx('TEST-NAVE-SSRF-003')

        tx._process_notification_data({
            'payment_id': 'pay-ok',
            'external_payment_id': 'TEST-NAVE-SSRF-003',
            'payment_check_url': 'api-sandbox.ranty.io/ranty-payments/payments/pay-ok',
        })

        self.assertEqual(
            mock_get.call_args[0][0],
            'https://api-sandbox.ranty.io/ranty-payments/payments/pay-ok',
        )
        self.assertEqual(tx.state, 'done')

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_17_webhook_check_url_drops_userinfo(self, mock_get):
        """Se descarta el userinfo de la URL, que sólo sirve para confundir al que lee el log."""
        mock_get.return_value = MagicMock(
            json=MagicMock(return_value={'id': 'pay-u', 'status': {'name': 'APPROVED'}}),
            raise_for_status=MagicMock(return_value=None),
        )
        self._nave_arm_token()
        tx = self._nave_make_tx('TEST-NAVE-SSRF-004')

        tx._process_notification_data({
            'payment_id': 'pay-u',
            'external_payment_id': 'TEST-NAVE-SSRF-004',
            'payment_check_url': 'https://atacante.example.com@api-sandbox.ranty.io/payments/pay-u',
        })

        self.assertEqual(
            mock_get.call_args[0][0],
            'https://api-sandbox.ranty.io/payments/pay-u',
        )
