# -*- coding: utf-8 -*-
# [ADD] payment_nave: La ayuda de cada pos_id indica qué fila del archivo de Nave copiar.

from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install', 'payment_nave')
class TestNaveConfigHelp(TransactionCase):
    """Nave entrega los pos_id en POS_ID-<CUIT>.xlsx, una fila por medio de cobro.

    Un pos_id cargado en el campo equivocado hace que Nave rechace el cobro sin decir cuál de los
    campos está mal, así que la ayuda tiene que llevar al comercio a la fila correcta. Se comprueban
    las marcas que el comercio busca en el archivo, no la redacción completa.
    """

    def _help(self, field_name):
        return self.env['payment.provider']._fields[field_name].help or ''

    def test_01_la_tienda_online_lleva_a_la_fila_ecommerce(self):
        ayuda = self._help('nave_pos_id')
        for marca in ('POS_ID-', 'Sistema de gestión', 'ECOMMERCE', 'Tienda online propia'):
            self.assertIn(marca, ayuda)

    def test_02_el_link_de_pago_lleva_a_la_fila_ldp(self):
        ayuda = self._help('nave_payment_link_pos_id')
        for marca in ('POS_ID-', 'Sistema de gestión', 'LDP', 'invalid_pos'):
            self.assertIn(marca, ayuda)
        self.assertNotIn('409', ayuda, "Nave responde 400 invalid_pos, no 409")
