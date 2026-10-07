# Design

## Context

Ver `proposal.md` — Why. Lo que condiciona el enfoque:

- `nave_cancel_payment_intent` hace `DELETE /api/payment_requests/{id}` con
  `{"reason": {"code": "disabled_from_saas", "description": "Cancelado desde Odoo POS"}}`.
- Lo que acepta Nave se averiguó sondeando sandbox con una intención inexistente: un motivo
  aceptado devuelve 404 (la intención no existe) y uno rechazado, 400. Aceptados:
  `disabled_from_saas` / `disabled from SAAS`, los otros cuatro pares de
  `docs/nave_codigos_referencia.md` §5, y el cuerpo vacío o ausente.
- El navegador ya trata bien los dos desenlaces: sin aviso si la baja se confirma, y con *"La
  terminal puede seguir cobrando"* y el mensaje de Nave si no.
- `_nave_error_body` y `_nave_error_payload` ya existen, de la consulta de estado.

## Goals / Non-Goals

**Goals:**

- Que cancelar desde Odoo dé de baja el cobro en la terminal.
- Que una cancelación fallida se pueda diagnosticar desde el log.

**Non-Goals:**

- Cambiar qué hace el punto de venta con el cobro al cancelar. Eso quedó resuelto en
  `survive-network-cuts-without-charging-twice`: el cobro en curso se resuelve una sola vez y la
  línea queda para reintentar.
- Saber de antemano en qué estados Nave acepta la baja, por ejemplo con el cliente ya operando en la
  terminal. Lo responden las pruebas B y C con la terminal, después de esta corrección.

## Decisions

### Se manda el motivo que corresponde, con su texto fijo

El cuerpo pasa a ser `{"reason": {"code": "disabled_from_saas", "description": "disabled from
SAAS"}}`. El par vive en una constante con la explicación de por qué el texto es fijo.

*Por qué el motivo y no el cuerpo vacío*: los dos pasan la validación. El motivo le dice a Nave que
la baja la pidió el sistema del comercio y no la terminal, que es la distinción que hace su catálogo.
La terminal o la soporte de Nave pueden mostrarlo.

### Si Nave rechaza el motivo, se reintenta sin motivo

Si la baja vuelve con `400` y el mensaje de Nave menciona `Invalid input reason`, se repite una vez
sin cuerpo.

*Por qué*: el texto fijo no está documentado, y Nave puede cambiarlo sin aviso. Si eso pasa, la
cancelación seguiría funcionando, sin motivo, en lugar de volver a fallar siempre. El reintento se
limita a ese rechazo puntual, para no repetir bajas que fallan por otra causa.

*Alternativa descartada — mandar siempre el cuerpo vacío*: funciona hoy, pero pierde el motivo, y
tampoco está documentado que Nave lo vaya a seguir aceptando.

### El error se registra con la respuesta de Nave

Cuando la baja falla, el log registra el código HTTP y el cuerpo de la respuesta, recortado a 500
caracteres como los demás.

## Risks / Trade-offs

- **[Riesgo] Nave cambia los textos y también deja de aceptar el cuerpo vacío** → La baja falla,
  queda registrada con la respuesta y el cajero recibe el aviso de que la terminal puede seguir
  cobrando. Es lo que pasa hoy.
- **[Trade-off] Una llamada extra cuando Nave rechaza el motivo** → Sólo en ese caso, y una sola vez.

## Migration Plan

Ninguna. Se despliega `pos_nave`; la cancelación no depende del navegador.
