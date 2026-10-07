# Proposal

## Why

Lo que el cajero lee cuando un cobro presencial no sale bien no le sirve para decidir qué hacer.
Verificado con la terminal física:

| Situación | Lo que lee hoy |
|---|---|
| Tarjeta sin fondos | *"Nave bloqueó la operación por motivos de seguridad. Contactá a Nave antes de reintentar."* |
| Intención vencida | *"El cobro fue dado de baja: `payment_request_is_disabled`"* |
| Cancelación en la terminal | el mismo mensaje |

**El del rechazo es el que más daño hace.** Nave devuelve el estado `BLOCKED` para un rechazo
corriente —confirmado con dos tarjetas sin fondos distintas— y el módulo lo interpreta como fraude,
siguiendo lo que sugiere el nombre. El cajero recibe una alarma de seguridad y la instrucción de
llamar al proveedor, con el cliente esperando, porque una tarjeta no tenía saldo.

La propia terminal, en la misma situación, dice: *"La tarjeta con la que se intentó pagar no tiene el
dinero necesario. Podés intentar pagar con otra."* Nave le explica al operador qué pasó y qué hacer;
nosotros lo convertimos en otra cosa.

**El segundo es un código que fabrica el propio módulo.** Al dar de baja una intención, consultarla
devuelve un error cuyo código el backend copia como si fuera un motivo de negocio, y el frontend lo
imprime literal. El cajero termina leyendo un identificador interno que no existe en ningún lado
salvo en nuestro código.

## What Changes

- **Un rechazo se lee como un rechazo.** Deja de presentarse como un bloqueo de seguridad.
- **El motivo sale del pago, no de la intención.** Nave informa el motivo del rechazo en el pago
  (`status.reason_code`); la intención informa su propio desenlace. Leer el de la intención le
  mostró al cajero *"payment retries limit reached"* por una tarjeta sin fondos.
- **El cajero lee el motivo en las palabras de Nave.** Nave publica el catálogo de motivos de
  rechazo y de baja, con un mensaje en castellano para cada código. El aviso usa ese mensaje y le
  suma qué hacer a continuación. Si el código no está en el catálogo, el aviso describe la
  situación sin motivo.
- **El código queda a mano para soporte.** Debajo del aviso, en un bloque rotulado *"Para
  soporte"*, van el código tal como lo informa Nave y los identificadores del cobro. Es lo que el
  cajero necesita si llama a la soporte de primer nivel.
- **El desenlace queda registrado.** El aviso desaparece cuando el cajero lo cierra, y un cobro
  rechazado no deja nada en Odoo. El servidor registra en el log el desenlace de cada cobro.

No cambia qué cobros se aceptan ni cómo se registran: sólo qué se le dice al cajero y qué queda
registrado.

## Capabilities

### New Capabilities

<!-- Ninguna. -->

### Modified Capabilities

- `nave-pos-collection`: hoy exige que el cajero reciba un aviso que distinga un vencimiento de una
  falta de respuesta del proveedor. Se amplía a todos los desenlaces de un cobro: el aviso describe
  la situación con el motivo que publica Nave, y los códigos van aparte, rotulados para soporte.

## Impact

- `payment_nave/models/nave_reasons.py` (nuevo) — el catálogo de motivos de Nave. Vive en
  `payment_nave` porque los cobros online reciben los mismos códigos, aunque este cambio no toca
  esos flujos.
- `pos_nave/models/pos_payment_method.py` — resolver el motivo desde el pago y registrar el
  desenlace; dejar de inyectar un motivo sintético al traducir el error de baja.
- `pos_nave/static/src/app/payment_nave.js` — la clasificación de estados y los avisos.
- Pruebas: `payment_nave/tests/` y `pos_nave/tests/`.

### Evidencia

El catálogo de Nave está transcripto en `docs/nave_codigos_referencia.md`, con la fecha y las URL
de origen.

La primera implementación de este cambio mostraba el motivo cuando "parecía una frase". La reprueba
de C3 con la versión desplegada mostró *"El pago fue rechazado: payment retries limit reached"*:
una frase en inglés técnico que, además, describe a la intención y no a la tarjeta. Las capturas
están en `docs/homologacion/evidencias/C3/reprueba_18.0.1.8.0/`.

Los tres casos están cerrados en la matriz con sus capturas en `docs/homologacion/evidencias/`, y
documentados en `tasks/plan_homologacion_nave.md` §3.28, §3.29 y §3.30. El rechazo se verificó dos
veces con tarjetas distintas para descartar que fuera una particularidad de una de ellas.

Conviene corregirlo antes de seguir con los casos del bloque C que faltan —C4, C7, C9 y C10—, porque
son pruebas manuales con la terminal y habría que repetirlas si el código cambia después.
