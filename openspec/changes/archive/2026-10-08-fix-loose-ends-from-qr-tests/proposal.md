# Proposal

## Why

Las pruebas del 2026-10-08 dejaron cinco detalles menores (`tasks/plan_homologacion_nave.md` §3.38,
§3.39 y §3.40). Ninguno rompe un cobro, pero uno confunde al cajero, otro le hace pedidos de más a
Nave y tres engañan a quien lee el log o el código.

- **Con el QR fijo, la línea dice *"Esperando la tarjeta"*.** Es el texto del core para cualquier
  terminal. Con un QR confunde y, además, no le dice al cajero lo importante: el cliente tiene que
  escanear **después** de que aparezca el cobro. En H5, un escaneo anticipado hizo que la billetera
  pidiera el monto, y el pago quedó fuera de Odoo sin ningún aviso.
- **En los últimos 5 minutos de cada token, cada llamada pide uno nuevo.** Lo verificamos en
  producción: Nave devuelve el **mismo** token con su vida restante (84.249 s restantes →
  `expires_in: 84250`). El margen de 5 minutos lo da por vencido, pide otro y recibe el mismo. Entre
  las 19:10 y las 19:12 UTC hubo unos 25 pedidos.
- **El log del QR dice *"Enviando solicitud Smart POS a la terminal"*.** Para el QR fijo es falso.
- **El comentario de `close()` afirma que se llama al salir de la pantalla de pago.** El core de
  Odoo 18 nunca lo llama (C7, §3.38), y por eso un pago hecho mientras el cajero está en productos
  se registra igual.
- **Un JSON roto en el webhook se registra como error** (D2c). La falla es de quien lo manda, no de
  Odoo, y ensucia el log que acabamos de limpiar.

## What Changes

- **Con *Nave QR*, la línea en espera dice *"Esperando el escaneo del QR"*.** Las demás terminales
  siguen con el texto del core.
- **El token se reusa hasta poco antes de vencer**, con un margen que sólo cubre la demora de una
  llamada. Pasado ese punto, se pide uno nuevo.
- **El log del envío dice si el cobro va a la terminal o al QR.**
- **Se corrige el comentario de `close()`.**
- **El JSON roto en el webhook se registra como advertencia**, y sigue respondiendo 400.

## Capabilities

### New Capabilities

<!-- Ninguna. -->

### Modified Capabilities

- `nave-pos-collection`: se agrega que la línea en espera le dice al cajero qué espera el cobro,
  tarjeta o escaneo del QR.

El token, el log y el comentario no cambian ningún comportamiento descrito en las specs.

## Impact

- `pos_nave/static/src/app/`: una plantilla que extiende `point_of_sale.PaymentScreenPaymentLines`,
  y el comentario de `close()` en `payment_nave.js`.
- `pos_nave/models/pos_payment_method.py`: el texto del log del envío.
- `payment_nave/models/payment_provider.py`: el margen del token.
- `payment_nave/controllers/main.py`: el nivel del log del JSON roto.
- Pruebas: `payment_nave/tests/` y `pos_nave/tests/`.
- Versiones: `payment_nave` y `pos_nave`.
