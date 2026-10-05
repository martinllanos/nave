# Proposal

## Why

Ningún cliente puede pagar desde la tienda. Al apretar "Pagar ahora" se crea la intención en Nave y
el navegador llega a la pantalla de pago **sin el identificador de esa intención**, así que Nave no
sabe qué cobrar y muestra una pantalla en blanco. El pedido queda esperando un pago que el cliente no
tiene forma de completar.

El formulario de redirección pone el identificador en el query string de su `action` y se envía con
`method="get"`. El algoritmo de submit del HTML descarta el query string de la `action` y lo
reemplaza por los campos del formulario; como el formulario no tiene ninguno, el parámetro se pierde
entre Odoo y Nave.

No lo detectó ninguna de las pruebas de homologación ni ninguno de los 79 tests: todas abrieron el
`checkout_url` directamente. El recorrido que de verdad hace un cliente —carrito, dirección, medio de
pago, pagar— se ejecutó por primera vez el 2026-10-05 y falló en el primer intento.

## What Changes

- **El cliente llega a la pantalla de pago con su intención cargada.** La redirección deja de
  depender del query string de la `action`: los parámetros que Nave pone en la URL del checkout
  viajan como campos del formulario, que es lo que un envío GET conserva.
- Los parámetros se toman **de la URL que Nave devuelve**, sin suponer cuáles son ni cuántos.

No cambia nada de lo que se le informa a Nave al crear la intención, ni el link de pago, que entrega
la URL al usuario y no pasa por este formulario.

## Capabilities

### New Capabilities

<!-- Ninguna. -->

### Modified Capabilities

- `nave-payment-request`: se agrega el requisito de que el cliente llegue a la pantalla de pago con
  la intención que se creó. La capacidad ya cubre la intención y el retorno del cliente tras pagar;
  faltaba el tramo de ida.

## Impact

- `payment_nave/views/payment_provider_views.xml` — la plantilla `redirect_form`.
- `payment_nave/models/payment_transaction.py` — los valores que se le pasan a esa plantilla.
- Pruebas: `payment_nave/tests/`.
- Sin impacto en `pos_nave` ni en el wizard del link de pago.

### Evidencia

Pedido `S00030` ($223,45) generado recorriendo el e-commerce de homologación:

```
nave_checkout_url guardado  → …/nave?payment_request_id=f9d279b1-a6d3-4135-bec6-a570035b9c51
location.href tras el submit → …/nave
```

La intención existía en Nave y el cliente veía una pantalla vacía.
