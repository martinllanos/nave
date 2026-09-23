# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Set module_id on the Nave payment provider record.

    The provider record was originally created without module_id, and XML
    noupdate mechanisms don't reliably update it on existing records. This
    migration ensures the link is always established.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    provider = env['payment.provider'].search([('code', '=', 'nave')], limit=1)
    module = env['ir.module.module'].search([('name', '=', 'payment_nave')], limit=1)
    if provider and module and not provider.module_id:
        provider.module_id = module
