# Proposal

## Why

Para configurar los módulos, el comercio carga en Odoo los `pos_id` que le asigna Nave: uno para la
tienda online, otro para los links de pago y uno por cada terminal o QR. La ayuda de esos campos dice
sólo *"Nave > Integraciones"* o *"Nave > Integraciones > Sistema de gestión"*, y eso no alcanza para
elegir el correcto.

Nave entrega los `pos_id` en un archivo, `POS_ID-<CUIT>.xlsx`, que se descarga desde
**Integraciones › Sistema de gestión › Descargar archivo**. Tiene una fila por medio de cobro y por
dispositivo, con cuatro columnas: *Nombre del local*, *Medio de cobro*, *Nombre/N° de serie* y
*POS ID*. Cada medio se identifica distinto:

| Medio de cobro en Odoo | Fila del archivo |
|---|---|
| Tienda online | *Medio de cobro* `ECOMMERCE`, con el nombre de la tienda en *Nombre/N° de serie* |
| Link de pago | *Medio de cobro* `LDP` |
| Nave Point | *Medio de cobro* `NAVE POINT`, con el número de serie de la terminal |
| QR | *Medio de cobro* `QR`, con el nombre del QR y del local |

Al homologar costó saber qué `pos_id` correspondía a cada tienda. Habíamos creado varias, que no se
pueden borrar, y el archivo las identifica sólo por el nombre (ver
`docs/requerimientos_publicacion_odoo_apps.md` §6). Un `pos_id` cargado en el campo equivocado hace
que Nave rechace el cobro con `invalid_pos`, y ese mensaje no dice cuál de los campos está mal.

Los módulos se entregan a Nave para publicarlos, así que quien lea estos textos va a ser un comercio
configurando Odoo por primera vez, sin nadie al lado.

Además, varios textos dicen que Nave rechaza con `409 INVALID_POS`. Ese código es el del ejemplo de
la documentación; la API real responde `400` con `code: "invalid_pos"`, como se verificó en la
homologación (`plan_homologacion_nave.md` §3.24). La detección del error ya contempla las dos formas;
lo que está mal es lo que dicen la ayuda, los comentarios y la spec.

## What Changes

- **La ayuda de cada campo de `pos_id` indica qué fila del archivo copiar.** Dice de dónde se
  descarga el archivo y cómo reconocer la fila de ese medio de cobro: el nombre de la tienda, la fila
  `LDP`, el número de serie de la terminal o el nombre del QR y su local.
- **El error se nombra como lo devuelve Nave.** La ayuda, los comentarios y la spec dejan de citar
  `409 INVALID_POS`, y la spec describe el rechazo sin atarlo a un código HTTP.
- **La descripción del módulo de punto de venta nombra el archivo**, alineada con la ayuda del campo.

No cambia el comportamiento: son textos.

## Capabilities

### New Capabilities

<!-- Ninguna. -->

### Modified Capabilities

- `nave-payment-provider`: la ayuda de cada `pos_id` tiene que indicar la fila del archivo de Nave, y
  el rechazo por identidad se describe sin atarlo a un código HTTP.
- `nave-pos-collection`: se agrega que el método de pago del punto de venta indica de dónde sale el
  `pos_id` de cada dispositivo. Hoy no hay ningún requisito sobre esa configuración.

## Impact

- `payment_nave/models/payment_provider.py`: la ayuda de `nave_pos_id` y de
  `nave_payment_link_pos_id`, y dos comentarios.
- `payment_nave/models/payment_transaction.py`: un comentario.
- `pos_nave/models/pos_payment_method.py`: la ayuda de `nave_terminal_id`.
- `pos_nave/__manifest__.py`: la descripción.
- Pruebas: `payment_nave/tests/` y `pos_nave/tests/`.
- Sin migración: la ayuda de un campo se lee del código.
