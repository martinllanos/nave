# nave-payment-request Specification

## Purpose

Define qué le informa Odoo a Nave al crear una intención de pago —el detalle de lo que se cobra, a
dónde devolver al cliente cuando termina de pagar y por cuánto tiempo vale la intención— de modo que
lo que el cliente ve en el checkout y en su comprobante se corresponda con lo que se le cobra.

## Requirements

### Requirement: El detalle de productos se corresponde con el importe que se cobra

La intención de pago DEBE informar un detalle de productos cuya suma coincida con el importe cobrado,
impuestos incluidos, salvo las diferencias de redondeo a dos decimales que impone el proveedor.

Nave rechaza las cantidades fraccionarias y no valida que el detalle cuadre con el importe, así que
una línea con cantidad no entera DEBE informarse de una forma que preserve esa correspondencia en
lugar de enviar la cantidad truncada junto al precio unitario original.

#### Scenario: Línea con cantidad fraccionaria

- **WHEN** se genera una intención para una línea de 0,15 kg a $800,00 por kilo, que se cobra $120,00
- **THEN** el detalle informa un importe de $120,00 para esa línea
- **AND** la cantidad real queda indicada en la descripción de la línea
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

### Requirement: La intención indica a dónde vuelve el cliente tras pagar

Toda intención de pago que se cobre en una pantalla de Nave DEBE informar la URL de retorno a Odoo,
cualquiera sea el medio por el que se generó, para que el cliente pueda regresar al comercio al
aprobarse el pago en lugar de quedar en la pantalla del proveedor.

#### Scenario: Cobro desde un link de pago

- **WHEN** se genera un link de pago desde una factura o un pedido de venta
- **THEN** la intención viaja con la URL de retorno a Odoo

#### Scenario: Cobro desde el checkout del sitio

- **WHEN** se genera una intención para una compra del e-commerce
- **THEN** la intención viaja con la URL de retorno a Odoo

### Requirement: El plazo de validez de la intención del checkout es configurable

El plazo durante el cual una intención del checkout admite el pago DEBE poder ajustarse sin editar
código, y DEBE conservar como valor por omisión el plazo vigente de 50 minutos.

El ajuste DEBE respetar la operación multi-compañía del módulo.

#### Scenario: No se configuró ningún plazo

- **WHEN** se genera una intención del checkout sin haber ajustado el plazo
- **THEN** la intención vale 50 minutos

#### Scenario: Se configuró un plazo distinto

- **WHEN** se ajusta el plazo y luego se genera una intención del checkout
- **THEN** la intención vale el plazo configurado

#### Scenario: Compañías con plazos distintos

- **WHEN** dos compañías tienen configurado un plazo distinto y cada una genera una intención
- **THEN** cada intención vale el plazo configurado para su compañía

### Requirement: El cliente llega a la pantalla de pago con su intención cargada

Al enviar al cliente a pagar, la redirección DEBE conservar todos los parámetros con los que Nave
identifica la intención en la URL del checkout que devolvió.

Los parámetros DEBEN tomarse de esa URL, sin suponer cuáles son ni cuántos, porque los decide Nave y
no están documentados.

#### Scenario: El cliente paga desde la tienda

- **WHEN** el cliente confirma el pago de un pedido del e-commerce
- **THEN** llega a la pantalla de pago de Nave con la intención que se creó para ese pedido
- **AND** ve el importe y el detalle de su compra

#### Scenario: La URL del checkout trae varios parámetros

- **WHEN** Nave devuelve una URL de checkout con más de un parámetro
- **THEN** la redirección los conserva todos

#### Scenario: La URL del checkout no trae parámetros

- **WHEN** Nave devuelve una URL de checkout sin parámetros
- **THEN** la redirección lleva al cliente a esa URL tal como vino
