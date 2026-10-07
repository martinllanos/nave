# Spec Delta

## MODIFIED Requirements

### Requirement: Configuración visible de las identidades

La configuración del proveedor DEBE exponer cada `pos_id` con una etiqueta que indique a qué medio
de cobro corresponde, y DEBE indicar de dónde obtenerlo, porque el administrador recibe de Nave
varios identificadores con el mismo formato y cargarlos cruzados produce un rechazo que no explica
cuál es el campo equivocado.

Indicar de dónde obtenerlo DEBE incluir cómo reconocer, en el archivo de identificadores que entrega
Nave, la fila que corresponde a ese medio de cobro. Nombrar sólo la sección del portal no alcanza:
el archivo tiene una fila por medio y por tienda, y varias pueden parecerse.

#### Scenario: Administrador configura el proveedor

- **WHEN** un administrador abre la configuración del proveedor Nave
- **THEN** ve un campo por cada medio de cobro online, identificado por medio
- **AND** la ayuda de cada campo indica desde dónde se obtiene su valor

#### Scenario: Administrador busca el identificador de la tienda online

- **WHEN** un administrador abre la ayuda del identificador de la tienda online
- **THEN** la ayuda indica de dónde descargar el archivo de identificadores de Nave
- **AND** indica que la fila es la del medio de cobro de e-commerce cuyo nombre coincide con el de la
  tienda dada de alta en Nave

#### Scenario: Administrador busca el identificador del link de pago

- **WHEN** un administrador abre la ayuda del identificador de los links de pago
- **THEN** la ayuda indica que la fila es la del medio de cobro de link de pago del mismo archivo

### Requirement: Error de identidad diagnosticable

Cuando Nave rechaza una intención por un `pos_id` que no corresponde al medio, el proveedor DEBE
registrar el motivo de forma que permita identificar qué medio y qué identificador se usaron, porque
el mensaje de Nave no dice cuál de los configurados está mal.

El rechazo DEBE reconocerse por el motivo que informa Nave y no por el código HTTP, porque la API no
responde con el código que muestra su documentación.

#### Scenario: Identificador cruzado entre medios

- **WHEN** Nave rechaza una intención porque su `pos_id` pertenece a otro medio de cobro
- **THEN** queda registrado el medio de cobro de esa intención y el identificador enviado
