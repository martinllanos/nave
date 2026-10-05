# Spec Delta

## MODIFIED Requirements

### Requirement: El detalle de productos se corresponde con el importe que se cobra

La intención de pago DEBE informar un detalle de productos cuya suma coincida con el importe cobrado,
impuestos incluidos, salvo las diferencias de redondeo a dos decimales que impone el proveedor.

Nave rechaza las cantidades fraccionarias y no valida que el detalle cuadre con el importe, así que
una línea con cantidad no entera DEBE informarse de una forma que preserve esa correspondencia en
lugar de enviar la cantidad truncada junto al precio unitario original.

Cuando la cantidad informada no sea la real, la cantidad real DEBE quedar donde el cliente la lee.

#### Scenario: Línea con cantidad fraccionaria

- **WHEN** se genera una intención para una línea de 0,15 kg a $800,00 por kilo, que se cobra $120,00
- **THEN** el detalle informa un importe de $120,00 para esa línea
- **AND** el cliente puede leer que la línea es de 0,15 kg
- **AND** el importe cobrado sigue siendo $120,00

#### Scenario: Línea con cantidad entera

- **WHEN** se genera una intención para una línea de 3 unidades cuyo importe con impuestos es
  $1.815,00
- **THEN** el detalle informa 3 unidades a $605,00 cada una
- **AND** el importe cobrado sigue siendo $1.815,00

#### Scenario: La línea tiene impuestos

- **WHEN** se genera una intención para una venta de $120,00 más $25,20 de impuestos
- **THEN** la suma del detalle es $145,20, el mismo importe que se cobra

#### Scenario: La cantidad fraccionaria proviene de una factura

- **WHEN** se genera una intención para la línea de una factura con cantidad no entera
- **THEN** el detalle se corresponde con el importe cobrado igual que si proviniera de un pedido de
  venta

#### Scenario: Varias líneas con cantidades mixtas

- **WHEN** se genera una intención para un documento con líneas de cantidad entera y fraccionaria
- **THEN** la suma de los importes del detalle coincide con el importe cobrado
