# Design

## Context

- **La base de producción `www.onlyone.ar` ya está creada**, según el usuario el 2026-09-28. Tiene la compañía monotributista y el proveedor Nave en estado **Activado**. Las tareas del change `promote-do-onlyone-to-production` todavía no están marcadas: el corte se hizo por fuera de ese flujo.
- **El proveedor tiene cargado como POS ID `f71ba756-…`, que es el id de sandbox** (tabla de `pos_id` de `promote-do-onlyone-to-production/tasks.md`). Ningún cobro con este set va a funcionar hasta corregirlo.
- **La plantilla contable de monotributo (`l10n_ar`, `ar_base`) no define impuestos de venta** (`account.tax-ar_base.csv` solo trae percepciones de compra). Los precios de lista son finales, y `products[]` y `amount` coinciden. Por eso A12 no es reproducible en esta compañía.
- **Campos de Odoo 18 involucrados:**
  - `product.template`: `type` (`consu` o `service`) e `is_storable` (de `stock`, en falso para no exigir inventario).
  - `available_in_pos` y `pos_categ_ids` (de `point_of_sale`).
  - `is_published` y `public_categ_ids` (de `website_sale`).
  - `taxes_id`, `uom_id`, `uom_po_id` y `default_code`.
- **Topes de §3.11:** ARS 1.200 por transacción y ARS 90.000 en total.
- **Cómo trata el módulo cantidades y montos:** `payment_transaction.py:151` envía `int(qty) or 1`, de donde sale el caso A13, y el monto va como string con 2 decimales (A9).

## Goals / Non-Goals

**Goals:**

- El set se carga en minutos desde la UI, se puede repetir y queda auditado en git.
- Cada peso gastado en la homologación responde a un caso concreto de la matriz.

**Non-Goals:**

- Stock, variantes, listas de precios o combos. No los ejercita ningún caso pendiente.
- Automatizar la carga por API o con un módulo de datos. Se descartó por decisión del usuario.
- Corregir el `pos_id` del proveedor. Es la tarea 4.4 de `promote-do-onlyone-to-production`.

## Decisions

### D1. CSV importable con External ID propio

Los archivos van en `docs/homologacion/`. La columna `id` lleva External IDs con el prefijo `homologacion_nave.` (por ejemplo, `homologacion_nave.producto_01`). Al importar, Odoo crea esos `ir.model.data` con módulo `homologacion_nave`, y en una reimportación **actualiza** el registro en lugar de duplicarlo, que es lo que exige el requirement "Carga repetible".

- **Alternativa descartada: un módulo de datos.** Deja código instalado en producción, y desinstalarlo choca con los pedidos que referencian los productos.
- **Alternativa descartada: un script XML-RPC.** Necesita credenciales de producción en la máquina local.

### D2. Tres archivos en orden de dependencia

1. `pos_category.csv`: `id,name`.
2. `product_public_category.csv`: `id,name`.
3. `product_template.csv`: referencia las categorías por External ID (`pos_categ_ids/id`, `public_categ_ids/id`), así no depende de que coincidan los nombres.

Separarlos evita depender de la opción de crear relaciones faltantes del importador.

### D3. El set

Precios en ARS, finales y sin impuestos. `consu` implica `is_storable` en falso.

| Ref | Nombre (tras `[PRUEBA] `) | Tipo | UdM | Precio | Casos |
|---|---|---|---|---|---|
| HOMO-NAVE-01 | Importe mínimo | consu | Unidades | 10,00 | Rotación de `pos_id`, primer cobro web y POS, C1, C2b |
| HOMO-NAVE-02 | Cobro bajo | consu | Unidades | 50,00 | C3 (tarjeta vencida o CVV), C4 a C8 (cancelaciones y timeouts), A7 |
| HOMO-NAVE-03 | Precio con centavos | consu | Unidades | 123,45 | A9 (versión bajo el tope del caso de $1.234,56) |
| HOMO-NAVE-04 | Precio terminado en 99 | consu | Unidades | 199,99 | Redondeo del `amount` |
| HOMO-NAVE-05 | Granel por kilo | consu | kg | 800,00 | A13 (qty 0,5 → se envía 1) |
| HOMO-NAVE-06 | Café Ñandú «Edición» 100% — Prueba & Cía | consu | Unidades | 250,00 | Codificación de `products[].name` |
| HOMO-NAVE-07 | Nombre largo (más de 100 caracteres) | consu | Unidades | 300,00 | Truncado de `products[].name` |
| HOMO-NAVE-08 | Tope por transacción | consu | Unidades | 1.200,00 | Límite exacto, A4 (cuotas) |
| HOMO-NAVE-09 | Cuotas y ticket | consu | Unidades | 1.150,00 | A2, A3, C2 (chip), C12 (ticket) |
| HOMO-NAVE-10 | Servicio de prueba | service | Unidades | 500,00 | Factura, B1c/B2c (cuando haya `pos_id` de links), F1 |

- **Multilínea:** HOMO-NAVE-01 + 03 + 06 suman 383,45 y cubren un carrito de varias líneas (F4) sin producto extra.
- **Descuento:** se ejercita aplicando un descuento de línea en el POS sobre HOMO-NAVE-09. No necesita producto propio.
- `description_sale` de todos: "Producto de prueba para homologación de pagos. No se envía."

### D4. Presupuesto de la matriz

La estimación es de **unos ARS 15.000 contando reintentos**, muy por debajo de los ARS 90.000.

- La rotación de `pos_id` usa HOMO-NAVE-01: unos 10 intentos de $10.
- Cada caso aprobado se cobra una vez con su producto, más un reintento.
- Los rechazos no acreditan.

El README lleva la planilla de gasto real con fecha, caso, producto y monto, y se actualiza en cada sesión de pruebas.

### D5. Publicados durante la homologación, retiro archivando

Los productos se importan con `is_published = True` para que el e-commerce los muestre sin pasos manuales. Al cierre se **archivan** desde la lista de productos: se filtra `HOMO-NAVE`, se seleccionan todos y se usa Acción > Archivar. Un producto archivado deja de aparecer en la tienda y deja de cargarse en el POS, así que no hace falta despublicarlo antes.

- Archivar no borra, así que los pedidos y las transacciones conservan sus líneas, como pide el requirement "Retiro".
- **Descartado: borrar.** Odoo lo impide para productos con pedidos, y además se perdería trazabilidad.
- **Descartado: un CSV de retiro** (reimportar con `available_in_pos` / `is_published` / `active` en falso). Es un paso más sin beneficio frente a la acción estándar.
- **Para cortar la exposición entre sesiones de prueba**, se archiva el set y se desarchiva al retomar. Los External IDs se conservan, así que una reimportación posterior sigue actualizando los mismos productos.

## Risks / Trade-offs

- **[Riesgo] Un cliente real compra un producto `[PRUEBA]` desde la tienda pública**, lo que genera un cobro real y hoy no se puede devolver por API (B6). → Nombre y descripción explícitos, y precios bajos. Si pasa, el procedimiento es la devolución manual del runbook de `promote-do-onlyone-to-production` (tarea 4.6). Entre sesiones de prueba, el set se puede archivar en bloque (D5).
- **[Riesgo] Con el `pos_id` de sandbox cargado, los primeros intentos fallan y se pueden confundir con un problema del set.** → La tarea 2.1 exige confirmar el `pos_id` antes del primer cobro.
- **[Riesgo] Nave podría exigir un monto mínimo por medio o para cuotas.** Si $10 o $1.150 quedan fuera de lo aceptado, los intentos fallan por monto y no por integración. → El README registra la respuesta de Nave; si hace falta, se sube el precio de HOMO-NAVE-01 o se baja el de 09 y se reimporta (D1 lo permite).
- **[Trade-off] Sin variantes ni stock** no se prueba cómo viajan las variantes en `products[]`. Ningún caso actual de la matriz lo pide.
- **[Riesgo] El importador en español espera los números con el separador que corresponda.** → El CSV usa punto decimal y se importa eligiendo "." como separador decimal en las opciones de importación. El README lo indica.
