# -*- coding: utf-8 -*-
# [ADD] payment_nave: Tests funcionales para el proveedor de pago Nave.
# Cubre: autenticación (caché de token), creación de intención de pago,
# procesamiento de webhooks, reembolsos y el wizard de link de pago.

from datetime import timedelta
from unittest.mock import patch, MagicMock

import requests

from odoo import Command, fields
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

    # ──────────────────────────────────────────────
    # 7. ACTIVACIÓN DE MÉTODOS DE PAGO
    # ──────────────────────────────────────────────

    def test_18_provider_activates_its_payment_methods(self):
        """Habilitar el proveedor activa sus métodos de pago.

        Odoo archiva los métodos y sólo activa los que devuelve _get_default_payment_method_codes.
        Sin implementarlo, el proveedor quedaba habilitado y el checkout no ofrecía ninguno.
        """
        self.assertEqual(
            self.nave_provider._get_default_payment_method_codes(),
            {'card', 'naranja', 'nave_qr'},
        )

        self.nave_qr_method.active = False
        self.nave_provider.state = 'disabled'
        self.nave_provider.state = 'test'

        self.assertTrue(
            self.nave_qr_method.active,
            "Al habilitar el proveedor, su método de pago debe quedar activo",
        )

    # ──────────────────────────────────────────────
    # 8. CONCILIACIÓN DE RESPALDO (CRON)
    # ──────────────────────────────────────────────

    def _nave_make_stale_tx(self, reference, request_id, minutes_old=90):
        """Transacción pendiente y lo bastante vieja como para que el cron la tome."""
        tx = self._nave_make_tx(reference)
        tx.write({'nave_payment_request_id': request_id})
        tx._set_pending()
        old = fields.Datetime.now() - timedelta(minutes=minutes_old)
        self.env.cr.execute(
            "UPDATE payment_transaction SET create_date = %s WHERE id = %s", (old, tx.id)
        )
        tx.invalidate_recordset(['create_date'])
        return tx

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_19_cron_reconciles_lost_webhook(self, mock_get):
        """Si el webhook nunca llegó, el cron recupera el pago y concilia.

        Nave reintenta cinco veces durante unas 7h45m y después se rinde; sin esta red la
        transacción queda pendiente para siempre.
        """
        self._nave_arm_token()
        tx = self._nave_make_stale_tx('TEST-NAVE-CRON-001', 'pr-cron-001')

        mock_get.side_effect = [
            # 1) la intención, ya cobrada, con el payment_id adentro
            MagicMock(
                json=MagicMock(return_value={
                    'id': 'pr-cron-001',
                    'status': {'name': 'SUCCESS_PROCESSED'},
                    'payment_attempts': {'payments': [{'payment_id': 'pay-cron-001'}]},
                }),
                raise_for_status=MagicMock(return_value=None),
            ),
            # 2) la verificación del pago, el mismo camino que usa el webhook
            MagicMock(
                json=MagicMock(return_value={
                    'id': 'pay-cron-001',
                    'status': {'name': 'APPROVED', 'reason_code': 'transaction_successful'},
                    'wallet': {'name': 'modo'},
                }),
                raise_for_status=MagicMock(return_value=None),
            ),
        ]

        self.env['payment.transaction']._cron_nave_poll_pending_transactions()

        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.nave_payment_id, 'pay-cron-001')

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_20_cron_cancels_expired_intent(self, mock_get):
        """Una intención vencida deja de estar pendiente en vez de quedar colgada."""
        self._nave_arm_token()
        tx = self._nave_make_stale_tx('TEST-NAVE-CRON-002', 'pr-cron-002')

        mock_get.return_value = MagicMock(
            json=MagicMock(return_value={'id': 'pr-cron-002', 'status': {'name': 'EXPIRED'}}),
            raise_for_status=MagicMock(return_value=None),
        )

        self.env['payment.transaction']._cron_nave_poll_pending_transactions()

        self.assertEqual(tx.state, 'cancel')

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_21_cron_skips_recent_transactions(self, mock_get):
        """No se adelanta al webhook: las transacciones recientes se dejan en paz."""
        self._nave_arm_token()
        self._nave_make_stale_tx('TEST-NAVE-CRON-003', 'pr-cron-003', minutes_old=5)

        self.env['payment.transaction']._cron_nave_poll_pending_transactions()

        mock_get.assert_not_called()

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_22_cron_survives_a_failing_transaction(self, mock_get):
        """Una transacción que falla no se lleva puesto el resto del lote."""
        self._nave_arm_token()
        failing = self._nave_make_stale_tx('TEST-NAVE-CRON-004', 'pr-cron-004')
        healthy = self._nave_make_stale_tx('TEST-NAVE-CRON-005', 'pr-cron-005')

        # El cron no garantiza el orden en que toma las transacciones, así que se responde
        # según la URL consultada y no por posición.
        def _dispatch(url, **kwargs):
            if 'pr-cron-004' in url:
                raise requests.exceptions.RequestException("boom")
            if 'pr-cron-005' in url:
                return MagicMock(
                    json=MagicMock(return_value={
                        'id': 'pr-cron-005',
                        'status': {'name': 'SUCCESS_PROCESSED'},
                        'payment_attempts': {'payments': [{'payment_id': 'pay-cron-005'}]},
                    }),
                    raise_for_status=MagicMock(return_value=None),
                )
            return MagicMock(
                json=MagicMock(return_value={
                    'id': 'pay-cron-005',
                    'status': {'name': 'APPROVED', 'reason_code': 'transaction_successful'},
                }),
                raise_for_status=MagicMock(return_value=None),
            )

        mock_get.side_effect = _dispatch

        self.env['payment.transaction']._cron_nave_poll_pending_transactions()

        self.assertEqual(failing.state, 'pending', "La que falló queda como estaba")
        self.assertEqual(healthy.state, 'done', "La sana se concilia igual")

    # ──────────────────────────────────────────────
    # 9. CAMBIO DE AMBIENTE
    # ──────────────────────────────────────────────

    def _nave_has_cached_token(self):
        return bool(self.nave_provider.nave_access_token)

    def test_23_switching_environment_clears_the_token(self):
        """Pasar de Prueba a Producción invalida el token cacheado.

        El token dura hasta 24 h y no se revalida solo. Sin invalidarlo, el módulo seguiría
        mandando un token de sandbox a la API de producción y todas las llamadas darían 401.
        """
        self._nave_arm_token()
        self.assertTrue(self._nave_has_cached_token())

        self.nave_provider.state = 'enabled'

        self.assertFalse(self._nave_has_cached_token(),
                         "Al cambiar de ambiente el token viejo no puede sobrevivir")
        self.assertFalse(self.nave_provider.nave_token_expiry)

    def test_24_changing_credentials_clears_the_token(self):
        """Reemplazar las credenciales también invalida el token que emitieron las anteriores."""
        self._nave_arm_token()

        self.nave_provider.nave_client_id = 'otro_client_id'

        self.assertFalse(self._nave_has_cached_token())

    def test_25_unrelated_write_keeps_the_token(self):
        """Un cambio ajeno no descarta el token: sólo ambiente y credenciales lo invalidan."""
        self._nave_arm_token()

        self.nave_provider.name = 'Nave Test renombrado'

        self.assertTrue(self._nave_has_cached_token())

    # ──────────────────────────────────────────────
    # 10. POS ID POR MEDIO DE COBRO
    # ──────────────────────────────────────────────

    def test_29_pos_id_resolves_per_payment_type(self):
        """Cada medio de cobro tiene su propio identificador ante Nave."""
        self.nave_provider.nave_payment_link_pos_id = 'pos-link-999'

        self.assertEqual(
            self.nave_provider._nave_get_pos_id('payment_link'), 'pos-link-999',
            "El link de pago usa el identificador de su medio",
        )
        self.assertEqual(
            self.nave_provider._nave_get_pos_id('ecommerce'), 'pos-test-uuid-001',
            "El checkout sigue usando el de la tienda",
        )

    def test_30_pos_id_falls_back_to_the_store(self):
        """Sin identificador propio, el link usa el de la tienda.

        Es el estado de las instalaciones configuradas cuando el proveedor admitía uno solo, y el
        de los comercios a los que Nave entregó el mismo para ambos medios.
        """
        self.assertFalse(self.nave_provider.nave_payment_link_pos_id)

        self.assertEqual(
            self.nave_provider._nave_get_pos_id('payment_link'), 'pos-test-uuid-001')
        self.assertEqual(
            self.nave_provider._nave_get_pos_id('ecommerce'), 'pos-test-uuid-001')
        self.assertEqual(
            self.nave_provider._nave_get_pos_id(), 'pos-test-uuid-001',
            "Un medio no declarado también cae a la tienda",
        )

    @patch('odoo.addons.payment_nave.models.nave_link_wizard.requests.post')
    def test_31_link_wizard_sends_its_own_pos_id(self, mock_post):
        """El link viaja con el identificador del medio link de pago, no con el de la tienda."""
        mock_post.return_value = MagicMock(
            json=MagicMock(return_value={
                'id': 'pr-link-031',
                'checkout_url': 'https://checkout.ranty.io/link/pr-link-031',
            }),
            raise_for_status=MagicMock(return_value=None),
        )
        self._nave_arm_token()
        self.nave_provider.nave_payment_link_pos_id = 'pos-link-999'

        wizard = self.env['nave.payment.link.wizard'].create({
            'provider_id': self.nave_provider.id,
            'company_id': self.env.company.id,
            'partner_id': self.partner.id,
            'amount': 1000.00,
            'currency_id': self.currency_ars.id,
            'external_reference': 'INV-2026-0031',
        })
        wizard.action_generate_link()

        self.assertEqual(mock_post.call_args[1]['json']['seller']['pos_id'], 'pos-link-999')

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.post')
    def test_32_checkout_pos_id_follows_the_endpoint(self, mock_post):
        """Una factura pagada desde el portal va por el circuito de link, y su pos_id también.

        El checkout elige el endpoint `payment_link` cuando la transacción tiene factura. Si el
        pos_id se quedara en el de la tienda, Nave rechazaría ese pago con 409 INVALID_POS.
        """
        def _dispatch(url, **kwargs):
            return MagicMock(
                json=MagicMock(return_value={
                    'id': 'pr-032',
                    'checkout_url': 'https://checkout.ranty.io/032',
                }),
                raise_for_status=MagicMock(return_value=None),
            )
        mock_post.side_effect = _dispatch
        self._nave_arm_token()
        self.nave_provider.nave_payment_link_pos_id = 'pos-link-999'

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'currency_id': self.currency_ars.id,
            'invoice_line_ids': [Command.create({'name': 'Prueba', 'quantity': 1, 'price_unit': 500.0})],
        })
        tx = self.env['payment.transaction'].create({
            'provider_id': self.nave_provider.id,
            'payment_method_id': self.payment_method_id,
            'amount': 500.00,
            'currency_id': self.currency_ars.id,
            'reference': 'TEST-NAVE-PORTAL-032',
            'partner_id': self.partner.id,
            'operation': 'online_redirect',
            'invoice_ids': [Command.set([invoice.id])],
        })
        tx._get_specific_rendering_values({})

        called_url = mock_post.call_args[0][0]
        self.assertIn('/payment_request/payment_link', called_url)
        self.assertEqual(
            mock_post.call_args[1]['json']['seller']['pos_id'], 'pos-link-999',
            "El pos_id tiene que acompañar al endpoint elegido",
        )

    @patch('odoo.addons.payment_nave.models.nave_link_wizard.requests.post')
    def test_33_invalid_pos_is_logged_with_medium_and_id(self, mock_post):
        """Un rechazo por identidad deja registrado qué medio y qué identificador se usaron.

        Nave no dice cuál de los configurados está mal, así que sin esos dos datos diagnosticarlo
        obliga a reproducir el cobro.
        """
        # Cuerpo real capturado de la API el 2026-10-05, que difiere del ejemplo de la
        # documentación: 400 en vez de 409, y el código en minúsculas dentro de `code`.
        response = MagicMock(status_code=400)
        response.json.return_value = {
            'code': 'invalid_pos',
            'message': 'Given POS is for a different payment type',
        }
        mock_post.side_effect = requests.exceptions.HTTPError(response=response)
        self._nave_arm_token()
        self.nave_provider.nave_payment_link_pos_id = 'pos-link-cruzado'

        wizard = self.env['nave.payment.link.wizard'].create({
            'provider_id': self.nave_provider.id,
            'company_id': self.env.company.id,
            'partner_id': self.partner.id,
            'amount': 1000.00,
            'currency_id': self.currency_ars.id,
            'external_reference': 'INV-2026-0033',
        })

        from odoo.exceptions import UserError
        with self.assertLogs('odoo.addons.payment_nave.models.payment_provider', 'ERROR') as logs:
            with self.assertRaises(UserError):
                wizard.action_generate_link()

        registrado = "\n".join(logs.output)
        self.assertIn('payment_link', registrado)
        self.assertIn('pos-link-cruzado', registrado)

    def test_34_invalid_pos_is_recognised_in_both_shapes(self):
        """El rechazo se reconoce tanto en la forma real como en la del ejemplo de la doc."""
        provider = self.nave_provider
        import requests as _requests

        def _error(status, body):
            resp = MagicMock(status_code=status)
            resp.json.return_value = body
            return _requests.exceptions.HTTPError(response=resp)

        casos = [
            ("real", _error(400, {'code': 'invalid_pos', 'message': 'Given POS is for a different payment type'})),
            ("doc", _error(409, {'code': '409', 'message': 'INVALID_POS', 'detail': 'different payment type'})),
        ]
        for nombre, exc in casos:
            with self.assertLogs('odoo.addons.payment_nave.models.payment_provider', 'ERROR') as logs:
                provider._nave_log_invalid_pos(exc, 'payment_link', 'pos-x')
            self.assertIn('pos-x', "\n".join(logs.output), f"forma {nombre} no reconocida")

        # Un error ajeno no debe registrarse como problema de identidad.
        otro = _error(400, {'code': 'not_found', 'message': 'Payment request not found'})
        provider._nave_log_invalid_pos(otro, 'payment_link', 'pos-x')

    # ──────────────────────────────────────────────
    # 11. VARIOS INTENTOS SOBRE LA MISMA INTENCIÓN
    # ──────────────────────────────────────────────

    def _nave_verificacion(self, status_name, reason_code='transaction_successful', payment_id='pay-x'):
        return MagicMock(
            json=MagicMock(return_value={
                'id': payment_id,
                'status': {'name': status_name, 'reason_code': reason_code},
            }),
            raise_for_status=MagicMock(return_value=None),
        )

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_35_approval_after_rejection_recovers_the_transaction(self, mock_get):
        """El cliente reintenta con otra tarjeta y el cobro prospera: hay que registrarlo.

        Una intención de Nave admite varios intentos. Descartar la aprobación posterior deja dinero
        cobrado sin registrar, que es lo que ocurrió con el pedido S00005.
        """
        self._nave_arm_token()
        tx = self._nave_make_tx('TEST-NAVE-RETRY-001')

        # Primer intento: rechazado.
        mock_get.return_value = self._nave_verificacion('REJECTED', 'no_amount_available', 'pay-rechazado')
        tx._process_notification_data({
            'payment_id': 'pay-rechazado', 'external_payment_id': 'TEST-NAVE-RETRY-001',
        })
        self.assertEqual(tx.state, 'cancel')

        # Segundo intento sobre la misma intención: aprobado.
        mock_get.return_value = self._nave_verificacion('APPROVED', payment_id='pay-aprobado')
        tx._process_notification_data({
            'payment_id': 'pay-aprobado', 'external_payment_id': 'TEST-NAVE-RETRY-001',
        })

        self.assertEqual(tx.state, 'done', "La aprobación posterior debe recuperar la transacción")
        self.assertEqual(tx.nave_payment_id, 'pay-aprobado',
                         "Debe quedar asociada al pago aprobado, no al rechazado")

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_36_recovery_is_visible_in_the_document(self, mock_get):
        """Un cobro recuperado se distingue de uno directo: la diferencia le importa a quien concilia."""
        self._nave_arm_token()

        directo = self._nave_make_tx('TEST-NAVE-RETRY-002')
        mock_get.return_value = self._nave_verificacion('APPROVED', payment_id='pay-directo')
        directo._process_notification_data({
            'payment_id': 'pay-directo', 'external_payment_id': 'TEST-NAVE-RETRY-002',
        })
        self.assertNotIn('rechazado', directo.state_message or '')

        recuperada = self._nave_make_tx('TEST-NAVE-RETRY-003')
        mock_get.return_value = self._nave_verificacion('REJECTED', 'denied', 'pay-r')
        recuperada._process_notification_data({
            'payment_id': 'pay-r', 'external_payment_id': 'TEST-NAVE-RETRY-003',
        })
        mock_get.return_value = self._nave_verificacion('APPROVED', payment_id='pay-ok')
        recuperada._process_notification_data({
            'payment_id': 'pay-ok', 'external_payment_id': 'TEST-NAVE-RETRY-003',
        })

        self.assertEqual(recuperada.state, 'done')
        self.assertIn('rechazado', recuperada.state_message,
                      "El mensaje debe decir que hubo un intento rechazado antes")

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_37_late_rejection_does_not_revert_a_paid_transaction(self, mock_get):
        """Los reintentos de Nave duran horas: un rechazo puede llegar después de una aprobación."""
        self._nave_arm_token()
        tx = self._nave_make_tx('TEST-NAVE-RETRY-004')

        mock_get.return_value = self._nave_verificacion('APPROVED', payment_id='pay-ok')
        tx._process_notification_data({
            'payment_id': 'pay-ok', 'external_payment_id': 'TEST-NAVE-RETRY-004',
        })
        self.assertEqual(tx.state, 'done')

        mock_get.return_value = self._nave_verificacion('REJECTED', 'denied', 'pay-viejo')
        with self.assertLogs('odoo.addons.payment_nave.models.payment_transaction', 'WARNING') as logs:
            tx._process_notification_data({
                'payment_id': 'pay-viejo', 'external_payment_id': 'TEST-NAVE-RETRY-004',
            })

        self.assertEqual(tx.state, 'done', "Un rechazo tardío no puede revertir un cobro")
        self.assertEqual(tx.nave_payment_id, 'pay-ok',
                         "Debe seguir apuntando al pago aprobado, no al rechazado tardío")
        registrado = "\n".join(logs.output)
        self.assertIn('TEST-NAVE-RETRY-004', registrado)
        self.assertIn('REJECTED', registrado)

    # ──────────────────────────────────────────────
    # 12. DATOS DEL COBRO
    # ──────────────────────────────────────────────

    # Payload real del pedido S00007, capturado del sandbox el 2026-10-05: $1.150 de venta pagados
    # en 3 cuotas con interés, con un total de $1.263,10 a cargo del cliente.
    PAGO_CUOTAS = {
        'id': 'pay-s00007',
        'payment_code': 'AYO870166980',
        'payment_input': 'manual_input',
        'status': {'name': 'APPROVED', 'reason_code': 'transaction_successful'},
        'payment_method': {
            'type': 'card_payment', 'card_brand': 'VISA', 'card_type': 'CREDIT',
            'card_last4': '0231', 'bin': '476122',
            'issuer': 'BANCO SANTANDER ARGENTINA S.A.',
            'installment_plan': {
                'name': 'CUOTA SIMPLE 3', 'installments': 3, 'has_interest': True,
                'interest_rate': '7.40', 'annual_nominal_rate': 63,
                'total_financial_cost': '9.83',
                'total_amount': {'value': '1263.10', 'currency': 'ARS'},
            },
        },
        'transactions': [{'auth_data': {
            'auth_id': '002999', 'ticket': {'number': '11', 'batch': '490'},
        }}],
    }

    PAGO_BILLETERA = {
        'id': 'pay-qr',
        'payment_code': 'A07135516',
        'payment_input': 'wallet',
        'status': {'name': 'APPROVED', 'reason_code': 'transaction_successful'},
        'payment_method': {'type': 'transfer_payment', 'wallet_name': 'mercado pago'},
        'wallet': {'name': 'mercado pago'},
        'transactions': [{'auth_data': {'auth_id': 'O7L8GYKNXZ8'}}],
    }

    def _nave_cobrar(self, reference, payload, mock_get):
        self._nave_arm_token()
        tx = self._nave_make_tx(reference)
        mock_get.return_value = MagicMock(
            json=MagicMock(return_value=payload),
            raise_for_status=MagicMock(return_value=None),
        )
        tx._process_notification_data({
            'payment_id': payload['id'], 'external_payment_id': reference,
        })
        return tx

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_38_card_details_are_kept(self, mock_get):
        """Lo que Nave informa del instrumento deja de perderse."""
        tx = self._nave_cobrar('TEST-NAVE-DET-001', self.PAGO_CUOTAS, mock_get)

        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.nave_card_brand, 'VISA')
        self.assertEqual(tx.nave_card_type, 'CREDIT')
        self.assertEqual(tx.nave_card_last4, '0231')
        self.assertEqual(tx.nave_card_issuer, 'BANCO SANTANDER ARGENTINA S.A.')
        self.assertEqual(tx.nave_payment_input, 'manual_input')

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_39_receipt_identifiers_are_kept(self, mock_get):
        """Cupón, autorización y lote son lo que se pide al reclamar una operación."""
        tx = self._nave_cobrar('TEST-NAVE-DET-002', self.PAGO_CUOTAS, mock_get)

        self.assertEqual(tx.nave_payment_code, 'AYO870166980')
        self.assertEqual(tx.nave_auth_code, '002999')
        self.assertEqual(tx.nave_batch, '490')

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_40_financing_is_kept_without_touching_the_sale(self, mock_get):
        """El cliente pagó más que el monto de la venta, y las dos cifras importan."""
        tx = self._nave_cobrar('TEST-NAVE-DET-003', self.PAGO_CUOTAS, mock_get)

        self.assertEqual(tx.nave_installments, 3)
        self.assertTrue(tx.nave_installment_has_interest)
        self.assertEqual(tx.nave_interest_rate, '7.40')
        self.assertEqual(tx.nave_annual_nominal_rate, '63')
        self.assertEqual(tx.nave_total_financial_cost, '9.83')
        self.assertAlmostEqual(tx.nave_customer_total, 1263.10, places=2)
        self.assertAlmostEqual(tx.amount, 1500.00, places=2,
                               msg="El monto de la venta no se toca: es lo que factura el comercio")

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_41_wallet_payment_leaves_card_fields_empty(self, mock_get):
        """Un cobro por billetera no debe rellenar datos de tarjeta con valores inventados."""
        tx = self._nave_cobrar('TEST-NAVE-DET-004', self.PAGO_BILLETERA, mock_get)

        self.assertEqual(tx.nave_wallet_name, 'mercado pago')
        self.assertFalse(tx.nave_card_brand)
        self.assertFalse(tx.nave_card_last4)
        self.assertEqual(tx.nave_installments, 0)
        self.assertFalse(tx.nave_installment_has_interest)

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_42_summary_describes_the_medium_used(self, mock_get):
        """El resumen deja de afirmar 'Billetera: N/A' en un pago con tarjeta."""
        con_tarjeta = self._nave_cobrar('TEST-NAVE-DET-005', self.PAGO_CUOTAS, mock_get)
        self.assertIn('VISA', con_tarjeta.state_message)
        self.assertIn('0231', con_tarjeta.state_message)
        self.assertIn('3', con_tarjeta.state_message)
        self.assertNotIn('illetera', con_tarjeta.state_message)

        con_billetera = self._nave_cobrar('TEST-NAVE-DET-006', self.PAGO_BILLETERA, mock_get)
        self.assertIn('mercado pago', con_billetera.state_message)

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_43_known_brand_lands_on_the_payment_method(self, mock_get):
        """La marca va donde Odoo la muestra, no sólo a un campo del módulo."""
        marca_visa = self.env['payment.method'].with_context(active_test=False).search([
            ('name', '=ilike', 'visa'),
            ('primary_payment_method_id.code', '=', 'card'),
        ], limit=1)
        self.nave_provider.payment_method_ids = [Command.link(marca_visa.primary_payment_method_id.id)]

        tx = self._nave_cobrar('TEST-NAVE-DET-007', self.PAGO_CUOTAS, mock_get)

        self.assertEqual(tx.payment_method_id, marca_visa,
                         "El medio de pago de la transacción debe reflejar la marca usada")

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_44_unknown_brand_keeps_the_data(self, mock_get):
        """Una marca sin equivalente no puede hacer perder el dato ni romper el registro."""
        payload = dict(self.PAGO_CUOTAS)
        payload['payment_method'] = dict(self.PAGO_CUOTAS['payment_method'], card_brand='MARCA INEXISTENTE')
        metodo_previo = self.payment_method_id

        tx = self._nave_cobrar('TEST-NAVE-DET-008', payload, mock_get)

        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.nave_card_brand, 'MARCA INEXISTENTE')
        self.assertEqual(tx.payment_method_id.id, metodo_previo,
                         "Sin equivalente, el medio de pago queda como estaba")

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.get')
    def test_45_repeated_notification_does_not_warn(self, mock_get):
        """Nave reintenta cada webhook hasta cinco veces: el mismo desenlace llega varias veces.

        Advertir por eso llenaría el log de avisos que no requieren nada, y una advertencia que
        salta cuando no pasa nada termina haciendo que se ignoren las que sí importan.
        """
        import logging
        self._nave_arm_token()
        tx = self._nave_make_tx('TEST-NAVE-REPEAT-001')

        mock_get.return_value = self._nave_verificacion('APPROVED', payment_id='pay-ok')
        datos = {'payment_id': 'pay-ok', 'external_payment_id': 'TEST-NAVE-REPEAT-001'}
        tx._process_notification_data(datos)
        self.assertEqual(tx.state, 'done')

        logger = logging.getLogger('odoo.addons.payment_nave.models.payment_transaction')
        with self.assertNoLogs(logger, 'WARNING'):
            tx._process_notification_data(datos)

        self.assertEqual(tx.state, 'done')
        self.assertEqual(tx.nave_payment_id, 'pay-ok')

    # ──────────────────────────────────────────────
    # 9. EL DETALLE SE CORRESPONDE CON LO QUE SE COBRA
    # ──────────────────────────────────────────────

    def _nave_producto(self, nombre, precio, uom=None):
        valores = {'name': nombre, 'list_price': precio, 'type': 'consu'}
        if uom:
            valores.update({'uom_id': uom.id, 'uom_po_id': uom.id})
        return self.env['product.product'].create(valores)

    def _nave_pedido(self, lineas):
        """`lineas` es una lista de (producto, cantidad)."""
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                Command.create({'product_id': p.id, 'product_uom_qty': qty, 'price_unit': p.list_price})
                for p, qty in lineas
            ],
        })

    def _nave_tx_de(self, pedido):
        return self.env['payment.transaction'].create({
            'provider_id': self.nave_provider.id,
            'payment_method_id': self.nave_qr_method.id,
            'amount': pedido.amount_total,
            'currency_id': pedido.currency_id.id,
            'reference': f"TEST-DETALLE-{pedido.id}",
            'partner_id': self.partner.id,
            'operation': 'online_redirect',
            'sale_order_ids': [Command.set([pedido.id])],
        })

    def _nave_suma(self, detalle):
        return sum(float(d['unit_price']['value']) * d['quantity'] for d in detalle)

    def test_46_detalle_cantidad_entera_viaja_tal_cual(self):
        """Con cantidad entera se informa la cantidad: es lo que el cliente espera leer."""
        producto = self._nave_producto('Producto suelto', 500.0)
        pedido = self._nave_pedido([(producto, 3)])
        tx = self._nave_tx_de(pedido)

        detalle = tx._nave_get_products_payload()

        self.assertEqual(len(detalle), 1)
        self.assertEqual(detalle[0]['quantity'], 3)
        self.assertAlmostEqual(self._nave_suma(detalle), tx.amount, delta=0.03,
                               msg="El detalle debe sumar lo mismo que se cobra, impuestos incluidos")

    def test_47_detalle_cantidad_fraccionaria_cuadra_con_el_cobro(self):
        """0,15 kg a $800 el kilo se cobra $120: el detalle tiene que decir $120, no $800.

        Nave rechaza `quantity` fraccionario con un 502 y no valida que el detalle cuadre con el
        importe, así que truncar la cantidad hacía que el cliente leyera 1 × $800 mientras se le
        cobraban $120.
        """
        kg = self.env.ref('uom.product_uom_kgm')
        producto = self._nave_producto('Granel por kilo', 800.0, uom=kg)
        pedido = self._nave_pedido([(producto, 0.15)])
        tx = self._nave_tx_de(pedido)

        detalle = tx._nave_get_products_payload()

        self.assertEqual(detalle[0]['quantity'], 1)
        self.assertAlmostEqual(float(detalle[0]['unit_price']['value']), tx.amount, delta=0.01,
                               msg="El detalle debe sumar lo mismo que se cobra")
        self.assertIn('kg', detalle[0]['description'],
                      "La cantidad real tiene que sobrevivir en la descripción")

    def test_48_detalle_mezcla_de_cantidades_suma_el_total(self):
        """Con líneas enteras y fraccionarias mezcladas, el detalle sigue sumando el importe."""
        kg = self.env.ref('uom.product_uom_kgm')
        entero = self._nave_producto('Caja cerrada', 500.0)
        granel = self._nave_producto('Granel por kilo', 800.0, uom=kg)
        pedido = self._nave_pedido([(entero, 2), (granel, 0.25)])
        tx = self._nave_tx_de(pedido)

        detalle = tx._nave_get_products_payload()

        self.assertEqual(len(detalle), 2)
        self.assertAlmostEqual(self._nave_suma(detalle), tx.amount, delta=0.03)

    def test_49_detalle_redondea_el_subtotal_a_dos_decimales(self):
        """Un subtotal con más de dos decimales se informa con dos, que es lo que Nave admite."""
        kg = self.env.ref('uom.product_uom_kgm')
        producto = self._nave_producto('Granel con cola', 333.33, uom=kg)
        pedido = self._nave_pedido([(producto, 0.333)])

        detalle = self._nave_tx_de(pedido)._nave_get_products_payload()

        valor = detalle[0]['unit_price']['value']
        self.assertEqual(len(valor.split('.')[1]), 2, f"Se esperaban 2 decimales y llegó {valor}")

    def test_50_el_link_de_pago_arma_el_mismo_detalle_que_el_checkout(self):
        """El defecto estaba escrito en las cuatro ramas: el link no puede quedar con su copia."""
        kg = self.env.ref('uom.product_uom_kgm')
        producto = self._nave_producto('Granel por kilo', 800.0, uom=kg)
        pedido = self._nave_pedido([(producto, 0.15)])
        pedido.action_confirm()

        wizard = self.env['nave.payment.link.wizard'].create({
            'provider_id': self.nave_provider.id,
            'company_id': self.env.company.id,
            'partner_id': self.partner.id,
            'amount': pedido.amount_total,
            'currency_id': pedido.currency_id.id,
            'external_reference': f"SO-{pedido.id}",
            'sale_id': pedido.id,
        })

        por_link = wizard._nave_build_products_payload()
        por_checkout = self._nave_tx_de(pedido)._nave_get_products_payload()

        self.assertEqual(por_link[0]['quantity'], por_checkout[0]['quantity'])
        self.assertEqual(por_link[0]['unit_price']['value'], por_checkout[0]['unit_price']['value'])
        self.assertEqual(por_link[0]['quantity'], 1,
                         "La línea fraccionaria se informa como una unidad por el total")

    @patch('odoo.addons.payment_nave.models.nave_link_wizard.requests.post')
    def test_51_el_link_de_pago_dice_a_donde_volver(self, mock_post):
        """Sin `callback_url` el cliente que paga una factura queda en la pantalla de Nave.

        Es la URL que habilita el botón "Volver a la tienda" al aprobarse el pago, y el checkout ya
        la manda: el wizard era el único de los dos que no.
        """
        self._nave_arm_token()
        mock_post.return_value = MagicMock(
            json=MagicMock(return_value={
                'id': 'pr-callback-001',
                'checkout_url': 'https://checkout.ranty.io/link/pr-callback-001',
            }),
            raise_for_status=MagicMock(return_value=None),
        )

        wizard = self.env['nave.payment.link.wizard'].create({
            'provider_id': self.nave_provider.id,
            'company_id': self.env.company.id,
            'partner_id': self.partner.id,
            'amount': 1500.0,
            'currency_id': self.currency_ars.id,
            'external_reference': 'INV-CALLBACK-001',
        })
        wizard.action_generate_link()

        payload = mock_post.call_args.kwargs['json']
        self.assertIn('additional_info', payload,
                      "El payload del link debe llevar el bloque additional_info")
        self.assertTrue(payload['additional_info'].get('callback_url'),
                        "El link de pago debe decirle a Nave a dónde volver")
        self.assertTrue(payload['additional_info']['callback_url'].endswith('/payment/nave/return'),
                        "Debe ser la misma ruta de retorno que usa el checkout")

    def _nave_checkout_payload(self, mock_post, provider=None, amount=1000.0):
        """Dispara la creación de una intención y devuelve el payload que se le mandó a Nave."""
        proveedor = provider or self.nave_provider
        mock_post.return_value = MagicMock(
            json=MagicMock(return_value={
                'id': 'pr-duracion-001',
                'checkout_url': 'https://checkout.ranty.io/pr-duracion-001',
            }),
            raise_for_status=MagicMock(return_value=None),
        )
        tx = self.env['payment.transaction'].create({
            'provider_id': proveedor.id,
            'payment_method_id': self.nave_qr_method.id,
            'amount': amount,
            'currency_id': self.currency_ars.id,
            'reference': f"TEST-DURACION-{proveedor.id}-{amount}",
            'partner_id': self.partner.id,
            'operation': 'online_redirect',
        })
        tx._get_specific_rendering_values({})
        return mock_post.call_args.kwargs['json']

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.post')
    def test_52_el_plazo_del_checkout_por_omision_no_cambia(self, mock_post):
        """Quien no toque nada tiene que seguir teniendo los 50 minutos de siempre."""
        self._nave_arm_token()

        payload = self._nave_checkout_payload(mock_post)

        self.assertEqual(payload['duration_time'], 3000)

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.post')
    def test_53_el_plazo_del_checkout_es_configurable(self, mock_post):
        """El plazo era un número fijo en el código y ya hizo vencer intenciones."""
        self._nave_arm_token()
        self.nave_provider.nave_checkout_duration_minutes = 120

        payload = self._nave_checkout_payload(mock_post)

        self.assertEqual(payload['duration_time'], 7200)

    @patch('odoo.addons.payment_nave.models.payment_transaction.requests.post')
    def test_54_cada_compania_tiene_su_propio_plazo(self, mock_post):
        """El plazo vive en el proveedor justamente para no ser global."""
        self._nave_arm_token()
        self.nave_provider.nave_checkout_duration_minutes = 30

        otra_compania = self.env['res.company'].create({'name': 'Otra Compañía Nave'})
        otro_proveedor = self.env['payment.provider'].create({
            'name': 'Nave Otra',
            'code': 'nave',
            'state': 'test',
            'company_id': otra_compania.id,
            'nave_client_id': 'otro_client_id',
            'nave_client_secret': 'otro_secret',
            'nave_pos_id': 'pos-otra-001',
            'nave_checkout_duration_minutes': 90,
            'payment_method_ids': [Command.set([self.nave_qr_method.id])],
        })
        otro_proveedor.write({
            'nave_access_token': 'tok_test',
            'nave_token_expiry': self.env['payment.provider']._fields['nave_token_expiry'].from_string('2099-01-01 00:00:00'),
        })

        propia = self._nave_checkout_payload(mock_post, amount=1000.0)
        ajena = self._nave_checkout_payload(mock_post, provider=otro_proveedor, amount=2000.0)

        self.assertEqual(propia['duration_time'], 1800)
        self.assertEqual(ajena['duration_time'], 5400)

    # ──────────────────────────────────────────────
    # 10. LA REDIRECCIÓN LLEVA AL CLIENTE A SU INTENCIÓN
    # ──────────────────────────────────────────────

    def _nave_render_redirect(self, checkout_url):
        """Renderiza el formulario de redirección tal como lo hace el core de `payment`."""
        tx = self.env['payment.transaction'].create({
            'provider_id': self.nave_provider.id,
            'payment_method_id': self.nave_qr_method.id,
            'amount': 500.0,
            'currency_id': self.currency_ars.id,
            'reference': f"TEST-REDIR-{abs(hash(checkout_url)) % 10**8}",
            'partner_id': self.partner.id,
            'operation': 'online_redirect',
        })
        valores = tx._nave_redirect_values(checkout_url)
        vista = self.env.ref('payment_nave.redirect_form')
        return valores, self.env['ir.qweb']._render(vista.id, valores)

    def test_55_la_redireccion_conserva_la_intencion(self):
        """Un envío GET descarta el query string de la acción y lo reemplaza por los campos.

        Con el identificador sólo en la acción, el cliente llegaba a Nave sin su intención y veía
        una pantalla en blanco: el pedido quedaba esperando un pago que no se podía completar.
        """
        url = 'https://sandbox-hosted-checkout.ranty.io/nave?payment_request_id=f9d279b1-abc'

        valores, html = self._nave_render_redirect(url)

        self.assertEqual(valores['api_url'], 'https://sandbox-hosted-checkout.ranty.io/nave',
                         "La acción no debe depender del query string")
        self.assertIn('name="payment_request_id"', html,
                      "El identificador debe viajar como campo del formulario")
        self.assertIn('value="f9d279b1-abc"', html)

    def test_56_la_redireccion_conserva_todos_los_parametros(self):
        """Los parámetros los decide Nave y no están documentados: no se suponen."""
        url = 'https://sandbox-hosted-checkout.ranty.io/nave?payment_request_id=abc&lang=es&v=2'

        valores, html = self._nave_render_redirect(url)

        self.assertEqual(len(valores['nave_redirect_params']), 3)
        for nombre in ('payment_request_id', 'lang', 'v'):
            self.assertIn(f'name="{nombre}"', html, f"Falta el parámetro {nombre}")

    def test_57_la_redireccion_sin_parametros_no_rompe(self):
        """Si Nave devolviera una URL sin parámetros, se redirige tal cual."""
        url = 'https://sandbox-hosted-checkout.ranty.io/nave'

        valores, html = self._nave_render_redirect(url)

        self.assertEqual(valores['api_url'], url)
        self.assertEqual(valores['nave_redirect_params'], [])
        self.assertNotIn('type="hidden"', html)
