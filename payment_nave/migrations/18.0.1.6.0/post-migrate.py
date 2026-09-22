# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Activate the Nave payment methods on providers that already exist.

    _activate_default_pms only runs when a provider is switched on, so a provider that was
    already in test or enabled before this version would keep its payment methods archived
    and show nothing at checkout.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    providers = env['payment.provider'].search([
        ('code', '=', 'nave'),
        ('state', '!=', 'disabled'),
    ])
    providers._activate_default_pms()
