# -*- coding: utf-8 -*-
# [ADD] pos_nave: Tests funcionales del backend para los pagos POS con Nave.

import copy
from unittest.mock import patch, MagicMock

from odoo.tests import tagged, TransactionCase
from odoo.exceptions import ValidationError

# Respuesta realista de GET /api/payment_requests/{id} para una intención ya cobrada.
# Recortada de la documentación oficial de Nave (ver tasks/doc_actualizada_2026-09-22.md).
INTENT_SUCCESS = {
    'id': 'intent-1234',
    'payment_type': 'smart_pos',
    'status': {'name': 'SUCCESS_PROCESSED'},
    'external_payment_id': 'POS-ORDER-001',
    'payment_attempts': {
        'attempts': 1,
        'payments': [{'payment_id': 'pay-9999', 'status': 'APPROVED'}],
    },
}

# Respuesta realista de GET /ranty-payments/payments/{id}.
PAYMENT_APPROVED = {
    'id': 'pay-9999',
    'payment_code': 'K88530374',
    'payment_input': 'chip',
    'status': {'name': 'APPROVED', 'reason_code': 'transaction_successful'},
    'payment_method': {
        'card_brand': 'VISA',
        'card_type': 'DEBIT',
        'card_last4': '0011',
        'issuer': 'BANCO DE GALICIA Y BUENOS AIRES S.A.U.',
        'installment_plan': {'installments': 1},
    },
    'transactions': [{'auth_data': {'auth_id': '032745', 'ticket': {'number': '11', 'batch': '168'}}}],
}


def _mock_response(payload):
    """Respuesta simulada de `requests`.

    `json()` devuelve una copia en cada llamada: el código adjunta datos sobre el dict que recibe,
    y sin la copia mutaría las constantes compartidas entre tests.
    """
    return MagicMock(
        json=MagicMock(side_effect=lambda: copy.deepcopy(payload)),
        raise_for_status=MagicMock(return_value=None),
    )


PAYMENT_QR_APPROVED = {
    'id': 'pay-qr-1',
    'payment_code': 'A07135516',
    'payment_input': 'wallet',
    'payment_type': 'static_qr',
    'status': {'name': 'APPROVED', 'reason_code': 'transaction_successful'},
    'payment_method': {'type': 'transfer_payment', 'wallet_name': 'mercado pago'},
    'wallet': {'name': 'mercado pago'},
    'transactions': [{'auth_data': {'auth_id': 'O7L8GYKNXZ8YRZQ2MPRZ50'}}],
}


@tagged('post_install', '-at_install', 'pos_nave')
class TestPosNavePayment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company

        # 1. Crear el proveedor Nave en modo test
        cls.provider = cls.env['payment.provider'].create({
            'name': 'Nave Test Provider',
            'code': 'nave',
            'state': 'test',
            'company_id': cls.company.id,
            'nave_client_id': 'test_client_id',
            'nave_client_secret': 'test_client_secret',
            'nave_pos_id': 'pos-test-123',
            'nave_access_token': 'mocked_token',
            # Asignar vencimiento futuro para evitar llamada real a Auth0 en estos tests
            'nave_token_expiry': cls.env['payment.provider']._fields['nave_token_expiry'].from_string('2099-01-01 00:00:00'),
        })

        # 2. Configurar el método de pago del POS
        cls.pos_payment_method = cls.env['pos.payment.method'].create({
            'name': 'Terminal Nave',
            'use_payment_terminal': 'nave',
            'nave_terminal_id': 'TERM-001',
            'company_id': cls.company.id,
        })

    # ──────────────────────────────────────────────
    # 1. ENVÍO DE COBRO (INTENCIÓN DE PAGO)
    # ──────────────────────────────────────────────

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.post')
    def test_01_nave_send_payment_intent(self, mock_post):
        """Envío exitoso de un cobro a la terminal."""
        mock_post.return_value = _mock_response({'id': 'intent-1234', 'external_payment_id': 'POS-ORDER-001'})

        res = self.pos_payment_method.nave_send_payment_intent(
            self.pos_payment_method.id,
            amount=5000.0,
            reference='POS-ORDER-001'
        )

        self.assertEqual(res['id'], 'intent-1234')

        # Nave Point usa su propio host de sandbox, distinto del de checkout/link/QR.
        call_url = mock_post.call_args[0][0]
        self.assertEqual(call_url, 'https://e3-api.ranty.io/api/payment_request/smart_pos')

        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['transactions'][0]['amount']['value'], '5000.00')
        self.assertEqual(payload['seller']['pos_id'], 'TERM-001')

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.post')
    def test_02_nave_send_payment_intent_error(self, mock_post):
        """El envío falla por error de conexión o de API."""
        import requests
        mock_post.side_effect = requests.exceptions.RequestException("Timeout Error")

        res = self.pos_payment_method.nave_send_payment_intent(
            self.pos_payment_method.id,
            amount=1500.0,
            reference='POS-ORDER-002'
        )

        self.assertTrue(res.get('error'), "Debe retornar un error controlado")
        self.assertIn("Timeout Error", res.get('message', ''))

    # ──────────────────────────────────────────────
    # 2. CONSULTA DE ESTADO (POLLING)
    # ──────────────────────────────────────────────

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.get')
    def test_03_check_status_pending(self, mock_get):
        """Una intención sin pagos asociados se devuelve tal cual, sin datos de pago."""
        mock_get.return_value = _mock_response({'id': 'intent-1234', 'status': {'name': 'PENDING'}})

        res = self.pos_payment_method.nave_check_payment_status(
            self.pos_payment_method.id, intent_id='intent-1234'
        )

        self.assertEqual(res['status']['name'], 'PENDING')
        self.assertNotIn('nave_payment_id', res)
        self.assertEqual(
            mock_get.call_args[0][0],
            'https://e3-api.ranty.io/api/payment_requests/intent-1234',
        )

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.get')
    def test_04_check_status_success_attaches_payment(self, mock_get):
        """Al cobrarse, se adjunta el payment_id y el pago completo.

        El endpoint de intención devuelve SUCCESS_PROCESSED, no APPROVED: son dos vocabularios
        distintos. Y el payment_id vive en payment_attempts, no en el id de la intención.
        """
        mock_get.side_effect = [_mock_response(INTENT_SUCCESS), _mock_response(PAYMENT_APPROVED)]

        res = self.pos_payment_method.nave_check_payment_status(
            self.pos_payment_method.id, intent_id='intent-1234'
        )

        self.assertEqual(res['status']['name'], 'SUCCESS_PROCESSED')
        self.assertEqual(res['nave_payment_id'], 'pay-9999')
        self.assertEqual(res['nave_payment']['payment_method']['card_last4'], '0011')

        # El segundo GET va al recurso de pago, con el payment_id y no con el de la intención.
        self.assertEqual(
            mock_get.call_args_list[1][0][0],
            'https://e3-api.ranty.io/ranty-payments/payments/pay-9999',
        )

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.get')
    def test_05_check_status_survives_payment_fetch_failure(self, mock_get):
        """Si falla el GET del pago, la intención se devuelve igual: el cobro ya salió bien."""
        import requests
        mock_get.side_effect = [
            _mock_response(INTENT_SUCCESS),
            requests.exceptions.RequestException("boom"),
        ]

        res = self.pos_payment_method.nave_check_payment_status(
            self.pos_payment_method.id, intent_id='intent-1234'
        )

        self.assertEqual(res['status']['name'], 'SUCCESS_PROCESSED')
        self.assertEqual(res['nave_payment_id'], 'pay-9999')
        self.assertNotIn('nave_payment', res)

    def test_06_extract_payment_id(self):
        """El payment_id sale del último intento de payment_attempts."""
        method = self.pos_payment_method
        self.assertEqual(method._nave_extract_payment_id(INTENT_SUCCESS), 'pay-9999')
        self.assertFalse(method._nave_extract_payment_id({'id': 'x'}))
        self.assertFalse(method._nave_extract_payment_id({'payment_attempts': {'payments': []}}))
        self.assertFalse(method._nave_extract_payment_id(None))
        self.assertEqual(
            method._nave_extract_payment_id({
                'payment_attempts': {'payments': [{'payment_id': 'a'}, {'payment_id': 'b'}]},
            }),
            'b',
        )

    # ──────────────────────────────────────────────
    # 3. HOSTS POR TIPO DE PAGO
    # ──────────────────────────────────────────────

    def test_07_api_host_per_payment_type(self):
        """Nave Point tiene un host de sandbox propio; en producción todos comparten uno."""
        self.assertEqual(self.provider._nave_get_api_url('smart_pos'), 'https://e3-api.ranty.io')
        self.assertEqual(self.provider._nave_get_api_url('static_qr'), 'https://api-sandbox.ranty.io')
        self.assertEqual(self.provider._nave_get_api_url(), 'https://api-sandbox.ranty.io')

        self.provider.state = 'enabled'
        self.assertEqual(self.provider._nave_get_api_url('smart_pos'), 'https://api.ranty.io')
        self.assertEqual(self.provider._nave_get_api_url(), 'https://api.ranty.io')

    # ──────────────────────────────────────────────
    # 4. DEVOLUCIÓN
    # ──────────────────────────────────────────────

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.delete')
    def test_08_nave_refund_payment(self, mock_delete):
        """La devolución es un DELETE sobre el pago, sin monto: Nave sólo admite total."""
        mock_delete.return_value = _mock_response({'status': 'CANCELLING'})

        res = self.pos_payment_method.nave_refund_payment(
            self.pos_payment_method.id, transaction_id='pay-9999', amount=-5000.0
        )

        self.assertEqual(res.get('status'), 'CANCELLING')
        self.assertEqual(
            mock_delete.call_args[0][0],
            'https://e3-api.ranty.io/api/payments/pay-9999',
        )
        self.assertNotIn('json', mock_delete.call_args[1])

    # ──────────────────────────────────────────────
    # 5. CONFIGURACIÓN DEL POS ID
    # ──────────────────────────────────────────────

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.post')
    def test_09_pos_id_falls_back_to_provider(self, mock_post):
        """Sin terminal en el método de pago, se usa el nave_pos_id del proveedor."""
        mock_post.return_value = _mock_response({'id': 'intent-1234'})

        method = self.env['pos.payment.method'].create({
            'name': 'Terminal sin ID',
            'use_payment_terminal': 'nave',
            'company_id': self.company.id,
        })
        method.nave_send_payment_intent(method.id, 100.0, 'REF-1')

        self.assertEqual(mock_post.call_args[1]['json']['seller']['pos_id'], 'pos-test-123')

    def test_10_provider_requires_pos_id(self):
        """El `nave_pos_id` es obligatorio en el proveedor mientras no esté deshabilitado.

        De ahí que el fallback de `nave_send_payment_intent` nunca quede sin valor: la guarda
        `if not pos_id: raise UserError` es defensiva y no alcanzable por configuración.
        """
        with self.assertRaises(ValidationError):
            self.provider.nave_pos_id = False

    # ──────────────────────────────────────────────
    # 6. QR INTEROPERABLE
    # ──────────────────────────────────────────────

    def _make_qr_method(self):
        return self.env['pos.payment.method'].create({
            'name': 'QR Nave',
            'use_payment_terminal': 'nave_qr',
            'nave_terminal_id': 'QR-POS-001',
            'company_id': self.company.id,
        })

    def test_11_qr_payment_type_and_host(self):
        """El QR es otro tipo de pago, con su propio host de sandbox."""
        qr_method = self._make_qr_method()
        self.assertEqual(qr_method._nave_payment_type(), 'static_qr')
        self.assertEqual(self.pos_payment_method._nave_payment_type(), 'smart_pos')
        self.assertEqual(self.provider._nave_get_api_url('static_qr'), 'https://api-sandbox.ranty.io')

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.post')
    def test_12_qr_intent_uses_its_own_endpoint(self, mock_post):
        """El cobro por QR va a /static_qr y manda qr_amount, que Nave exige."""
        mock_post.return_value = _mock_response({'id': 'intent-qr-1'})
        qr_method = self._make_qr_method()

        qr_method.nave_send_payment_intent(qr_method.id, amount=999.0, reference='POS-QR-001')

        self.assertEqual(
            mock_post.call_args[0][0],
            'https://api-sandbox.ranty.io/api/payment_request/static_qr',
        )
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['transactions'][0]['qr_amount'], 'close')
        self.assertEqual(payload['transactions'][0]['amount']['value'], '999.00')
        self.assertEqual(payload['seller']['pos_id'], 'QR-POS-001')

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.post')
    def test_13_smart_pos_does_not_send_qr_amount(self, mock_post):
        """Nave Point no lleva qr_amount: es un campo propio del QR."""
        mock_post.return_value = _mock_response({'id': 'intent-1234'})

        self.pos_payment_method.nave_send_payment_intent(
            self.pos_payment_method.id, amount=100.0, reference='POS-001'
        )

        self.assertNotIn('qr_amount', mock_post.call_args[1]['json']['transactions'][0])

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.get')
    def test_14_qr_status_uses_its_own_host(self, mock_get):
        """El polling del QR y la consulta del pago también van a api-sandbox."""
        qr_intent = dict(INTENT_SUCCESS, payment_type='static_qr')
        mock_get.side_effect = [_mock_response(qr_intent), _mock_response(PAYMENT_QR_APPROVED)]
        qr_method = self._make_qr_method()

        res = qr_method.nave_check_payment_status(qr_method.id, intent_id='intent-qr-1')

        self.assertEqual(res['nave_payment_id'], 'pay-9999')
        self.assertEqual(res['nave_payment']['wallet']['name'], 'mercado pago')
        self.assertEqual(
            mock_get.call_args_list[0][0][0],
            'https://api-sandbox.ranty.io/api/payment_requests/intent-qr-1',
        )
        self.assertEqual(
            mock_get.call_args_list[1][0][0],
            'https://api-sandbox.ranty.io/ranty-payments/payments/pay-9999',
        )

    # ──────────────────────────────────────────────
    # 7. TIMEOUTS
    # ──────────────────────────────────────────────

    def test_15_timeouts_have_defaults_and_overrides(self):
        """Crear la intención espera más que las consultas de estado.

        Nave tiene que alcanzar la terminal física antes de responder, mientras que el polling
        corre cada 3 segundos y no puede quedarse esperando.
        """
        method = self.pos_payment_method
        self.assertEqual(method._nave_timeout('intent'), 30)
        self.assertEqual(method._nave_timeout('status'), 5)
        self.assertGreater(method._nave_timeout('intent'), method._nave_timeout('status'))

        self.env['ir.config_parameter'].sudo().set_param('pos_nave.timeout_intent', '45')
        self.assertEqual(method._nave_timeout('intent'), 45)

    def test_16_invalid_timeout_falls_back_to_default(self):
        """Un parámetro mal cargado no puede romper un cobro."""
        self.env['ir.config_parameter'].sudo().set_param('pos_nave.timeout_intent', 'treinta')
        self.assertEqual(self.pos_payment_method._nave_timeout('intent'), 30)

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.post')
    def test_17_intent_uses_the_configured_timeout(self, mock_post):
        """El timeout configurado llega efectivamente a la llamada."""
        mock_post.return_value = _mock_response({'id': 'intent-1234'})
        self.env['ir.config_parameter'].sudo().set_param('pos_nave.timeout_intent', '42')

        self.pos_payment_method.nave_send_payment_intent(
            self.pos_payment_method.id, amount=100.0, reference='POS-TO-1'
        )

        self.assertEqual(mock_post.call_args[1]['timeout'], 42)

    # ──────────────────────────────────────────────
    # 8. CANCELACIÓN DE INTENCIÓN
    # ──────────────────────────────────────────────

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.delete')
    def test_18_cancel_reports_nave_rejection(self, mock_delete):
        """Nave rechaza la baja de una intención de terminal y hay que decirlo.

        Su catálogo sólo admite dar de baja payment_link, dynamic_qr y static_qr, así que un
        smart_pos responde 400. Callarlo dejaría al cajero creyendo que canceló un cobro que sigue
        vivo hasta expirar.
        """
        import requests as _requests
        response = MagicMock(status_code=400)
        response.json.return_value = {
            'code': 'payment_request_delete_failed',
            'message': 'The payment request could not be deleted.',
        }
        mock_delete.side_effect = _requests.exceptions.HTTPError(response=response)

        res = self.pos_payment_method.nave_cancel_payment_intent(
            self.pos_payment_method.id, intent_id='intent-1234'
        )

        self.assertTrue(res.get('error'))
        self.assertIn('could not be deleted', res.get('message', ''))
        self.assertIn('400', res.get('message', ''))

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.delete')
    def test_19_cancel_success(self, mock_delete):
        """Una baja aceptada devuelve éxito y usa el endpoint de intenciones."""
        mock_delete.return_value = _mock_response({'message': 'Payment request deleted'})

        res = self.pos_payment_method.nave_cancel_payment_intent(
            self.pos_payment_method.id, intent_id='intent-1234'
        )

        self.assertTrue(res.get('success'))
        self.assertEqual(
            mock_delete.call_args[0][0],
            'https://e3-api.ranty.io/api/payment_requests/intent-1234',
        )

    # ──────────────────────────────────────────────
    # 9. COBRO INMEDIATO vs COBRO DIVIDIDO
    # ──────────────────────────────────────────────

    def test_20_fast_payments_defaults_to_on(self):
        """Por defecto el cobro se dispara al seleccionar el método, que es el comportamiento
        previo y el más rápido para una venta común."""
        self.assertTrue(self.pos_payment_method.nave_fast_payments)

    def test_21_fast_payments_is_configurable_and_reaches_the_pos(self):
        """Se puede desactivar por método de pago, y el campo baja al frontend.

        Sin que viaje en los datos del POS, el cliente JS no puede leerlo y el ajuste no tendría
        ningún efecto.
        """
        self.pos_payment_method.nave_fast_payments = False
        self.assertFalse(self.pos_payment_method.nave_fast_payments)

        fields_loaded = self.env['pos.payment.method']._load_pos_data_fields(False)
        self.assertIn('nave_fast_payments', fields_loaded)
        self.assertIn('nave_terminal_id', fields_loaded)
