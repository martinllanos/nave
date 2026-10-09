# Proposal

## Why

Cuando Nave rechaza la creación de un cobro presencial, el cajero lee la respuesta cruda de Nave, en
inglés y sin indicación de qué hacer (`tasks/plan_homologacion_nave.md` §3.43, caso H8):

- *"Given POS is for a different payment type (HTTP 400)"* si el `pos_id` del método es de otro
  medio de cobro;
- *"ERROR_ENCODE_DYNAMIC_QR: Error-timeout of 2500ms exceeded (HTTP 500)"* si Nave no pudo generar
  el QR, según el ejemplo de la documentación.

Nave documenta siete errores al crear una intención con QR y tres con Nave Point, y en dos formatos
distintos. En producción, los dos endpoints respondieron igual a un `pos_id` equivocado:
`400 {"code":"invalid_pos", …}`, que es la forma de Nave Point y no la del ejemplo del QR. El POS
pasa lo que llegue a `_nave_error_message`, que arma el texto con el mensaje de Nave.

Además, en el POS un `invalid_pos` no queda registrado con el medio y el `pos_id`. Los cobros online
sí lo registran (`_nave_log_invalid_pos`), y sin esos datos el diagnóstico obliga a reproducir el
cobro.

Es lo mismo que resolvió *speak-to-the-cashier-not-the-api* para los desenlaces de un cobro: el aviso
tiene que decir qué pasó en términos del cajero, qué hacer, y dejar el código para soporte.

## What Changes

- **Un catálogo de errores al crear un cobro**, con un mensaje en castellano que dice qué pasó y qué
  hacer: reintentar, cobrar por otro medio o avisar al administrador.
- **El código se reconoce en los dos formatos de Nave**: en `code`, en minúsculas, o en `message`,
  en mayúsculas. Los alias documentados (`api_status_error` y `PAYMENT_TYPE_IS_NOT_OPERATIVE`) dan
  el mismo mensaje.
- **El aviso termina con un bloque *"Para soporte"*** que trae el código de Nave y el HTTP, como los
  avisos de desenlace.
- **Un `invalid_pos` queda registrado con el medio y el `pos_id`**, reusando lo que ya usan los cobros
  online.
- **Lo que no está en el catálogo sigue como hoy**: el mensaje de Nave, o la pista por código HTTP si
  Nave no explica nada.

## Capabilities

### New Capabilities

<!-- Ninguna. -->

### Modified Capabilities

- `nave-pos-collection`: se agrega que, si Nave no acepta crear el cobro, el cajero entiende por qué
  y qué hacer.

## Impact

- `payment_nave/models/nave_reasons.py`: el catálogo de errores al crear una intención y la función
  que normaliza su código. Va junto a los demás catálogos, porque los cobros online pueden recibir
  los mismos errores.
- `pos_nave/models/pos_payment_method.py`: el mensaje y el registro del error en
  `nave_send_payment_intent`.
- Pruebas: `pos_nave/tests/` y `payment_nave/tests/test_nave_reasons.py`.
- Sin cambios en el JS: el POS ya muestra el texto que devuelve el servidor.
- Versiones: `payment_nave` y `pos_nave`.
