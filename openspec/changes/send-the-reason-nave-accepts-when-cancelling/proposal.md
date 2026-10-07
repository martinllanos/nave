# Proposal

## Why

Cancelar un cobro presencial desde Odoo nunca funcionó. Lo verificamos con la terminal en C4
(`tasks/plan_homologacion_nave.md` §3.36, evidencia en `docs/homologacion/evidencias/C4/`).

Al tocar *Cancelar* en Odoo con la terminal pidiendo la tarjeta, Nave respondió
`400 {"code":"validation_exception","message":["Invalid input reason"]}` y la terminal siguió
cobrando. El cajero vio *"La terminal puede seguir cobrando"*: Odoo había dejado de esperar el cobro,
pero el cliente todavía podía pagarlo.

La causa está en el motivo de baja que manda Odoo. Nave exige que la descripción sea un texto fijo
para cada código, comparado exacto y con mayúsculas: `disabled_from_saas` sólo pasa con
`disabled from SAAS`. Odoo manda el código correcto con una descripción libre, `"Cancelado desde
Odoo POS"`, así que Nave rechaza todas las cancelaciones. Lo sondeamos en sandbox con una intención
inexistente, porque Nave valida el motivo antes de buscar la intención. La documentación presenta la
descripción como texto libre y no lo aclara (`docs/nave_codigos_referencia.md` §5).

Además:

- **Cuando la cancelación falla, el log no dice por qué.** Registra la excepción, no la respuesta de
  Nave. El motivo se supo porque el aviso al cajero sí muestra el mensaje.
- **El código afirma que Nave no permite dar de baja una intención de terminal.** Lo dicen dos
  comentarios y el docstring de un test. Es falso, y quien leyera el código daría la cancelación por
  imposible.

## What Changes

- **La cancelación manda el motivo que Nave acepta:** `disabled_from_saas` con `disabled from SAAS`.
- **Si Nave rechaza el motivo, se reintenta la baja sin motivo**, que también acepta. Así la
  cancelación no depende de un texto que Nave puede cambiar sin documentarlo.
- **Una cancelación fallida queda registrada con la respuesta de Nave.**
- **Se corrigen los comentarios y el test que afirmaban que la baja era imposible.**

No cambia el resto de la cancelación: el cobro en curso se resuelve igual, la línea queda para
reintentar, y el cajero sólo recibe un aviso si Nave no confirma la baja.

## Capabilities

### New Capabilities

<!-- Ninguna. -->

### Modified Capabilities

- `nave-pos-collection`: se agrega que cancelar un cobro desde el punto de venta lo da de baja en la
  terminal, o avisa que no pudo. Hoy ningún requisito cubre la cancelación.

## Impact

- `pos_nave/models/pos_payment_method.py`: el cuerpo de la baja, el reintento sin motivo, el registro
  del error y un comentario.
- `pos_nave/static/src/app/payment_nave.js`: un comentario de `send_payment_cancel`.
- Pruebas: `pos_nave/tests/`.
- Sin impacto en `payment_nave`: es el único lugar que da de baja una intención.
