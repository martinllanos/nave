# Design

## Context

Ver `proposal.md` — Why. Lo que condiciona el enfoque:

- El detalle de productos se arma en un solo lugar, `_nave_get_products_payload`, con dos ramas casi
  idénticas: una lee líneas de pedido de venta y otra líneas de factura. El link de pago arma el suyo
  por separado en el wizard.
- Nave rechaza cantidades fraccionarias con un **502** —no con un 400— y acepta sin validar un
  detalle que no cuadra con el `amount`. El sondeo está en `tasks/plan_homologacion_nave.md` §3.20.
  Esto fija el camino: la corrección no puede consistir en mandar el decimal.
- `payment.provider` ya es un modelo por compañía: el core le pone `company_id`, y las credenciales
  de Nave (`nave_client_id`, `nave_client_secret`) y los `pos_id` ya viven ahí.
- La URL de retorno ya se calcula en el checkout a partir de `get_base_url()`; el wizard no la arma.

## Goals / Non-Goals

**Goals:**

- Una sola forma de construir el detalle, compartida por las tres procedencias (pedido, factura,
  wizard), para que el defecto no pueda reaparecer en una sola de ellas.
- Que la corrección sea verificable mirando el payload, no sólo el importe cobrado.

**Non-Goals:**

- Cambiar cómo se calcula el importe que se cobra. `amount` ya es correcto en todos los casos; lo que
  está mal es el detalle que lo acompaña.
- Tocar los payloads de `pos_nave`. Los flujos presenciales arman el suyo y no comparten este código.
- Hacer configurable el plazo del link de pago: el wizard ya lo expone como `duration_hours`.

## Decisions

### Cantidad fraccionaria: una unidad con el subtotal de la línea

Cuando la cantidad no es entera, se informa `quantity: 1` con el subtotal de la línea como precio
unitario, y la cantidad real pasa a la descripción (por ejemplo, `0,15 kg × $800,00`). Con cantidad
entera no cambia nada: viaja la cantidad y el precio unitario tal cual.

*Por qué no mandar el decimal*: Nave responde 502. No es una preferencia de diseño, es lo que el
sondeo devolvió.

*Por qué no mandar siempre `quantity: 1` con el subtotal*: funcionaría, pero degrada el detalle de la
venta normal —tres unidades a $500 pasarían a leerse como una de $1.500— que es el caso mayoritario y
hoy se informa bien.

*Por qué la cantidad va en la descripción*: es el único campo de texto libre del producto, y sin ella
el cliente perdería el dato de cuánto llevó. La descripción ya se recorta a 150 caracteres, así que
el prefijo va primero para que no sea lo que se pierde al truncar.

### El detalle viaja con impuestos incluidos

Cada entrada del detalle informa lo que esa línea le cuesta al cliente con IVA (`price_total`), y el
precio unitario se deriva de ahí dividiendo por la cantidad.

*Por qué*: lo descubrieron los tests del punto anterior. El detalle se armaba con
`price_reduce_taxexcl`, sin impuestos, mientras la intención se cobra por un importe con impuestos:
una venta de $120 + IVA informaba productos por $120 y cobraba $145,20. Nunca se vio en homologación
porque el catálogo de prueba no tiene impuestos configurados, así que ambos números coincidían.

Es un desajuste preexistente, no introducido por este cambio, pero corregir la cantidad y dejar el
IVA de lado habría dejado el detalle igual de incoherente por otro motivo. Mostrar precios finales es
además cómo se le informan los precios al consumidor en Argentina.

*Qué cambia para una venta normal*: tres unidades a $500 pasan a informarse como tres a $605. El
cliente ve lo que paga por unidad.

### El redondeo se absorbe en el detalle, no en el importe

El total de una línea dividido por su cantidad puede no dar dos decimales exactos. El precio unitario
se redondea a dos, pero el `amount` de la intención se sigue tomando del importe de la transacción y
no de la suma del detalle. Si ambos difirieran por redondeo, manda el importe: es el que determina
cuánto se cobra, y es el que Odoo concilia después.

Dicho de otro modo: el requisito de que el detalle se corresponda con el importe se cumple a nivel de
lo que el cliente lee, no como una identidad aritmética exacta que haría fallar un cobro por un
centavo.

### El detalle se construye una sola vez

Las dos ramas de `_nave_get_products_payload` y la del wizard pasan a compartir la construcción de
cada entrada del detalle, parametrizada por los tres datos que difieren entre un pedido, una factura
y una línea del wizard: nombre, descripción y cantidad con su precio.

*Por qué*: hoy el mismo defecto está escrito dos veces (`:161` y `:174`). Corregirlo en dos lugares
deja viva la posibilidad de arreglar uno y olvidar el otro, que es exactamente cómo apareció.

### El plazo de validez vive en el proveedor

Un campo nuevo en `payment.provider`, con 50 minutos por omisión.

*Por qué no `ir.config_parameter`*: es global. El módulo debe operar multi-compañía
(`.agent/rules.md` §2), y un parámetro de sistema haría que dos compañías compartieran el plazo.

*Por qué el proveedor y no la compañía*: el proveedor ya es por compañía y ya es donde viven las
credenciales y los `pos_id` de Nave. Un campo en `res.company` agregaría un segundo lugar donde
buscar la configuración de Nave sin ganar nada.

*Unidad*: minutos. El checkout opera en esa escala —50 minutos— y expresarlo en horas obligaría a
decimales para el valor por omisión. El wizard usa horas porque un link vive días; son escalas
distintas y está bien que se declaren distinto.

### La URL de retorno del link reutiliza la del checkout

El wizard arma `additional_info.callback_url` con la misma URL que ya usa el checkout. No se
introduce una ruta de retorno distinta para el link.

*Por qué*: la ruta existente ya resuelve la transacción por su referencia, que es lo único que
necesita para redirigir. Una ruta separada duplicaría esa lógica sin motivo.

## Risks / Trade-offs

- **El detalle de una línea fraccionaria deja de verse como una cantidad** → La cantidad real queda en
  la descripción, que es lo que Nave muestra junto al nombre. Se pierde la posibilidad de que Nave la
  trate como número, pero hoy esa posibilidad no existe de todos modos: Nave no acepta decimales.
- **Un plazo configurado demasiado corto haría expirar intenciones antes de que el cliente pague** →
  El valor por omisión no cambia, así que nadie queda peor sin tocar nada. El campo lleva una ayuda
  que advierte el efecto.
- **El cambio toca el payload de los tres flujos online a la vez** → Cada uno tiene su prueba, y el
  detalle construido es verificable sobre el payload sin necesidad de cobrar.

## Migration Plan

No hay migración de datos: el campo nuevo toma su valor por omisión en los proveedores existentes y
las intenciones ya creadas no se tocan. El despliegue es una actualización de módulo.

Si hubiera que volver atrás, revertir el módulo restaura el comportamiento anterior sin dejar estado
inconsistente: lo único que persiste es el campo del plazo, que queda ignorado.
