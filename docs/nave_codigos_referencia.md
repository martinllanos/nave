# Nave — Códigos de estado y de rechazo

Referencia extraída de la documentación para desarrolladores de Nave el **2026-10-07**.

| Página | URL |
|---|---|
| Nave Point | https://developer-portal-doc-mfe-website-mfe.ranty.io/nave/in-person-payments/nave-point |
| QR interoperable | https://developer-portal-doc-mfe-website-mfe.ranty.io/nave/in-person-payments/qr-interoperable |
| Checkout | https://developer-portal-doc-mfe-website-mfe.ranty.io/nave/online-payments/checkout |
| Link de pago | https://developer-portal-doc-mfe-website-mfe.ranty.io/nave/online-payments/payment-link |

El portal arma las tablas con JavaScript, así que no se leen con un navegador sin JS ni con un
lector de páginas. Se extrajeron de los paquetes `chunk-*.js` que sirve el propio portal: Nave
Point = `chunk-PIHPEHQF.js`, QR = `chunk-3SROTMK6.js`, Checkout = `chunk-QZNGFD4P.js`, Link =
`chunk-6DUH72HE.js`. Los nombres cambian con cada despliegue del portal. Si hay que actualizar
esta referencia, se buscan por el contenido (por ejemplo, `no_amount_available`).

Los textos son de Nave y se transcriben sin cambios, erratas incluidas (`PURCHARSE_REVERSED`,
`purcharser`, `parainiciar`).

## Dos objetos, dos vocabularios

Una **intención de pago** (`/api/payment_requests/{id}`) es el pedido de cobro. Un **pago**
(`/ranty-payments/payments/{id}`) es cada intento de pagar esa intención. Cada uno tiene su
propio estado y su propio motivo:

| | Estado | Motivo |
|---|---|---|
| Intención | `status.name` (tabla 1) | `reason.code` / `reason.description` cuando se da de baja (tabla 5) |
| Pago | `status.name` (tabla 2) | `status.reason_code` / `status.reason_name` (tablas 3 y 4) |

**El motivo de un rechazo está en el pago, no en la intención.** Nave Point lo dice textualmente:
*"El código de rechazo se informa en el campo `status.reason_code` de la respuesta del pago cuando
el estado es REJECTED."* La intención informa su propio desenlace. En la reprueba de C3, una
tarjeta sin fondos dejó la intención en `BLOCKED` con *"payment retries limit reached"*, que
corresponde a los "intentos excedidos" de la tabla 1, no al motivo del rechazo.

## 1. Estados de la intención de pago

| Estado | Descripción |
|---|---|
| `PENDING` | Solicitud creada, sin pagos asociados aún |
| `PROCESSED` | Solicitud con un pago iniciado |
| `DISABLED` | Intención desactivada antes de usarse |
| `SUCCESS_PROCESSED` | Pago aprobado |
| `FAILURE_PROCESSED` | Pago rechazado |
| `EXPIRED` | Intención vencida |
| `BLOCKED` | Intención bloqueada por fraude o intentos excedidos |

## 2. Estados del pago

Nave Point:

| Estado | Descripción |
|---|---|
| `PENDING` | Transacción iniciada, sin resultado final |
| `APPROVED` | Pago aprobado |
| `REJECTED` | Pago rechazado |
| `CANCELLED` | Cancelación manual antes del cierre de lote |
| `REFUNDED` | Devolución total emitida |
| `PURCHARSE_REVERSED` | Reservado antes de liquidarse |
| `CHARGEBACK_REVIEW` | Disputa en proceso por contracargo |
| `CHARGED_BACK` | Contracargo confirmado por la entidad emisora |

El link de pago agrega `PARTIALLY_CANCELLED` (*"Anulación parcial antes del cierre del lote"*) y
`PARTIALLY_REFUNDED` (*"Devolución parcial luego del cierre del lote"*), y escribe
`PURCHASE_REVERSED` sin la errata.

## 3. Motivos de rechazo de pagos con tarjeta

Tabla común a Nave Point, QR interoperable, Checkout y Link de pago:

| Código de error | Mensaje |
|---|---|
| `denied` | Error con el proveedor de la tarjeta. Inténtalo de nuevo. |
| `no_amount_available` | La tarjeta no tiene fondos suficientes. |
| `risky_payment` | El pago fue clasificado como riesgoso y declinado por prevención de fraude. |
| `cvv2_failure` | El código de seguridad (CVV/CVC) ingresado es incorrecto. |
| `fraud_identification` | La transacción fue identificada y bloqueada como fraude. |
| `account_identity_validation_error` | La información de la tarjeta no es válida. |
| `invalid_card_type` | El tipo de tarjeta no es válido o no es aceptado por este comercio (ej. débito en vez de crédito). |
| `fraud_suspected` | Transacción declinada por sospecha de actividad fraudulenta. |
| `restricted_card` | La tarjeta tiene restricciones para realizar este tipo de operación (ej. compras internacionales o por internet). |
| `interruption_at_emitter` | Problema técnico o interrupción de servicio en el sistema del banco emisor. |
| `invalid_or_nonexistent_account` | El número de cuenta o tarjeta ingresado es inválido o no existe. |
| `exchange_key_validation_failure` | Fallo en la validación de las claves de seguridad durante el intercambio de datos. |
| `expired_card_invalid_expiry_date` | La fecha de vencimiento no es válida. |
| `invalid_transaction` | La transacción es inválida para el estado actual de la tarjeta o cuenta. |
| `denied_card_expired` | Transacción denegada específicamente porque la tarjeta está vencida. |
| `security_violation` | Violación de las normas de seguridad durante el procesamiento de la transacción. |
| `blocked_by_cardholder` | La tarjeta ha sido bloqueada preventivamente por el titular. |
| `exceeds_amount_limit` | El monto de la transacción supera el límite permitido. |

Sólo en las páginas de cobros online:

| Código | Mensaje | Página |
|---|---|---|
| `denied_hold_card` | Tu banco rechazó la operación. | Checkout |
| `invalid_merchant`, `system_error`, `gateway_timeout` | Error interno o con el proveedor de la tarjeta. | Checkout |
| `gateway_not_available` | Error interno o con el proveedor. | Checkout |
| `gateway_not_available` | Hubo un error al intentar procesar el pago. Por favor, inténtalo nuevamente. | Link de pago |
| `check_the_system_transaction_not_allowed_to_that_card` | La tarjeta fue rechazada. Por favor, intentá pagar con otro medio o comunicate con el banco emisor. | Link de pago |
| `denied_hold_card` | Tu banco rechazó la operación. | Link de pago |
| `invalid_merchant`, `system_error`, `gateway_timeout` | Error interno o con el proveedor de la tarjeta. | Link de pago |

`gateway_not_available` tiene un texto distinto en cada página. Los mensajes de los cobros online
le hablan al comprador (*"Tu banco rechazó la operación."*); los de la tabla común son neutros.

## 4. Motivos de rechazo de pagos con dinero en cuenta (transferencia / DEBIN)

Igual en las cuatro páginas:

| Código de error | Descripción |
|---|---|
| `error_of_debit` | Transacción rechazada por falta de saldo disponible en la cuenta del pagador. |
| `alert_sent` | El banco emisor no responde a la notificación de débito del DEBIN. |
| `general_error` | Error notificado por COELSA. |
| `error_of_credit` | Error de comunicación entre el Banco Crédito y COELSA. |
| `error_of_communication_with_purcharser` | Nave no respondió a la solicitud de COELSA dentro del tiempo máximo de 3 segundos. |
| `error_operation_expired` | Operacion expirada en COELSA |
| `invalid_CBU_COELSA_account` | Validación interna de COELSA. |
| `error_validation_against_purcharser` | Falla comunicación COELSA contra Banco Crédito. |
| `account_insufficient_available` | Validaciones del Banco Débito. |
| `others_problems` | Validaciones del Banco Débito. |

## 5. Motivos de baja de una intención (Nave Point)

Se informan en `reason.code` y `reason.description`:

| Código | Razón |
|---|---|
| `low_battery` | La terminal objetivo no posee batería suficiente parainiciar el pago(menos de 5% de batería) |
| `manual_disabled_by_user` | El pago fue cancelado por el usuario dentro de la terminal |
| `disabled_by_user_timeout` | La terminal no pudo ser notificada y se deshabilitó automáticamente |
| `device_already_on_payment_flow` | La terminal no puede tomarla intención de pago dado que está en un proceso de pago |
| `disabled_from_saas` | Intención de pago deshabilitada desde el SAAS por motivo externo |
| `not_specified` | Sin especificar |

La misma página trae una versión más corta de esta tabla que omite `disabled_by_user_timeout` y
`not_specified`. Esta es la completa.

**Para dar de baja una intención (`DELETE /api/payment_requests/{id}`), la descripción no es libre.**
Verificado contra la API el 2026-10-07: Nave exige un texto fijo por código, en inglés y con esas
mayúsculas, y responde `400 {"code":"validation_exception","message":["Invalid input reason"]}`
con cualquier otro. La documentación no lo menciona.

| `reason.code` | `reason.description` aceptada |
|---|---|
| `disabled_from_saas` | `disabled from SAAS` |
| `manual_disabled_by_user` | `manual disabled by user` |
| `low_battery` | `low battery` |
| `device_already_on_payment_flow` | `device already on payment flow` |
| `disabled_by_user_timeout` | `disabled by user timeout` |

`not_specified` no fue aceptado con `not specified`. Un cuerpo vacío también pasa la validación.

**Esto contradice un supuesto del módulo.** El POS da por hecho que desde Odoo no se puede
distinguir una cancelación en la terminal de un vencimiento o de una falla de notificación, y Nave
informa justamente esa diferencia. Lo que no está verificado es si llega a Odoo: cuando la
intención está dada de baja, `GET /api/payment_requests/{id}` responde
`400 payment_request_is_disabled`, y falta ver si el cuerpo de esa respuesta, o la notificación de
la intención (`disabled_reason`, tabla 6), trae el `reason.code`.

## 6. Notificación (webhook)

Campos de la notificación de una **intención** en Nave Point:

| Atributo | Descripción | Tipo |
|---|---|---|
| `payment_request_id` | Identificación de la intención de pago en Nave | String |
| `status` | Estado en el cual está la intención de pago | String |
| `disabled_reason` | Motivo de baja de la intención (informado por SAAS o por el mismo sistema de Nave) | String |
| `payment_check_url` | Endpoint utilizado para consultar el estado de la intención de pago | String |
| `external_payment_id` | Identificador del pago en la plataforma (máximo 36 caracteres) | String |

Campos de la notificación de un **pago**:

| Atributo | Descripción | Tipo |
|---|---|---|
| `payment_id` | Identificador del pago en Nave | String |
| `payment_check_url` | Endpoint utilizado para consultar el estado del pago | String |
| `external_payment_id` | Identificador del pago en la plataforma (máximo 36 caracteres) | String |

Si la URL de notificación no responde OK, Nave reintenta:

| Intento | Frecuencia |
|---|---|
| `1` | 10 segundos |
| `2` | 70 segundos |
| `3` | 490 segundos |
| `4` | 3340 segundos |
| `5` | 24010 segundos |

Son cinco reintentos en unas 7,8 horas. Un webhook que Odoo responde con 500 —por ejemplo, el de
un cobro del POS, que `payment_nave` no encuentra entre sus `payment.transaction`— se reintenta
cinco veces y después se descarta.

## 7. Errores al cancelar un pago

| Error | Descripción |
|---|---|
| `payment_not_found` | Pago no encontrado |
| `only_approved_operations_can_be_canceled` | Solo pagos aprobados pueden cancelarse |
| `INTERVAL_SERVER_ERROR` | Servicio no disponible |

Respuestas exitosas: `CANCELLED` (*"El pago fue cancelado exitosamente."*) y `REFUNDED` (*"El pago
fue reembolsado exitosamente"*).

## 8. Cancelación y devolución de pagos

Agregado el 2026-10-07, de la misma documentación.

| | Endpoint |
|---|---|
| Producción | `POST https://api.ranty.io/integrations/payments/{id}/refunds` |
| Sandbox — Nave Point | `POST https://e3-api.ranty.io/integrations/payments/{id}/refunds` |
| Sandbox — Checkout, Link de pago, QR | `POST https://api-sandbox.ranty.io/integrations/payments/{id}/refunds` |

`{id}` es el identificador del **pago**, no el de la intención.

Un único endpoint para los dos casos. Nave lo resuelve según el estado de liquidación:

- **Cancelación**, dentro de las primeras 24 h y antes del cierre de lote: el pago queda `CANCELLED`.
- **Devolución**, pasadas las 24 h o con el lote cerrado: el pago queda `REFUNDED`.

*"El integrador no necesita invocar endpoints diferentes para cada caso."* Requiere que el pago esté
`APPROVED`. La respuesta trae el pago con su estado final.

Atributos del body:

| Atributo | Descripción | Tipo |
|---|---|---|
| `amount` | Monto de la compra a devolver (incluye moneda y valor). | Object |
| `tip_amount` | Monto de la propina a devolver (incluye moneda y valor). | Object |

El único ejemplo de body de la documentación lleva sólo `tip_amount`. No está documentado si una
devolución total se pide con el body vacío o con `amount`.

Errores:

| Código | Descripción |
|---|---|
| `INVALID_SCHEMA` | El body o los path params no cumplen el schema |
| `PROFILE_NOT_FOUND` | No existe un perfil de ejecución aplicable al pago |
| `PROFILE_INVALID_CONFIG` | El perfil aplicable tiene configuración incompleta |
| `REFUND_NOT_ENABLED` | El perfil no tiene habilitados los refunds |
| `PAYMENT_DOES_NOT_HAVE_A_TIP_AMOUNT` | Se solicitó devolución de propina pero no hay saldo de propina disponible |
| `TIP_AMOUNT_MUST_BE_GREATER_THAN_ZERO` | tip_amount debe ser mayor a 0 |
| `THE_TIP_AMOUNT_MUST_NOT_EXCEED_THE_AVAILABLE_TIP_VALUE` | El monto de propina supera el saldo disponible |
| `INVALID_PAYMENT_STATUS` | El pago no está en un estado que permita realizar el refund |
| `REFUND_PERIOD_EXPIRED` | El pago superó la ventana temporal permitida para realizar el refund |

**Diferencia con el módulo:** `payment_nave` y `pos_nave` piden la devolución con
`DELETE /api/payments/{payment_id}`, el endpoint de la documentación anterior (`tasks/doc_*.md`).
La documentación vigente no lo menciona, y en sandbox responde con un 403 de IAM (N12).
