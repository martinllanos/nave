# Spec Delta

## ADDED Requirements

### Requirement: Cancelar desde el punto de venta da de baja el cobro en la terminal

Cuando el cajero cancela un cobro presencial en curso, el punto de venta DEBE pedirle al proveedor
que lo dé de baja, para que la terminal deje de cobrarlo. Si el proveedor no confirma la baja, el
cajero DEBE recibir un aviso de que el cobro puede seguir activo en la terminal, con el motivo que
informó el proveedor.

El pedido de baja NO DEBE fallar por la forma en que el punto de venta informa el motivo.

#### Scenario: El proveedor confirma la baja

- **WHEN** el cajero cancela un cobro mientras la terminal espera la tarjeta
- **THEN** la terminal deja de cobrarlo
- **AND** la línea de pago queda en condiciones de reintentarse, sin avisos

#### Scenario: El proveedor rechaza el motivo informado

- **WHEN** el proveedor rechaza la baja por el motivo que se le informó
- **THEN** el punto de venta vuelve a pedir la baja sin informar motivo

#### Scenario: El proveedor no confirma la baja

- **WHEN** el proveedor no confirma la baja por otra causa
- **THEN** el cajero recibe un aviso de que el cobro puede seguir activo en la terminal, con el
  mensaje del proveedor
- **AND** el registro del servidor conserva la respuesta del proveedor
