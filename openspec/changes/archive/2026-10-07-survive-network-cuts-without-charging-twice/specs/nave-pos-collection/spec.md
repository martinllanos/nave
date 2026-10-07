# Spec Delta

## MODIFIED Requirements

### Requirement: El punto de venta deja de esperar aunque el proveedor no conteste

El punto de venta DEBE dejar de esperar un cobro aunque el proveedor nunca informe un desenlace, y
DEBE avisarle al cajero que el resultado quedó sin confirmar.

Lo que termina la espera DEBE ser el plazo de la intención, con su margen, y no la falta de
respuesta. Un corte de conexión NO DEBE dar el cobro por terminado antes de ese plazo, porque la
terminal sigue cobrando aunque el punto de venta no pueda consultarla. Ninguna consulta al proveedor
DEBE quedar esperando sin límite.

#### Scenario: El proveedor deja de responder

- **WHEN** se lanza un cobro y el proveedor no informa ningún desenlace, ni siquiera el vencimiento
- **THEN** el punto de venta deja de esperar una vez vencido el plazo con su margen
- **AND** el cajero recibe un aviso que lo distingue de un vencimiento normal y le indica verificar
  el estado en la terminal antes de reintentar

#### Scenario: Se corta la conexión mientras la terminal espera la tarjeta

- **WHEN** el punto de venta pierde la conexión con un cobro en curso
- **THEN** el cobro sigue en curso hasta que vuelva la conexión o venza el plazo
- **AND** el cajero recibe un aviso de que el cobro puede seguir activo en la terminal y de que no lo
  cobre de nuevo

#### Scenario: Vuelve la conexión

- **WHEN** vuelve la conexión antes de que venza el plazo
- **THEN** el punto de venta resuelve el cobro con el desenlace que informa el proveedor, también si
  el cliente pagó durante el corte

#### Scenario: Una consulta no responde

- **WHEN** una consulta al proveedor no obtiene respuesta
- **THEN** el punto de venta la da por no respondida y sigue respetando el plazo
- **AND** forzar la terminación llega a preguntarle al cajero si vio la aprobación

#### Scenario: La línea de pago queda reintentable

- **WHEN** el punto de venta deja de esperar por cualquiera de los dos motivos
- **THEN** la línea de pago queda en condiciones de reintentarse, sin dar la venta por cobrada

## ADDED Requirements

### Requirement: Reintentar no le cobra dos veces al cliente

Antes de crear un cobro nuevo en una línea que ya tuvo una intención, el punto de venta DEBE
consultar al proveedor por esa intención y resolver la línea con lo que informe. NO DEBE crear un
cobro nuevo si la intención anterior se aprobó o sigue en curso, ni cuando no puede saberlo.

#### Scenario: El cobro anterior se aprobó sin que el punto de venta se enterara

- **WHEN** el cajero reintenta una línea cuya intención anterior el proveedor aprobó
- **THEN** la línea queda cobrada con los datos de la tarjeta
- **AND** no se crea un cobro nuevo

#### Scenario: El cobro anterior sigue en curso

- **WHEN** el cajero reintenta una línea cuya intención anterior todavía espera la tarjeta
- **THEN** el punto de venta retoma la espera de esa intención, sin crear otra

#### Scenario: El cobro anterior terminó sin cobrarse

- **WHEN** el cajero reintenta una línea cuya intención anterior se rechazó, se dio de baja o venció
- **THEN** el punto de venta crea un cobro nuevo

#### Scenario: No se puede saber qué pasó con el cobro anterior

- **WHEN** el cajero reintenta una línea y el proveedor no responde por la intención anterior
- **THEN** no se crea un cobro nuevo
- **AND** el cajero recibe un aviso de que el cobro anterior pudo haberse cobrado y de que espere a
  que vuelva la conexión
