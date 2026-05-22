# -*- coding: utf-8 -*-
# [ADD] pos_nave: Tests funcionales del backend para los pagos POS con Nave.

from unittest.mock import patch, MagicMock

from odoo.tests import tagged, TransactionCase
from odoo.exceptions import UserError


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
    # 1. TEST DE ENVÍO DE COBRO (INTENCIÓN DE PAGO)
    # ──────────────────────────────────────────────

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.post')
    def test_01_nave_send_payment_intent(self, mock_post):
        """Test: Envío exitoso de un cobro a la terminal."""
        mock_post.return_value = MagicMock(
            json=MagicMock(return_value={
                'id': 'intent-1234',
                'status': {'name': 'PENDING'},
            }),
            raise_for_status=MagicMock(return_value=None),
        )

        res = self.pos_payment_method.nave_send_payment_intent(
            self.pos_payment_method.id,
            amount=5000.0,
            reference='POS-ORDER-001'
        )

        self.assertIn('id', res, "La respuesta debe contener el ID de la intención de pago")
        self.assertEqual(res['id'], 'intent-1234')

        # Verificamos que se haya llamado a la URL correcta del entorno test
        call_url = mock_post.call_args[0][0]
        self.assertIn('e3-api.ranty.io/instore/payment_intents', call_url)

        # Verificamos que el payload tiene el monto formateado como string con 2 decimales
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['amount']['value'], '5000.00')

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.post')
    def test_02_nave_send_payment_intent_error(self, mock_post):
        """Test: Envío falla por error de conexión o API."""
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
    # 2. TEST DE CONSULTA DE ESTADO (POLLING)
    # ──────────────────────────────────────────────

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.get')
    def test_03_nave_check_payment_status(self, mock_get):
        """Test: Consulta de estado de un pago."""
        mock_get.return_value = MagicMock(
            json=MagicMock(return_value={
                'id': 'intent-1234',
                'status': {'name': 'APPROVED'},
            }),
            raise_for_status=MagicMock(return_value=None),
        )

        res = self.pos_payment_method.nave_check_payment_status(
            self.pos_payment_method.id,
            intent_id='intent-1234'
        )

        self.assertEqual(res.get('status', {}).get('name'), 'APPROVED')
        call_url = mock_get.call_args[0][0]
        self.assertTrue(call_url.endswith('/instore/payment_intents/intent-1234'))

    # ──────────────────────────────────────────────
    # 3. TEST DE REEMBOLSO (REFUND)
    # ──────────────────────────────────────────────

    @patch('odoo.addons.pos_nave.models.pos_payment_method.requests.post')
    def test_04_nave_refund_payment(self, mock_post):
        """Test: Envío exitoso de un reembolso a la terminal."""
        mock_post.return_value = MagicMock(
            json=MagicMock(return_value={
                'id': 'refund-5678',
                'status': {'name': 'APPROVED'},
            }),
            raise_for_status=MagicMock(return_value=None),
        )

        # Monto negativo (como llega de un reembolso en POS)
        res = self.pos_payment_method.nave_refund_payment(
            self.pos_payment_method.id,
            transaction_id='intent-1234',
            amount=-5000.0
        )

        self.assertEqual(res.get('id'), 'refund-5678')

        # Verificar que el payload mandó el monto en valor absoluto
        payload = mock_post.call_args[1]['json']
        self.assertEqual(payload['amount']['value'], '5000.00', "El monto de reembolso debe ser positivo en el payload")

    def test_05_missing_terminal_id(self):
        """Test: Validar que falla si el método de pago no tiene terminal_id configurado."""
        pos_method_no_terminal = self.env['pos.payment.method'].create({
            'name': 'Terminal Incompleta',
            'use_payment_terminal': 'nave',
            # Sin nave_terminal_id
            'company_id': self.company.id,
        })

        with self.assertRaises(UserError):
            pos_method_no_terminal.nave_send_payment_intent(pos_method_no_terminal.id, 100, 'REF-1')
