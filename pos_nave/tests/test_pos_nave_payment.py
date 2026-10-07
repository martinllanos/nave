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


# Una tarjeta sin fondos, como en la reprueba de C3: la intención queda en BLOCKED por los intentos
# excedidos, y el motivo del rechazo de la tarjeta está en el pago.
INTENT_BLOCKED = {
    'id': 'intent-blk',
    'payment_type': 'smart_pos',
    'external_payment_id': 'POS-ORDER-BLK',
    'status': {'name': 'BLOCKED', 'reason_name': 'payment retries limit reached'},
    'payment_attempts': {
        'attempts': 1,
        'payments': [{'payment_id': 'pay-rej', 'status': 'REJECTED'}],
    },
}

PAYMENT_REJECTED = {
    'id': 'pay-rej',
    'status': {
        'name': 'REJECTED',
        'reason_code': 'no_amount_available',
        'reason_name': 'No amount available',
    },
    'payment_method': {},
    'transactions': [],
}

POS_LOGGER = 'odoo.addons.pos_nave.models.pos_payment_method'


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
        self.assertEqual(res['nave_outcome'], 'approved')

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

    # ──────────────────────────────────────────────
    # 10. MENSAJES DE ERROR PARA EL CAJERO
    # ──────────────────────────────────────────────

    def _http_error(self, status_code, body, json_ok=True):
        import requests as _requests
        response = MagicMock(status_code=status_code, text=body)
        if json_ok:
            import json as _json
            response.json.return_value = _json.loads(body)
        else:
            response.json.side_effect = ValueError("no es JSON")
        return _requests.exceptions.HTTPError(response=response)

    def test_22_html_error_page_is_not_shown_to_the_cashier(self):
        """Un 502 devuelve una página HTML, no JSON. Volcársela al cajero no le sirve de nada."""
        html = '<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">' + 'x' * 400
        msg = self.pos_payment_method._nave_error_message(
            self._http_error(502, html, json_ok=False)
        )

        self.assertNotIn('DOCTYPE', msg)
        self.assertNotIn('<html', msg)
        self.assertIn('502', msg)
        self.assertIn('Nave no está respondiendo', msg)

    def test_23_json_error_keeps_the_reason_from_nave(self):
        """Cuando Nave explica el motivo, se muestra el motivo y no un texto genérico."""
        body = '{"message": "The payment request could not be deleted.", "detail": "smart_pos"}'
        msg = self.pos_payment_method._nave_error_message(self._http_error(400, body))

        self.assertIn('could not be deleted', msg)
        self.assertIn('smart_pos', msg)
        self.assertIn('400', msg)

    def test_24_hints_are_actionable_per_status(self):
        """Cada familia de error dice qué hacer, porque quien lo lee está cobrando."""
        method = self.pos_payment_method
        self.assertIn('credenciales', method._nave_http_hint(401))
        self.assertIn('configuración', method._nave_http_hint(404))
        self.assertIn('encendida', method._nave_http_hint(504))
        self.assertIn('Reintentá', method._nave_http_hint(503))

    def test_25_connection_error_without_response(self):
        """Un fallo de red no tiene respuesta HTTP: se usa el texto de la excepción."""
        import requests as _requests
        msg = self.pos_payment_method._nave_error_message(
            _requests.exceptions.ConnectionError("Connection refused")
        )
        self.assertIn('Connection refused', msg)

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.get')
    def test_26_disabled_intent_is_a_state_not_an_error(self, mock_get):
        """Una intención dada de baja cierra el cobro, no rompe la consulta.

        Nave responde 400 `payment_request_is_disabled` cuando la dio de baja, por ejemplo porque
        no pudo notificar a la terminal. Tratarlo como fallo técnico dejaría al cajero con un
        error críptico en vez de "el cobro fue dado de baja".
        """
        mock_get.side_effect = self._http_error(
            400, '{"code": "payment_request_is_disabled", "message": "Payment request is disabled"}'
        )

        res = self.pos_payment_method.nave_check_payment_status(
            self.pos_payment_method.id, intent_id='intent-off'
        )

        self.assertNotIn('error', res, "No es un error de consulta sino el desenlace del cobro")
        self.assertEqual(res['status']['name'], 'DISABLED')
        # Sin motivo: el único disponible sería el nombre del error HTTP, que el cajero terminaba
        # leyendo en pantalla como si fuera la explicación de lo que pasó.
        self.assertNotIn('reason_code', res['status'])
        self.assertNotIn('reason_name', res['status'])
        self.assertNotIn('nave_reason', res, "Sin motivo en el cuerpo, no se afirma ninguna causa")
        self.assertEqual(res['nave_outcome'], 'disabled')

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.get')
    def test_27_other_400s_are_still_errors(self, mock_get):
        """Sólo la baja se traduce a estado: el resto sigue siendo error."""
        mock_get.side_effect = self._http_error(
            400, '{"code": "not_found", "message": "Payment request not found"}'
        )

        res = self.pos_payment_method.nave_check_payment_status(
            self.pos_payment_method.id, intent_id='intent-x'
        )

        self.assertTrue(res.get('error'))
        self.assertIn('not found', res.get('message', ''))

    def test_28_error_code_extraction(self):
        """El código se lee del cuerpo, y una respuesta sin JSON no rompe nada."""
        method = self.pos_payment_method
        self.assertEqual(
            method._nave_error_code(self._http_error(400, '{"code": "invalid_pos"}')),
            'invalid_pos',
        )
        self.assertFalse(method._nave_error_code(self._http_error(502, '<html>', json_ok=False)))
        import requests as _requests
        self.assertFalse(method._nave_error_code(_requests.exceptions.ConnectionError("x")))

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.post')
    def test_29_intent_response_carries_its_duration(self, mock_post):
        """El punto de venta necesita el plazo para no dejar de esperar antes que Nave.

        Tenerlo repetido en el navegador hacía que un cambio desincronizara los dos en silencio, y
        el cajero terminaba recibiendo el aviso de "verificá la terminal" cuando lo único que había
        pasado era que la intención venció.
        """
        from odoo.addons.pos_nave.models.pos_payment_method import NAVE_INTENT_DURATION_SECONDS
        mock_post.return_value = _mock_response({'id': 'intent-dur', 'external_payment_id': 'POS-DUR'})

        res = self.pos_payment_method.nave_send_payment_intent(
            self.pos_payment_method.id, amount=100.0, reference='POS-DUR'
        )

        self.assertEqual(res['id'], 'intent-dur', "El identificador tiene que seguir llegando igual")
        self.assertEqual(res['nave_duration_seconds'], NAVE_INTENT_DURATION_SECONDS)
        self.assertEqual(
            mock_post.call_args[1]['json']['duration_time'], NAVE_INTENT_DURATION_SECONDS,
            "El plazo que se informa debe ser el mismo que se le pidió a Nave",
        )

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.get')
    def test_31_each_status_has_its_outcome(self, mock_get):
        """La clasificación decide si una venta queda cobrada, así que se prueba estado por estado.

        `BLOCKED` es un rechazo y no un bloqueo de seguridad: Nave lo define como "fraude o intentos
        excedidos", y una tarjeta sin fondos lo produce al agotar los intentos.
        """
        esperado = {
            'SUCCESS_PROCESSED': 'approved',
            'APPROVED': 'approved',
            'FAILURE_PROCESSED': 'rejected',
            'REJECTED': 'rejected',
            'BLOCKED': 'rejected',
            'DISABLED': 'disabled',
            'CANCELLED': 'disabled',
            'EXPIRED': 'expired',
            'PENDING': 'pending',
            'PROCESSED': 'pending',
            'PROCESSING': 'pending',
        }
        for status, outcome in esperado.items():
            with self.subTest(status=status):
                mock_get.side_effect = None
                mock_get.return_value = _mock_response({'id': 'intent-x', 'status': {'name': status}})
                res = self.pos_payment_method.nave_check_payment_status(
                    self.pos_payment_method.id, intent_id='intent-x'
                )
                self.assertEqual(res['nave_outcome'], outcome)

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.get')
    def test_31b_an_unknown_status_is_never_a_charge(self, mock_get):
        """Un estado que el módulo no conoce se trata como espera y queda registrado para agregarlo."""
        mock_get.return_value = _mock_response({'id': 'intent-raro', 'status': {'name': 'ALGO_NUEVO'}})

        with self.assertLogs(POS_LOGGER, level='WARNING') as logs:
            res = self.pos_payment_method.nave_check_payment_status(
                self.pos_payment_method.id, intent_id='intent-raro'
            )

        self.assertEqual(res['nave_outcome'], 'unknown')
        registro = next(line for line in logs.output if 'no contemplado' in line)
        self.assertIn('ALGO_NUEVO', registro)
        self.assertIn('intent-raro', registro)

    # ──────────────────────────────────────────────
    # MOTIVO DEL DESENLACE
    # ──────────────────────────────────────────────

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.get')
    def test_32_the_reason_comes_from_the_payment_not_the_intent(self, mock_get):
        """El motivo de un rechazo es el del pago.

        Es lo que mostró la reprueba de C3: el aviso leía el motivo de la intención y el cajero vio
        "payment retries limit reached" por una tarjeta sin fondos.
        """
        mock_get.side_effect = [_mock_response(INTENT_BLOCKED), _mock_response(PAYMENT_REJECTED)]

        res = self.pos_payment_method.nave_check_payment_status(
            self.pos_payment_method.id, intent_id='intent-blk'
        )

        self.assertEqual(res['nave_reason'], {
            'code': 'no_amount_available',
            'message': "La tarjeta no tiene fondos suficientes.",
            'source': 'payment',
        })

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.get')
    def test_33_without_payment_the_intent_reason_is_only_for_support(self, mock_get):
        """Sin pago, el código de la intención se informa, pero no se convierte en explicación."""
        import requests
        mock_get.side_effect = [
            _mock_response(INTENT_BLOCKED),
            requests.exceptions.RequestException("boom"),
        ]

        res = self.pos_payment_method.nave_check_payment_status(
            self.pos_payment_method.id, intent_id='intent-blk'
        )

        self.assertEqual(res['nave_reason']['code'], 'payment retries limit reached')
        self.assertEqual(res['nave_reason']['source'], 'intent')
        self.assertEqual(res['nave_reason']['message'], '',
                         "Un motivo que Nave no publica no se presenta como la causa")

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.get')
    def test_34_disabled_intent_uses_the_reason_if_nave_sends_it(self, mock_get):
        """Si el cuerpo del 400 trae el motivo de la baja, el cajero lo lee en palabras de Nave."""
        mock_get.side_effect = self._http_error(
            400,
            '{"code": "payment_request_is_disabled", "message": "Payment request is disabled", '
            '"reason": {"code": "manual_disabled_by_user", "description": "x"}}',
        )

        res = self.pos_payment_method.nave_check_payment_status(
            self.pos_payment_method.id, intent_id='intent-off'
        )

        self.assertEqual(res['status']['name'], 'DISABLED')
        self.assertEqual(res['nave_reason']['code'], 'manual_disabled_by_user')
        self.assertEqual(res['nave_reason']['message'],
                         "El pago fue cancelado por el usuario dentro de la terminal.")

    def test_35_disabled_reason_shapes(self):
        """Nave documenta el motivo de baja como `reason.code` y como `disabled_reason`."""
        method = self.pos_payment_method
        self.assertEqual(
            method._nave_disabled_reason_code({'reason': {'code': 'low_battery'}}), 'low_battery'
        )
        self.assertEqual(
            method._nave_disabled_reason_code({'disabled_reason': 'disabled_by_user_timeout'}),
            'disabled_by_user_timeout',
        )
        self.assertFalse(method._nave_disabled_reason_code({'code': 'payment_request_is_disabled'}))
        self.assertFalse(method._nave_disabled_reason_code({'reason': {}}))

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.get')
    def test_36_the_outcome_is_logged(self, mock_get):
        """El aviso se cierra y el rechazo no deja nada en Odoo: el log es el único rastro."""
        mock_get.side_effect = [_mock_response(INTENT_BLOCKED), _mock_response(PAYMENT_REJECTED)]

        with self.assertLogs(POS_LOGGER, level='INFO') as logs:
            self.pos_payment_method.nave_check_payment_status(
                self.pos_payment_method.id, intent_id='intent-blk'
            )

        registro = next(line for line in logs.output if 'terminado en' in line)
        for dato in ('POS-ORDER-BLK', 'BLOCKED', 'intent-blk', 'pay-rej', 'no_amount_available'):
            self.assertIn(dato, registro)

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.get')
    def test_37_a_pending_intent_is_not_logged_as_an_outcome(self, mock_get):
        """Se consulta cada 3 segundos: registrar cada consulta llenaría el log de ruido."""
        mock_get.return_value = _mock_response({'id': 'intent-1234', 'status': {'name': 'PENDING'}})

        with self.assertNoLogs(POS_LOGGER, level='INFO'):
            self.pos_payment_method.nave_check_payment_status(
                self.pos_payment_method.id, intent_id='intent-1234'
            )

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.get')
    def test_38_the_disabled_body_is_logged(self, mock_get):
        """Falta verificar si Nave informa el motivo de la baja en el 400. El log lo va a mostrar."""
        body = '{"code": "payment_request_is_disabled", "message": "Payment request is disabled"}'
        mock_get.side_effect = self._http_error(400, body)

        with self.assertLogs(POS_LOGGER, level='INFO') as logs:
            self.pos_payment_method.nave_check_payment_status(
                self.pos_payment_method.id, intent_id='intent-off'
            )

        self.assertTrue(any(body in line for line in logs.output))
        self.assertTrue(any('terminado en DISABLED' in line for line in logs.output))

    def test_39_the_device_help_points_at_its_row(self):
        """La ayuda lleva al comercio a la fila de su dispositivo en el archivo de Nave.

        Cada terminal y cada QR tiene su pos_id, y uno cruzado hace que Nave rechace el cobro sin
        decir cuál está mal.
        """
        ayuda = self.env['pos.payment.method']._fields['nave_terminal_id'].help or ''
        for marca in ('POS_ID-', 'Sistema de gestión', 'NAVE POINT', 'QR', 'número de serie'):
            self.assertIn(marca, ayuda)
