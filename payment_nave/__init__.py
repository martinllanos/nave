# -*- coding: utf-8 -*-

from . import models
from . import controllers
from odoo.addons.payment import setup_provider, reset_payment_provider


def post_init_hook(env):
    setup_provider(env, 'nave')
    # Force-set module_id on the provider record. The XML noupdate mechanism
    # does not reliably update this field on existing records, so we do it here.
    provider = env['payment.provider'].search([('code', '=', 'nave')], limit=1)
    module = env['ir.module.module'].search([('name', '=', 'payment_nave')], limit=1)
    if provider and module and not provider.module_id:
        provider.module_id = module


def uninstall_hook(env):
    reset_payment_provider(env, 'nave')
