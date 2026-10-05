# Tasks

## 1. Archivos del set

- [x] 1.1 Crear `docs/homologacion/pos_category.csv` y `docs/homologacion/product_public_category.csv`, cada uno con una fila "Homologación Nave" y External ID `homologacion_nave.categ_pos` / `homologacion_nave.categ_public` (D2). Verificar: los dos archivos se abren en una planilla con las columnas `id,name` y una fila de datos.
- [x] 1.2 Crear `docs/homologacion/product_template.csv` con los 10 productos de D3. Columnas: `id`, `default_code`, `name`, `type`, `is_storable`, `list_price`, `uom_id`, `uom_po_id`, `taxes_id`, `sale_ok`, `available_in_pos`, `pos_categ_ids/id`, `is_published`, `public_categ_ids/id`, `description_sale`. `taxes_id` vacío, punto decimal y UTF-8. Verificar: un chequeo con `python3 -c` sobre el CSV confirma 10 filas, `list_price <= 1200`, referencias `HOMO-NAVE-01` a `10` únicas, nombres con prefijo `[PRUEBA]`, el nombre de 07 con más de 100 caracteres y el de 06 con tildes, eñe y signos.
- [x] 1.3 Escribir `docs/homologacion/README.md` con:
  - Orden de importación y opciones del importador (separador decimal ".", codificación UTF-8).
  - Tabla producto → casos (D3).
  - Presupuesto estimado (D4) y planilla de gasto real (fecha, caso, producto, monto, respuesta de Nave).
  - Procedimiento de retiro (D5).
  
  Verificar: cada caso exigido por el requirement "Cobertura de casos" figura con al menos un producto.

## 2. Precondiciones en producción

- [ ] 2.1 Confirmar que el proveedor Nave ya no tiene el `pos_id` de sandbox `f71ba756-…` y que las credenciales cargadas son las productivas (tareas 1.5 y 4.4 de `promote-do-onlyone-to-production`). Verificar: el campo POS ID (Tienda) del proveedor muestra un id de la columna "Producción" de la tabla de `pos_id`.
- [ ] 2.2 Confirmar que en la base de producción están instalados `website_sale` y `point_of_sale`, que existe el POS de la compañía monotributista y que la UdM "kg" está disponible. Verificar: las tres pantallas abren y "kg" aparece en Unidades de medida.

## 3. Carga en producción

- [ ] 3.1 Importar `pos_category.csv` y después `product_public_category.csv` desde las listas de categorías. Verificar: existe una categoría "Homologación Nave" en POS y otra en el sitio web.
- [ ] 3.2 Importar `product_template.csv` desde Ventas > Productos > Importar, con las opciones del README. Verificar: la búsqueda `HOMO-NAVE` devuelve exactamente 10 productos, todos sin impuestos, en ambas categorías y publicados.
- [ ] 3.3 Reimportar el mismo archivo con un precio cambiado y después volver al original. Verificar: siguen siendo 10 productos (sin duplicados) y el precio se actualizó en ambos pasos.
- [ ] 3.4 Revisar los canales. Verificar: `www.onlyone.ar/shop` muestra los 10 productos en la categoría "Homologación Nave" en una ventana de incógnito, y una sesión POS los muestra al filtrar por la categoría.

## 4. Primer uso

- [ ] 4.1 Hacer un cobro web con HOMO-NAVE-01 (ARS 10) y anotarlo en la planilla de gasto. Verificar: el total del pedido, el `amount.value` del log y el monto en el Espacio Nave coinciden, y la transacción termina `done`.
- [ ] 4.2 Hacer un pedido web con HOMO-NAVE-05 en cantidad 0,5 kg (A13) y anotar qué recibe Nave en `products[]`. Verificar: el hallazgo queda registrado en el README y en la fila A13 de `tasks/plan_homologacion_nave.md`.

## 5. Documentación del proyecto

- [ ] 5.1 Enlazar el set desde `tasks/plan_homologacion_nave.md` (ítem P9 del checklist de preparación) y marcar P9 como resuelto. Anotar en la fila A12 que no aplica a una compañía monotributista. Verificar: P9 apunta a `docs/homologacion/README.md` y A12 tiene la nota.
- [x] 5.2 Agregar a `tasks/todo.md` el retiro del set como paso de cierre de la homologación (E4). Verificar: el ítem existe y apunta al procedimiento de retiro del README.
