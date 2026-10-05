# Spec Delta

## Purpose

Proveer un catálogo acotado y reconocible de productos de prueba en la base de producción, con el que ejercitar la matriz de homologación de Nave con cobros reales, tanto en el e-commerce como en el Punto de Venta, sin mezclarse con el catálogo comercial.

## ADDED Requirements

### Requirement: Diez productos disponibles en ambos canales

El set SHALL contener exactamente 10 productos. Cada uno SHALL poder venderse desde la tienda online de `www.onlyone.ar` y desde el Punto de Venta de la compañía monotributista.

#### Scenario: Visible en la tienda

- **WHEN** un visitante abre la categoría "Homologación Nave" de `www.onlyone.ar/shop` durante la homologación
- **THEN** ve los 10 productos y puede agregar cualquiera al carrito y llegar al pago con Nave

#### Scenario: Visible en el POS

- **WHEN** un cajero abre una sesión del Punto de Venta y filtra por la categoría "Homologación Nave"
- **THEN** ve los 10 productos y puede agregarlos a una orden

### Requirement: Precios dentro de los topes de la homologación acotada

Todo producto SHALL tener un precio de venta final de ARS 1.200,00 o menos, para que una línea de cantidad 1 no supere el tope por transacción. Los precios SHALL ser finales para el consumidor: la compañía es monotributista y los productos MUST NOT llevar impuestos de venta. El presupuesto documentado de la matriz de pruebas MUST NOT superar ARS 90.000 en total.

#### Scenario: Precio máximo

- **WHEN** se revisa el set cargado
- **THEN** ningún producto tiene precio de venta mayor a ARS 1.200,00 y ninguno tiene impuestos de venta asignados

#### Scenario: Total del pedido igual al monto enviado a Nave

- **WHEN** se paga en el e-commerce un pedido con un solo producto del set
- **THEN** el total del pedido en Odoo, el `amount.value` enviado a Nave y el precio de lista del producto coinciden

### Requirement: Cobertura de casos de la matriz

El set SHALL incluir, como mínimo:

- Un producto de importe mínimo para intentos baratos (rotación de `pos_id`, primeros cobros).
- Un producto con precio con centavos distintos de cero (A9).
- Un producto que se venda por kilogramo y admita cantidades fraccionarias (A13).
- Un producto cuyo nombre tenga tildes, eñes y signos (codificación de `products[]`).
- Un producto con nombre de más de 100 caracteres.
- Un producto con precio igual al tope por transacción.
- Un producto apto para pagos en cuotas (A3, A4, C12).
- Un producto de tipo servicio (facturas y links, B1c).

#### Scenario: Trazabilidad caso-producto

- **WHEN** se consulta la documentación del set
- **THEN** cada producto figura con los casos de la matriz que ejercita, y cada caso de la lista anterior tiene al menos un producto

### Requirement: Identificación y separación del catálogo real

Cada producto del set SHALL identificarse sin ambigüedad:

- Referencia interna con formato `HOMO-NAVE-NN`.
- Nombre que empiece con `[PRUEBA]`.
- Pertenencia a la categoría de POS y a la categoría pública "Homologación Nave".

Los productos del set MUST NOT pertenecer a ninguna categoría del catálogo comercial.

#### Scenario: Búsqueda del set

- **WHEN** se buscan productos por referencia interna `HOMO-NAVE`
- **THEN** aparecen exactamente los 10 productos del set y ningún otro

### Requirement: Carga repetible sin duplicados

El set SHALL poder cargarse desde un archivo versionado en el repo, mediante la importación estándar de Odoo, sin código adicional instalado en producción. Importar el mismo archivo dos veces MUST actualizar los productos existentes en lugar de crear duplicados.

#### Scenario: Reimportación

- **WHEN** se importa el archivo del set por segunda vez, con un precio modificado
- **THEN** siguen existiendo 10 productos `HOMO-NAVE` y el precio queda actualizado

### Requirement: Retiro al terminar la homologación

Al cerrar la homologación, los productos del set SHALL dejar de estar disponibles para la venta en ambos canales. Los pedidos, facturas y transacciones que los usaron SHALL conservarse íntegros.

#### Scenario: Después del retiro

- **WHEN** se ejecuta el procedimiento de retiro documentado
- **THEN** los productos no aparecen en la tienda ni en el POS, y los pedidos y transacciones de homologación siguen mostrando sus líneas y montos
