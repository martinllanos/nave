# Design

## Context

- `nave_send_payment_intent` atrapa el `RequestException` del `POST` y devuelve
  `{'error': True, 'message': self._nave_error_message(e)}`. El JS lo muestra tal cual, con
  `_showError(data.message, "Error al solicitar cobro")`, y el diálogo respeta los saltos de línea
  (los avisos de desenlace ya traen un bloque *"Para soporte"*).
- `_nave_error_message` toma `message`, `error` o `description` del cuerpo, con `detail` si lo hay. Si
  no hay JSON, usa `_nave_http_hint` por código HTTP. Lo usan también la consulta, la baja y la
  devolución.
- `payment_nave/models/nave_reasons.py` tiene los catálogos de motivos de rechazo y de baja, con
  `_lt`, y `nave_reason_message(env, code)`.
- `payment.provider._nave_log_invalid_pos(exc, payment_type, pos_id)` reconoce `invalid_pos` en las
  dos formas y lo registra con el medio y el `pos_id`.

**Formatos de error de Nave:**

| Origen | Forma |
|---|---|
| Ejemplos de la página del QR | `{"code": "409", "message": "NO_GATEWAYS_AVAILABLE", "detail": "…"}` |
| Ejemplos de la página de Nave Point | `{"code": "api_status_error", "message": "Payment type is not operational"}` |
| Respuesta real, QR y Nave Point (sondeo del 2026-10-09) | `400 {"code": "invalid_pos", "message": "Given POS is for a different payment type"}` |

## Goals / Non-Goals

**Goals:** un aviso claro para cada error documentado al crear un cobro presencial, el mismo en
cualquiera de los dos formatos, y el registro del `invalid_pos`.

**Non-Goals:**

- Cambiar los avisos de la consulta, la baja o la devolución. Siguen usando `_nave_error_message`.
- Los cobros online (checkout y link de pago): el catálogo queda en `payment_nave` para que puedan
  usarlo, pero este cambio no los toca.
- Reintentar solo ante un error pasajero. El cajero decide.

## Decisions

### El código se normaliza a minúsculas desde `code` o desde `message`

La clave del catálogo sale de `code` si no es un número. Si `code` es un número, como en los ejemplos
del QR, sale de `message`. Se pasa a minúsculas y se resuelven los alias:

| Clave | Viene como |
|---|---|
| `invalid_pos` | `invalid_pos`, `INVALID_POS` |
| `payment_type_is_not_operative` | `api_status_error`, `PAYMENT_TYPE_IS_NOT_OPERATIVE` |
| `internal_server_error` | `internal_server_error`, `INTERNAL_SERVER_ERROR`, `INTERVAL_SERVER_ERROR` (errata de la tabla) |
| `error_encode_dynamic_qr`, `no_gateways_available`, `application_error_service`, `client_validation_failed` | su forma en mayúsculas |

Alternativa descartada: **buscar el código en todo el cuerpo**, como `_nave_log_invalid_pos`. Sirve
para detectar un solo código, pero con un catálogo un texto de `detail` podría coincidir con otra
clave.

### Los mensajes dicen qué hacer, según quién lo puede resolver

| Clave | Mensaje |
|---|---|
| `invalid_pos` | El ID del punto de venta de este método de pago pertenece a otro medio de cobro de Nave. Avisá al administrador para que lo corrija en el método de pago. |
| `error_encode_dynamic_qr` | Nave no pudo generar el QR. Reintentá en unos segundos. |
| `no_gateways_available` | Nave no tiene disponible ningún procesador para este medio de cobro. Cobrá por otro medio y, si se repite, avisá al administrador. |
| `payment_type_is_not_operative` | Este medio de cobro de Nave está fuera de servicio en este momento. Cobrá por otro medio. |
| `application_error_service` | Nave no reconoce las credenciales del comercio. Avisá al administrador. |
| `client_validation_failed` | Nave rechazó los datos del cobro. Avisá al administrador: el detalle quedó en el registro. |
| `internal_server_error` | Nave tuvo un error interno. Reintentá en unos segundos o cobrá por otro medio. |

Con un mensaje del catálogo, el aviso termina así:

```
<mensaje>

Para soporte:
Código: <código como lo mandó Nave>
HTTP: <status>
```

### El catálogo vive en `nave_reasons.py`, el mensaje se arma en `pos_nave`

- `nave_reasons.py` suma `NAVE_INTENT_ERROR_MESSAGES` y una función `nave_intent_error(payload)` que
  devuelve la clave normalizada, o `''`.
- `pos_nave` agrega `_nave_intent_error_message(exc)`: si la clave está en el catálogo, arma el aviso
  con el bloque de soporte; si no, devuelve `_nave_error_message(exc)` como hoy.

`nave_send_payment_intent` pasa a usar `_nave_intent_error_message`, y además llama a
`provider._nave_log_invalid_pos(e, payment_type, pos_id)` y registra el cuerpo de la respuesta, como
ya hace la baja.

Alternativa descartada: **cambiar `_nave_error_message`** para todos los usos. Afectaría la baja,
cuyo `400 Invalid input reason` tiene su propio manejo, y los avisos de devolución.

## Risks / Trade-offs

- **[Riesgo] Nave cambia el formato o el nombre de un código.** → El código no se reconoce y el aviso
  vuelve al comportamiento actual, que nunca queda vacío.
- **[Trade-off] Seis de los siete errores no se pueden provocar.** → Se prueban con las respuestas
  documentadas, en las dos formas. `invalid_pos`, el único que se puede provocar, se prueba en
  producción.

## Migration Plan

Subir `payment_nave` a `18.0.1.12.4` y `pos_nave` a `18.0.1.11.3`. Desplegar con el procedimiento de
siempre, actualizando los dos módulos, y verificar versiones y hashes en el contenedor. Sin cambios
de datos.
