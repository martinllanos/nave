# -*- coding: utf-8 -*-
# [ADD] payment_nave: Tests del catálogo de motivos de rechazo y de baja de Nave.

from odoo.tests import tagged, TransactionCase

from odoo.addons.payment_nave.models.nave_reasons import (
    NAVE_REASON_MESSAGES,
    NAVE_REASONS_EXCLUDED,
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
