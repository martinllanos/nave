# Proposal

## Why

Lo que `payment_nave` le informa a Nave al crear una intención de pago no coincide con lo que
efectivamente se cobra. Una línea de 0,15 kg a $800/kg se cobra bien —$120,00— pero a Nave le llega
`"quantity": 1` con `"unit_price": "800.00"`, de modo que el checkout y el comprobante que el cliente
descarga dicen 1 × $800,00 mientras se le cobran $120,00. El dinero es correcto porque el cobro sale
por `amount`, pero el detalle que acompaña al cobro miente, y Nave lo acepta sin validarlo.

Junto con eso, el link de pago no le dice a Nave a dónde devolver al cliente, y el plazo de validez
del checkout es un número fijo en el código que ya hizo expirar intenciones durante la propia
homologación.

## What Changes

- **El detalle de productos describe lo que se cobra.** Cuando la cantidad de una línea no es entera,
  la intención informa una unidad con el subtotal de la línea como precio unitario y la cantidad real
  en la descripción. Con cantidades enteras sigue viajando la cantidad tal cual. Alcanza a las dos
  procedencias del detalle: pedidos de venta y facturas.
- **El link de pago le indica a Nave a dónde volver.** La intención del link viaja con la misma URL de
  retorno que ya usa el checkout, para que el cliente que paga una factura pueda regresar a Odoo en
  lugar de quedarse en la pantalla de Nave.
- **El plazo de validez del checkout se puede configurar.** Hoy son 50 minutos fijos en el código.
  Pasa a ser un valor ajustable, conservando ese mismo plazo como valor por omisión para no alterar el
  comportamiento de quien no lo toque.

Ningún cambio es incompatible: las intenciones que hoy se crean correctamente se siguen creando
igual.

## Capabilities

### New Capabilities

- `nave-payment-request`: qué le informa Odoo a Nave al crear una intención de pago —el detalle de lo
  que se cobra, a dónde devolver al cliente y por cuánto tiempo vale la intención— de modo que lo que
  el cliente ve en el checkout y en su comprobante se corresponda con lo que se le cobra.

### Modified Capabilities

<!-- Ninguna: no hay specs sincronizadas todavía, y las capacidades de los cambios en vuelo
     (`nave-payment-provider`, `nave-payment-record`, `nave-transaction-lifecycle`) cubren la
     identidad del comercio, lo que queda registrado al volver y el ciclo de vida de la transacción,
     no el contenido de la intención que se envía. -->

## Impact

- `payment_nave/models/payment_transaction.py` — `_nave_get_products_payload` (ramas de venta y de
  factura) y la construcción del payload del checkout.
- `payment_nave/models/nave_link_wizard.py` — construcción del payload del link de pago.
- Configuración: un ajuste nuevo para el plazo de validez del checkout, que debe respetar la
  operación multi-compañía del módulo.
- Pruebas: `payment_nave/tests/`.
- Sin impacto en `pos_nave`: los flujos presenciales arman su propio payload.

### Evidencia

Los tres defectos se verificaron contra sandbox el 2026-10-05; `tasks/plan_homologacion_nave.md`
§3.20 tiene los payloads reales y las capturas. El sondeo que fija el camino de la corrección:

| Payload enviado | Respuesta de Nave |
|---|---|
| `quantity: 0.15`, unit `800.00`, total `120.00` | **HTTP 502** con página HTML de error |
| `quantity: 1`, unit `120.00`, total `120.00` | **200 OK** |
| `quantity: 1`, unit `800.00`, total `120.00` | **200 OK** |

Nave no admite cantidades fraccionarias —y ni siquiera responde un 400— y acepta sin chistar un
detalle que no cuadra con el importe, que es por qué el defecto venía pasando inadvertido.
