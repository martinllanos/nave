# -*- coding: utf-8 -*-
# [ADD] payment_nave: Tests del catálogo de motivos de rechazo y de baja de Nave.

from odoo.tests import tagged, TransactionCase

from odoo.addons.payment_nave.models.nave_reasons import (
    NAVE_INTENT_ERROR_MESSAGES,
    NAVE_REASON_MESSAGES,
    NAVE_REASONS_EXCLUDED,
    nave_intent_error,
    nave_reason_message,
)


@tagged('post_install', '-at_install', 'payment_nave')
class TestNaveReasons(TransactionCase):

    def test_01_un_codigo_conocido_devuelve_el_mensaje_de_nave(self):
        """El cajero lee el mensaje que publica Nave, no el código."""
        self.assertEqual(
            nave_reason_message(self.env, 'no_amount_available'),
            "La tarjeta no tiene fondos suficientes.",
        )
        self.assertEqual(
            nave_reason_message(self.env, 'manual_disabled_by_user'),
            "El pago fue cancelado por el usuario dentro de la terminal.",
        )

    def test_02_un_codigo_desconocido_no_devuelve_nada(self):
        """Sin mensaje publicado, el aviso describe la situación sin motivo: no se inventa uno."""
        self.assertEqual(nave_reason_message(self.env, 'payment retries limit reached'), '')
        self.assertEqual(nave_reason_message(self.env, 'codigo_que_no_existe'), '')
        self.assertEqual(nave_reason_message(self.env, ''), '')
        self.assertEqual(nave_reason_message(self.env, None), '')

    def test_03_un_codigo_excluido_no_devuelve_nada(self):
        """Los códigos con jerga interna de Nave no llegan a la explicación del aviso."""
        self.assertEqual(nave_reason_message(self.env, 'disabled_from_saas'), '')
        self.assertEqual(nave_reason_message(self.env, 'general_error'), '')

    def test_04_la_fila_que_agrupa_codigos_cubre_a_cada_uno(self):
        """Nave publica `invalid_merchant, system_error, gateway_timeout` en una sola fila."""
        mensajes = {
            nave_reason_message(self.env, code)
            for code in ('invalid_merchant', 'system_error', 'gateway_timeout')
        }
        self.assertEqual(mensajes, {"Error interno o con el proveedor de la tarjeta."})

    def test_05_un_codigo_no_esta_a_la_vez_en_el_catalogo_y_excluido(self):
        """Cada código documentado tiene una sola decisión: se muestra o se excluye."""
        self.assertFalse(set(NAVE_REASON_MESSAGES) & set(NAVE_REASONS_EXCLUDED))

    def test_06_los_espacios_alrededor_del_codigo_no_cambian_nada(self):
        self.assertEqual(
            nave_reason_message(self.env, ' cvv2_failure '),
            "El código de seguridad (CVV/CVC) ingresado es incorrecto.",
        )


@tagged('post_install', '-at_install', 'payment_nave')
class TestNaveIntentErrors(TransactionCase):
    """Errores al crear una intención: el mismo error en cualquiera de las formas de Nave."""

    def test_01_la_respuesta_real_de_invalid_pos(self):
        """Sondeada en producción el 2026-10-09, con QR y con Nave Point."""
        self.assertEqual(
            nave_intent_error({'code': 'invalid_pos', 'message': 'Given POS is for a different payment type'}),
            'invalid_pos',
        )

    def test_02_los_ejemplos_de_la_pagina_del_qr(self):
        """El HTTP viene en `code` y el error en `message`, en mayúsculas."""
        casos = {
            ('500', 'ERROR_ENCODE_DYNAMIC_QR'): 'error_encode_dynamic_qr',
            ('409', 'NO_GATEWAYS_AVAILABLE'): 'no_gateways_available',
            ('503', 'PAYMENT_TYPE_IS_NOT_OPERATIVE'): 'payment_type_is_not_operative',
            ('409', 'INVALID_POS'): 'invalid_pos',
            ('404', 'APPLICATION_ERROR_SERVICE'): 'application_error_service',
            ('404', 'CLIENT_VALIDATION_FAILED'): 'client_validation_failed',
            ('500', 'INTERNAL_SERVER_ERROR'): 'internal_server_error',
            ('500', 'INTERVAL_SERVER_ERROR'): 'internal_server_error',
        }
        for (http, message), clave in casos.items():
            with self.subTest(message=message):
                self.assertEqual(nave_intent_error({'code': http, 'message': message, 'detail': 'x'}), clave)

    def test_03_los_ejemplos_de_la_pagina_de_nave_point(self):
        self.assertEqual(
            nave_intent_error({'code': 'api_status_error', 'message': 'Payment type is not operational'}),
            'payment_type_is_not_operative',
        )
        self.assertEqual(nave_intent_error({'code': 'internal_server_error'}), 'internal_server_error')

    def test_04_lo_que_no_esta_en_el_catalogo(self):
        """Un código desconocido o un cuerpo sin código no dan clave: el aviso queda como hoy."""
        self.assertEqual(nave_intent_error({'code': 'algo_nuevo', 'message': 'x'}), '')
        self.assertEqual(nave_intent_error({}), '')
        self.assertEqual(nave_intent_error(None), '')
        self.assertEqual(nave_intent_error({'code': '409', 'detail': 'INVALID_POS'}), '',
                         "No se busca el código en `detail`")

    def test_05_cada_clave_tiene_mensaje(self):
        for clave in NAVE_INTENT_ERROR_MESSAGES:
            with self.subTest(clave=clave):
                self.assertTrue(str(NAVE_INTENT_ERROR_MESSAGES[clave]))
