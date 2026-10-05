# Proposal

## Why

La base de producción `www.onlyone.ar` ya está creada: compañía monotributista y proveedor Nave activado. Pero no tiene productos con los que ejercitar la matriz de homologación (`tasks/plan_homologacion_nave.md` §4). Como la homologación se hace con **cobros reales acotados** (§3.11: ARS 1.200 por transacción y ARS 90.000 en total), cada producto tiene que tener un precio pensado para un caso concreto, entrar bajo el tope, y poder identificarse y retirarse sin tocar el catálogo real.

## What Changes

- **Un set de 10 productos de homologación, versionado en el repo como CSV importable**, disponibles a la vez en el e-commerce (`www.onlyone.ar/shop`) y en el Punto de Venta. Cada producto está asociado a uno o más casos de la matriz: importe mínimo para la rotación de `pos_id`, decimales (A9), cantidad fraccionaria (A13), caracteres especiales y nombre largo en `products[]`, tope exacto, cuotas (A3, A4), ticket (C12), y un servicio para facturas y links (B1c).
- **Dos categorías propias**, "Homologación Nave" (de POS y de sitio web), que agrupan los productos y permiten publicarlos, ocultarlos o archivarlos en bloque.
- **Identificación inequívoca:**
  - Referencia interna `HOMO-NAVE-01` a `HOMO-NAVE-10`.
  - Nombre con prefijo `[PRUEBA]`.
  - External ID estable, para que reimportar el archivo actualice los productos en lugar de duplicarlos.
- **Presupuesto de pruebas:** la suma estimada de los cobros de la matriz queda documentada y bajo el tope acumulado de ARS 90.000.
- **Procedimiento de carga y de retiro:** importar el CSV, verificar, despublicar y archivar al terminar la homologación. No hay código nuevo en los módulos ni en la imagen de producción.

## Capabilities

### New Capabilities

- `homologation-dataset`: el catálogo de productos de prueba para homologar Nave en producción. Define qué productos existen, en qué canales están disponibles, qué límites de precio respetan, cómo se identifican y cómo se cargan y se retiran.

### Modified Capabilities

(ninguna)

## Impact

- **Base de producción `www.onlyone.ar`:** alta de 10 productos (`product.template`), una categoría de POS (`pos.category`) y una categoría pública de e-commerce (`product.public.category`). Los productos se ven en la tienda pública durante la homologación.
- **Este repo:** archivos nuevos en `docs/homologacion/` (CSV y README de carga, retiro y presupuesto). No se toca código de los módulos.
- **Dependencias:** los cobros con estos productos requieren el `pos_id` correcto del proveedor. **Hoy el proveedor Activado tiene cargado el de sandbox (`f71ba756-…`)**, que debe corregirse primero (tareas 1.5 y 4.4 de `promote-do-onlyone-to-production`).
- **Casos que siguen sin poder ejercitarse:**
  - A12 (descuadre por IVA): la compañía es monotributista y no tiene IVA de venta.
  - Links de pago: no tienen `pos_id` propio en el módulo.
  - Devoluciones: B6 y B2 siguen abiertos.
