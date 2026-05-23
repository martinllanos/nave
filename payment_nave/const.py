# -*- coding: utf-8 -*-

# Currency codes supported by Nave (ISO 4217).
SUPPORTED_CURRENCIES = [
    'ARS',
]

# Default payment method codes to enable when Nave is activated.
DEFAULT_PAYMENT_METHOD_CODES = {
    'card',
    'naranja',
}

# Map Nave payment status names to Odoo transaction state handlers.
TRANSACTION_STATUS_MAPPING = {
    'pending': ('PENDING',),
    'done': ('APPROVED',),
    'canceled': ('REJECTED', 'CANCELLED', 'REFUNDED', 'PURCHASE_REVERSED'),
    'error': (),
}
