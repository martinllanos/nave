# Proposal

## Why

La cantidad real de una línea fraccionaria no le llega al cliente. Al corregir el detalle de
productos se la puso al frente de la descripción, dando por sentado que Nave la muestra junto al
nombre; abriendo el checkout con el navegador y leyendo el DOM se comprobó que **la descripción no se
renderiza en ningún lado**, ni en el resumen de la compra ni en la pantalla de pago con tarjeta. Nave
muestra sólo `{cantidad}x {nombre}` y el importe.

Lo que el cliente lee para una línea de 0,15 kg a $800 el kilo es `1x Granel por kilo — $120,00`. El
importe es correcto, que era el defecto que se arregló, pero se perdió el dato de cuánto llevó.

Aparte de eso, un test de la suite falla según lo que haya quedado en la base en lugar de según el
código, lo que convierte una corrida roja en una pista falsa.

## What Changes

- **La cantidad real viaja en el nombre del producto**, que es lo que Nave sí muestra, en lugar de en
  la descripción.
- **El test del cron deja de depender de los datos de la base**: pasa a juzgar sólo las transacciones
  que él mismo creó.

El importe que se cobra y la correspondencia entre detalle e importe no cambian.

## Capabilities

### New Capabilities

<!-- Ninguna. -->

### Modified Capabilities

- `nave-payment-request`: el requisito del detalle de productos exige hoy que la cantidad real quede
  en la descripción de la línea. Pasa a exigir que quede donde el cliente la lee, que es lo que el
  requisito buscaba y la descripción no cumple.

## Impact

- `payment_nave/models/nave_payload.py` — dónde se antepone la cantidad.
- `payment_nave/tests/test_nave_payment.py` — el test del detalle y el del cron.
- Sin impacto en los importes, en el link de pago ni en `pos_nave`.

### Evidencia

Leyendo el DOM del checkout (el contenido vive dentro del web component `payfac-sdk`), los únicos
nodos de texto del detalle son:

```
1x [PRUEBA] Granel por kilo
$120,00
$ 120,00
```

Ninguno contiene la descripción. En el checkout de un pedido con varias líneas se vio lo mismo:
`1x [PRUEBA] Precio ...`, con el nombre recortado por CSS y sin descripción visible.

Sobre el test: el cron barre **todas** las transacciones Nave pendientes de la base, no sólo la que
el test prepara, así que cualquiera en `draft` o `pending` con más de 30 minutos lo hace fallar. Pasó
el 2026-10-05 con una transacción creada a mano para verificar un payload contra sandbox: el test
cayó cuarenta minutos más tarde, sin que nadie hubiera tocado el cron, y una corrida en limpio no lo
reproducía.
