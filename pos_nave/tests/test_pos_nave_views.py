# -*- coding: utf-8 -*-

from lxml import etree

from odoo.tests import tagged, TransactionCase


NAVE_REFERENCES = ('payment_ref_no', 'transaction_id')


@tagged('post_install', '-at_install', 'pos_nave')
class TestPosNaveViews(TransactionCase):
    """Los identificadores del cobro se ven en la orden y se buscan en la lista de pagos."""

    def _arch(self, model, view_type):
        return etree.fromstring(self.env[model].get_view(view_type=view_type)['arch'])

    def test_01_order_payments_show_the_references_read_only(self):
        arch = self._arch('pos.order', 'form')
        payments = arch.xpath("//field[@name='payment_ids']/list")
        self.assertEqual(len(payments), 1)
        for name in NAVE_REFERENCES:
            node = payments[0].xpath(f"field[@name='{name}']")
            self.assertEqual(len(node), 1, f"{name} falta en la lista de pagos de la orden")
            self.assertNotIn('optional', node[0].attrib)
            self.assertEqual(node[0].get('readonly'), '1')
        authcode = payments[0].xpath("field[@name='payment_method_authcode']")
        self.assertEqual(len(authcode), 1)
        self.assertEqual(authcode[0].get('optional'), 'hide')
        self.assertEqual(authcode[0].get('readonly'), '1')

    def test_02_payment_list_and_search_include_the_references(self):
        listing = self._arch('pos.payment', 'list')
        search = self._arch('pos.payment', 'search')
        for name in NAVE_REFERENCES:
            column = listing.xpath(f"//field[@name='{name}']")
            self.assertEqual(len(column), 1, f"{name} falta en la lista de pagos")
            self.assertEqual(column[0].get('optional'), 'show')
            self.assertEqual(len(search.xpath(f"//field[@name='{name}']")), 1,
                             f"{name} falta en el buscador de pagos")
