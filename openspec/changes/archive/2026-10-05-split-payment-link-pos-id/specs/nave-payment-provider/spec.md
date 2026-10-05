# Spec Delta

## Purpose

Define cómo el proveedor de pagos Nave identifica al comercio ante la API —el `pos_id` que viaja en
`seller.pos_id` de cada intención de pago— y cómo se configura esa identidad, dado que Nave asigna un
identificador distinto por medio de cobro.

## ADDED Requirements

### Requirement: Identidad del comercio por medio de cobro

El proveedor DEBE resolver el `pos_id` que envía en una intención de pago a partir del **medio de
cobro** de esa intención, porque Nave asigna un identificador distinto a cada medio y rechaza con
`409 INVALID_POS` toda intención cuyo `pos_id` pertenezca a otro.

El proveedor DEBE admitir que se configure un `pos_id` por cada medio de cobro online que soporte:
tienda de e-commerce y link de pago.

#### Scenario: Cobro desde el checkout del sitio

- **WHEN** se genera una intención de pago para una compra del e-commerce
- **THEN** la intención viaja con el `pos_id` configurado para la tienda de e-commerce

#### Scenario: Cobro desde un link de pago

- **WHEN** se genera un link de pago desde una factura o un pedido de venta
- **THEN** la intención viaja con el `pos_id` configurado para el medio link de pago
- **AND** ese `pos_id` es independiente del configurado para la tienda de e-commerce

### Requirement: Compatibilidad con una única identidad configurada

El proveedor DEBE seguir operando cuando sólo está configurado el `pos_id` de la tienda de
e-commerce, usándolo para todos los medios de cobro online. Esto preserva el comportamiento de las
instalaciones existentes, que fueron configuradas cuando el proveedor admitía un solo identificador,
y contempla a los comercios a los que Nave entregó el mismo `pos_id` para ambos medios.

#### Scenario: Instalación sin el identificador de link de pago

- **WHEN** se genera un link de pago y no hay un `pos_id` configurado para ese medio
- **THEN** la intención viaja con el `pos_id` de la tienda de e-commerce
- **AND** el link se genera sin requerir configuración adicional

#### Scenario: Actualización de una instalación existente

- **WHEN** se actualiza el módulo en una instalación que ya cobraba con un único `pos_id`
- **THEN** los cobros existentes y los nuevos siguen funcionando sin intervención del administrador

### Requirement: Configuración visible de las identidades

La configuración del proveedor DEBE exponer cada `pos_id` con una etiqueta que indique a qué medio
de cobro corresponde, y DEBE indicar de dónde obtenerlo, porque el administrador recibe de Nave
varios identificadores con el mismo formato y cargarlos cruzados produce un rechazo que no explica
cuál es el campo equivocado.

#### Scenario: Administrador configura el proveedor

- **WHEN** un administrador abre la configuración del proveedor Nave
- **THEN** ve un campo por cada medio de cobro online, identificado por medio
- **AND** la ayuda de cada campo indica desde dónde se obtiene su valor

### Requirement: Error de identidad diagnosticable

Cuando Nave rechaza una intención por un `pos_id` que no corresponde al medio, el proveedor DEBE
registrar el motivo de forma que permita identificar qué medio y qué identificador se usaron, porque
el mensaje de Nave no dice cuál de los configurados está mal.

#### Scenario: Identificador cruzado entre medios

- **WHEN** Nave responde `409 INVALID_POS` a una intención
- **THEN** queda registrado el medio de cobro de esa intención y el identificador enviado
