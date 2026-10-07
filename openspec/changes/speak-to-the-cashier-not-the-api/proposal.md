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

- **Un rechazo se lee como un rechazo.** Deja de presentarse como un bloqueo de seguridad, y el
  cajero recibe la indicación de probar con otra tarjeta.
- **Los motivos que Nave informa en lenguaje llano se muestran; los códigos internos no.** Cuando lo
  único disponible es un identificador técnico, el cajero recibe una explicación de la situación en
  vez del código.
- **El aviso de baja no afirma una causa que no conocemos.** Una intención dada de baja puede venir
  de una cancelación, de un vencimiento o de que Nave no pudiera avisarle a la terminal, y desde
  Odoo son indistinguibles.

No cambia qué cobros se aceptan ni cómo se registran: sólo qué se le dice al cajero.

## Capabilities

### New Capabilities

<!-- Ninguna. -->

### Modified Capabilities

- `nave-pos-collection`: hoy exige que el cajero reciba un aviso que distinga un vencimiento de una
  falta de respuesta del proveedor. Se amplía a todos los desenlaces de un cobro, con la condición de
  que el aviso describa la situación en lugar de reproducir el vocabulario de la API.

## Impact

- `pos_nave/static/src/app/payment_nave.js` — la clasificación de estados y los mensajes.
- `pos_nave/models/pos_payment_method.py` — el motivo sintético que se inyecta al traducir el error.
- Pruebas: `pos_nave/tests/`.
- Sin impacto en `payment_nave` ni en los flujos online.

### Evidencia

Los tres casos están cerrados en la matriz con sus capturas en `docs/homologacion/evidencias/`, y
documentados en `tasks/plan_homologacion_nave.md` §3.28, §3.29 y §3.30. El rechazo se verificó dos
veces con tarjetas distintas para descartar que fuera una particularidad de una de ellas.

Conviene corregirlo antes de seguir con los casos del bloque C que faltan —C4, C7, C9 y C10—, porque
son pruebas manuales con la terminal y habría que repetirlas si el código cambia después.
