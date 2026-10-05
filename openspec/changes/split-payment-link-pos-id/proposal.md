# Proposal

## Why

Nave asigna un `pos_id` distinto **por medio de cobro**, no por tienda: la API responde
`409 INVALID_POS` — *"Given POS is for a different payment type"* — cuando el `seller.pos_id` de la
intención pertenece a otro medio. En producción el comercio tiene `b4c94f29-…` para ECOMMERCE y
`925a1b22-…` para LINK DE PAGO, pero `payment_nave` guarda un solo `nave_pos_id` y lo usa para los
dos flujos online. Con el de ECOMMERCE cargado —que es lo que exige el checkout— **el wizard de link
de pago está roto en producción**: toda factura o pedido desde el que se genere un link va a recibir
un 409.

## What Changes

- **Nuevo campo `nave_payment_link_pos_id` en `payment.provider`**, para el `pos_id` del medio LINK
  DE PAGO. Opcional, visible junto al `pos_id` de tienda en la pestaña de credenciales.
- **El wizard de link de pago usa ese campo** (`nave_link_wizard.py`) en lugar de `nave_pos_id`.
- **Fallback explícito**: si el campo nuevo está vacío, el wizard sigue usando `nave_pos_id`. Las
  instalaciones que hoy funcionan con un único `pos_id` —porque Nave les dio el mismo para ambos
  medios, o porque sólo usan un flujo— no cambian de comportamiento al actualizar.
- **El checkout de e-commerce no cambia**: `payment_transaction.py` sigue usando `nave_pos_id`.
- **El `pos_id` pasa a resolverse en un solo lugar** del proveedor, en vez de leerse del campo
  directamente en cada punto de uso, para que el próximo medio de cobro sea un caso más y no otra
  rama suelta.

No es breaking: el comportamiento sólo cambia cuando el campo nuevo se completa.

## Capabilities

### New Capabilities

- `nave-payment-provider`: cómo el proveedor Nave resuelve la identidad del comercio ante la API
  —el `pos_id` que viaja en `seller.pos_id`— según el medio de cobro de cada intención, y cómo se
  configura esa identidad.

### Modified Capabilities

(ninguna: el proyecto todavía no tiene specs de los módulos)

## Impact

- `payment_nave/models/payment_provider.py`: campo nuevo y resolución del `pos_id` por medio de cobro.
- `payment_nave/models/nave_link_wizard.py:186`: pasa a pedir el `pos_id` del medio `payment_link`.
- `payment_nave/models/payment_transaction.py:68`: pasa a pedirlo por el mismo camino, con el medio
  `ecommerce`; el valor que obtiene no cambia.
- `payment_nave/views/payment_provider_views.xml`: el campo nuevo en la pestaña de credenciales.
- `payment_nave/tests/test_nave_payment.py`: cobertura de la resolución y del fallback.
- Versión del módulo y configuración en producción: cargar `925a1b22-…` en el campo nuevo deja
  operativo el link de pago, que hoy no lo está.
- `pos_nave` no se toca: ya resuelve su `pos_id` por dispositivo (`nave_terminal_id`).
