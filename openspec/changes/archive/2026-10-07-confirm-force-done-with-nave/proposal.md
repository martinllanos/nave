# Proposal

## Why

En el punto de venta, un cajero puede dar por cobrada una venta que nadie pagó. Lo verificamos con
la terminal física en C9 (`tasks/plan_homologacion_nave.md` §3.32, evidencia en
`docs/homologacion/evidencias/C9/`).

Mientras la línea de pago dice *"Esperando la tarjeta"*, Odoo muestra el botón **Forzar
terminación**. Al tocarlo sin acercar ninguna tarjeta:

- la línea pasa a *"Pago exitoso"*, el restante a $0,00 y *Validar* se habilita;
- la terminal sigue esperando la tarjeta, así que el cliente todavía puede pagar;
- unos 3 minutos después, la terminal da de baja la intención por su propio tope y la línea vuelve
  a *"Volver a intentar"*.

Un cajero que valida en esa ventana cierra la venta y se imprime el ticket como pagado con Nave, sin
que Nave haya cobrado nada. Con la validación automática activa (`auto_validate_terminal_payment`),
la venta se cerraría en el acto. Hoy está desactivada en `POS 1`, pero es una opción que el
comercio puede activar cuando quiera. Desde que el módulo opera en producción, esto es riesgo
financiero y no sólo operativo.

El botón es del core de Odoo y está pensado para terminales locales que pierden la conexión: el
cajero vio la aprobación en el equipo y Odoo no se enteró. Marca la línea como cobrada sin
preguntarle nada al proveedor. Con Nave no hace falta que el cajero dé fe de lo que vio, porque el
estado del cobro siempre se puede consultar.

Conviene corregirlo antes de seguir con los casos que faltan del bloque C. Varios de ellos —C4,
C7, C8— terminan con el cajero buscando una salida, y *Forzar terminación* es la que tiene a mano.

## What Changes

- **En un cobro de Nave, *Forzar terminación* consulta a Nave antes de decidir.** El cobro queda
  como lo diga Nave, no como lo diga el botón:
  - si Nave confirma el cobro, queda cobrado, con los datos de la tarjeta, como un cobro normal;
  - si Nave lo rechazó, lo dio de baja o venció, el cajero recibe el aviso que corresponde y la
    línea queda reintentable;
  - si Nave todavía espera la tarjeta, no se da nada por cobrado y se le avisa al cajero que puede
    esperar o cancelar;
  - si todavía no se terminó de enviar el cobro a la terminal, tampoco.
- **Si Nave no responde, el cajero tiene que confirmarlo explícitamente.** Es el único caso en que
  el botón conserva su sentido original, y se le pregunta al cajero si vio la aprobación en la
  terminal o en el cupón antes de dar la venta por cobrada.
- **Un cobro dado por terminado no se reabre.** Una respuesta que llega tarde ya no puede devolver
  a reintentable una línea cobrada.

No cambia el resto del POS ni lo que hace el botón con otros medios de pago.

## Capabilities

### New Capabilities

<!-- Ninguna. -->

### Modified Capabilities

- `nave-pos-collection`: se agrega que el punto de venta no da por cobrado un cobro presencial que
  Nave no confirmó, ni siquiera cuando el cajero fuerza la terminación.

## Impact

- `pos_nave/static/src/app/` — intervenir *Forzar terminación* en la pantalla de pago sólo para las
  líneas de Nave, y que el cobro en curso termine según lo que responda Nave.
- `pos_nave/models/pos_payment_method.py` — informar el desenlace del cobro ya clasificado, para que
  la decisión que toma el botón se pueda probar con los tests del backend.
- Pruebas: `pos_nave/tests/`.
- Sin impacto en `payment_nave` ni en otros medios de pago del POS.
