# -*- coding: utf-8 -*-
""" Catálogo de motivos que informa Nave cuando un pago se rechaza o una intención se da de baja.

Nave informa un código (`no_amount_available`, `manual_disabled_by_user`, …) y publica, para cada
uno, un mensaje en castellano. Los mensajes de acá son esos, transcriptos de la documentación para
desarrolladores el 2026-10-07; la transcripción completa, con las URL de origen, está en
`docs/nave_codigos_referencia.md`. Se corrigen las erratas, porque estos textos los lee un cajero.

Quedan afuera los códigos cuyo mensaje usa jerga interna de Nave, que no le dice nada a quien está
cobrando: con ellos el aviso dice qué pasó sin motivo, y el código igual queda visible para
soporte. Están en `NAVE_REASONS_EXCLUDED` con el motivo de la exclusión, para que agregar uno
nuevo sea una decisión y no un olvido.
"""

from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

# Rechazos de pagos con tarjeta. Tabla común a Nave Point, QR interoperable, Checkout y Link de
# pago, más los que sólo figuran en las páginas de cobros online.
NAVE_CARD_REJECTION_MESSAGES = {
    'denied': _lt("Error con el proveedor de la tarjeta. Inténtalo de nuevo."),
    'no_amount_available': _lt("La tarjeta no tiene fondos suficientes."),
    'risky_payment': _lt("El pago fue clasificado como riesgoso y declinado por prevención de fraude."),
    'cvv2_failure': _lt("El código de seguridad (CVV/CVC) ingresado es incorrecto."),
    'fraud_identification': _lt("La transacción fue identificada y bloqueada como fraude."),
    'account_identity_validation_error': _lt("La información de la tarjeta no es válida."),
    'invalid_card_type': _lt(
        "El tipo de tarjeta no es válido o no es aceptado por este comercio "
        "(ej. débito en vez de crédito)."
    ),
    'fraud_suspected': _lt("Transacción declinada por sospecha de actividad fraudulenta."),
    'restricted_card': _lt(
        "La tarjeta tiene restricciones para realizar este tipo de operación "
        "(ej. compras internacionales o por internet)."
    ),
    'interruption_at_emitter': _lt("Problema técnico o interrupción de servicio en el sistema del banco emisor."),
    'invalid_or_nonexistent_account': _lt("El número de cuenta o tarjeta ingresado es inválido o no existe."),
    'exchange_key_validation_failure': _lt(
        "Fallo en la validación de las claves de seguridad durante el intercambio de datos."
    ),
    'expired_card_invalid_expiry_date': _lt("La fecha de vencimiento no es válida."),
    'invalid_transaction': _lt("La transacción es inválida para el estado actual de la tarjeta o cuenta."),
    'denied_card_expired': _lt("Transacción denegada específicamente porque la tarjeta está vencida."),
    'security_violation': _lt("Violación de las normas de seguridad durante el procesamiento de la transacción."),
    'blocked_by_cardholder': _lt("La tarjeta ha sido bloqueada preventivamente por el titular."),
    'exceeds_amount_limit': _lt("El monto de la transacción supera el límite permitido."),
    # Sólo en las páginas de cobros online.
    'denied_hold_card': _lt("Tu banco rechazó la operación."),
    'check_the_system_transaction_not_allowed_to_that_card': _lt(
        "La tarjeta fue rechazada. Por favor, intentá pagar con otro medio o comunicate con el "
        "banco emisor."
    ),
    # Nave agrupa estos tres en una sola fila, con un único mensaje.
    'invalid_merchant': _lt("Error interno o con el proveedor de la tarjeta."),
    'system_error': _lt("Error interno o con el proveedor de la tarjeta."),
    'gateway_timeout': _lt("Error interno o con el proveedor de la tarjeta."),
    # Tiene un texto distinto en cada página. Se usa el de Checkout, que es neutro; el del link de
    # pago le habla al comprador.
    'gateway_not_available': _lt("Error interno o con el proveedor."),
}

# Rechazos de pagos con dinero en cuenta (transferencia / DEBIN). Es el único de esa tabla cuyo
# mensaje describe la situación; el resto está en NAVE_REASONS_EXCLUDED.
NAVE_ACCOUNT_REJECTION_MESSAGES = {
    'error_of_debit': _lt("Transacción rechazada por falta de saldo disponible en la cuenta del pagador."),
}

# Motivos de baja de una intención de cobro presencial.
NAVE_DISABLE_MESSAGES = {
    'manual_disabled_by_user': _lt("El pago fue cancelado por el usuario dentro de la terminal."),
    'disabled_by_user_timeout': _lt("La terminal no pudo ser notificada y se deshabilitó automáticamente."),
    'low_battery': _lt(
        "La terminal no tiene batería suficiente para iniciar el pago (menos de 5 % de batería)."
    ),
    'device_already_on_payment_flow': _lt(
        "La terminal no puede tomar la intención de pago porque está en otro proceso de pago."
    ),
}

# Códigos documentados que no se le muestran al cajero como explicación, con el motivo.
NAVE_REASONS_EXCLUDED = {
    'disabled_from_saas': "Habla de \"el SAAS\". Es además la baja que pide el propio Odoo al cancelar.",
    'not_specified': "\"Sin especificar\" no agrega nada a la descripción genérica.",
    'alert_sent': "Habla de la notificación de débito del DEBIN.",
    'general_error': "\"Error notificado por COELSA.\"",
    'error_of_credit': "Habla de la comunicación entre el Banco Crédito y COELSA.",
    'error_of_communication_with_purcharser': "Habla de los tiempos de respuesta entre Nave y COELSA.",
    'error_operation_expired': "\"Operacion expirada en COELSA\".",
    'invalid_CBU_COELSA_account': "\"Validación interna de COELSA.\"",
    'error_validation_against_purcharser': "Habla de la comunicación entre COELSA y el Banco Crédito.",
    'account_insufficient_available': "\"Validaciones del Banco Débito.\"",
    'others_problems': "\"Validaciones del Banco Débito.\"",
}

NAVE_REASON_MESSAGES = {
    **NAVE_CARD_REJECTION_MESSAGES,
    **NAVE_ACCOUNT_REJECTION_MESSAGES,
    **NAVE_DISABLE_MESSAGES,
}


def nave_reason_message(env, code):
    """ Mensaje que publica Nave para `code`, traducido al idioma de `env`, o '' si no lo hay.

    Devuelve '' tanto para un código desconocido como para uno excluido: en los dos casos el aviso
    tiene que describir la situación sin motivo, y el código se muestra aparte, para soporte.
    """
    message = NAVE_REASON_MESSAGES.get((code or '').strip())
    return env._(message) if message else ''
