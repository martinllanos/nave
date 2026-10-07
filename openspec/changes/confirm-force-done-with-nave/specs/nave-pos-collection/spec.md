# Spec Delta

## ADDED Requirements

### Requirement: Forzar la terminación no da por cobrado lo que Nave no cobró

Cuando el cajero fuerza la terminación de un cobro presencial de Nave, el punto de venta DEBE
consultar el estado del cobro y resolverlo según lo que informe Nave. NO DEBE dar por cobrada una
venta que Nave no confirmó, salvo que Nave no responda y el cajero confirme explícitamente que vio
la aprobación.

Una vez que un cobro quedó cobrado, ninguna respuesta posterior DEBE devolverlo a reintentable.

#### Scenario: La terminal todavía espera la tarjeta

- **WHEN** el cajero fuerza la terminación mientras la terminal espera la tarjeta
- **THEN** el cobro no se da por cobrado y la venta no puede validarse con ese pago
- **AND** el cajero recibe un aviso de que la terminal sigue esperando la tarjeta y de que puede
  esperar o cancelar el cobro

#### Scenario: El cobro todavía se está enviando a la terminal

- **WHEN** el cajero fuerza la terminación antes de que el cobro haya llegado a la terminal
- **THEN** el cobro no se da por cobrado y el cajero recibe un aviso de que todavía se está enviando

#### Scenario: Nave ya aprobó el cobro

- **WHEN** el cajero fuerza la terminación de un cobro que Nave aprobó
- **THEN** el cobro queda cobrado con los datos de la tarjeta, igual que si el punto de venta se
  hubiera enterado por su cuenta

#### Scenario: Nave rechazó el cobro, lo dio de baja o venció

- **WHEN** el cajero fuerza la terminación de un cobro que Nave rechazó, dio de baja o dejó vencer
- **THEN** el cajero recibe el aviso que corresponde a ese desenlace y la línea queda reintentable,
  sin dar la venta por cobrada

#### Scenario: Nave no responde

- **WHEN** el cajero fuerza la terminación y no se puede consultar a Nave
- **THEN** el punto de venta le pide que confirme que vio la aprobación en la terminal o en el
  cupón antes de dar el cobro por cobrado
- **AND** si no lo confirma, el cobro no se da por cobrado

#### Scenario: Una respuesta llega después de dar el cobro por terminado

- **WHEN** un cobro quedó cobrado y después llega otra respuesta sobre ese mismo cobro
- **THEN** el cobro sigue cobrado y el cajero no recibe avisos sobre él

#### Scenario: Otros medios de pago

- **WHEN** el cajero fuerza la terminación de un pago que no es de Nave
- **THEN** el punto de venta se comporta como lo hacía antes de este cambio
