# Spec Delta

## ADDED Requirements

### Requirement: El cajero entiende qué pasó y qué puede hacer

Cuando un cobro no se completa, el aviso que recibe el cajero DEBE describir la situación en sus
términos e indicarle qué hacer a continuación.

El aviso NO DEBE mostrar identificadores internos del proveedor ni de la integración, y NO DEBE
afirmar una causa que el punto de venta no pueda distinguir.

#### Scenario: La tarjeta no tiene fondos

- **WHEN** el cobro se rechaza porque la tarjeta no tiene saldo suficiente
- **THEN** el cajero recibe un aviso de que el pago fue rechazado y de que puede probar con otra
  tarjeta
- **AND** no se le indica contactar al proveedor ni se presenta como un problema de seguridad

#### Scenario: El proveedor informa el motivo en lenguaje llano

- **WHEN** el proveedor informa un motivo legible del rechazo
- **THEN** ese motivo acompaña al aviso

#### Scenario: El proveedor sólo informa un código

- **WHEN** el único motivo disponible es un identificador técnico
- **THEN** el cajero recibe la descripción de la situación, sin el identificador

#### Scenario: La intención se dio de baja

- **WHEN** la intención se da de baja, sea por una cancelación en la terminal, por vencimiento o
  porque el proveedor no pudo avisarle al equipo
- **THEN** el aviso dice que el cobro ya no está disponible y que puede generarse uno nuevo
- **AND** no afirma cuál de esas causas fue

#### Scenario: El cobro queda reintentable

- **WHEN** el cobro termina en cualquiera de estas situaciones
- **THEN** la línea de pago queda en condiciones de reintentarse, sin dar la venta por cobrada
