# -*- coding: utf-8 -*-
# Respuestas del webhook: qué se acusa, qué se reintenta y qué no se aplica a medias.
import json
import logging
from unittest.mock import patch, MagicMock

import requests

from odoo import Command
from odoo.tests import tagged
from odoo.addons.payment.tests.http_common import PaymentHttpCommon

CONTROLLER_LOGGER = 'odoo.addons.payment_nave.controllers.main'
REQUESTS_GET = 'odoo.addons.payment_nave.models.payment_transaction.requests.get'

PAGO_APROBADO = {
    'id': 'pay-wh-001',
    'status': {'name': 'APPROVED', 'reason_code': 'transaction_successful'},
    'payment_method': {
        'type': 'card_payment', 'card_brand': 'VISA', 'card_type': 'CREDIT', 'card_last4': '0231',
    },
}


@tagged('post_install', '-at_install', 'payment_nave')
class TestNaveWebhook(PaymentHttpCommon):

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
            'nave_access_token': 'tok_test',
            'nave_token_expiry': '2099-01-01 00:00:00',
            'payment_method_ids': [Command.set([cls.env.ref('payment_nave.payment_method_nave_qr').id])],
        })
        cls.tx = cls.env['payment.transaction'].create({
            'provider_id': cls.nave_provider.id,
            'payment_method_id': cls.payment_method_id,
            'amount': 1500.00,
            'currency_id': cls.env.ref('base.ARS').id,
            'reference': 'TEST-NAVE-WEBHOOK-001',
            'partner_id': cls.partner.id,
            'operation': 'online_redirect',
        })
        cls.tx._set_pending()

    def _post(self, reference, payment_id='pay-wh-001'):
        return self.url_open(
            '/payment/nave/webhook',
            data=json.dumps({'payment_id': payment_id, 'external_payment_id': reference}),
            headers={'Content-Type': 'application/json'},
        )

    @staticmethod
    def _respuesta(payment_data):
        return MagicMock(
            json=MagicMock(return_value=payment_data),
            raise_for_status=MagicMock(return_value=None),
        )

    def _errores(self, logs):
        return [r for r in logs.records if r.levelno >= logging.ERROR]

    def test_01_referencia_ajena_se_acusa_sin_error(self):
        """El aviso de un cobro del punto de venta se acusa con 200 y no se registra como error."""
        with self.assertLogs(CONTROLLER_LOGGER, level='INFO') as logs:
            response = self._post('d6e5b758-7c0f-4c13-9051-3e8efc20f932')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(self._errores(logs), "Un aviso ajeno no es un error")
        self.assertTrue(
            any('no corresponde a ninguna transacción del sitio' in r.getMessage() for r in logs.records)
        )
        self.tx.invalidate_recordset()
        self.assertEqual(self.tx.state, 'pending', "Ninguna transacción del sitio cambia")

    @patch(REQUESTS_GET)
    def test_02_consulta_fallida_responde_500_y_no_cierra(self, mock_get):
        """Si Nave no responde la consulta del pago, se pide el reintento y la transacción sigue igual."""
        mock_get.side_effect = requests.exceptions.ConnectionError("sin red")

        response = self._post(self.tx.reference)

        self.assertEqual(response.status_code, 500)
        self.tx.invalidate_recordset()
        self.assertEqual(self.tx.state, 'pending')

    @patch(REQUESTS_GET)
    def test_03_falla_a_mitad_descarta_lo_escrito(self, mock_get):
        """Una falla después de empezar a escribir responde 500 y no deja nada aplicado."""
        mock_get.return_value = self._respuesta(PAGO_APROBADO)

        with patch.object(type(self.tx), '_set_done', side_effect=RuntimeError("falla del sitio")):
            response = self._post(self.tx.reference)

        self.assertEqual(response.status_code, 500)
        self.tx.invalidate_recordset()
        self.assertEqual(self.tx.state, 'pending')
        self.assertFalse(self.tx.nave_card_brand, "Los datos del pago escritos antes de la falla se descartan")

    @patch(REQUESTS_GET)
    def test_04_aviso_aprobado_concilia(self, mock_get):
        """El camino normal no cambia: 200 y la transacción pagada."""
        mock_get.return_value = self._respuesta(PAGO_APROBADO)

        response = self._post(self.tx.reference)

        self.assertEqual(response.status_code, 200)
        self.tx.invalidate_recordset()
        self.assertEqual(self.tx.state, 'done')
        self.assertEqual(self.tx.nave_card_brand, 'VISA')
