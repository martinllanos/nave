# nave-pos-collection Specification

## Purpose

Define cómo el Punto de Venta de Odoo cobra con Nave de forma presencial: cómo espera la resolución
de un cobro lanzado a la terminal o al QR, cuándo deja de esperar y qué entiende el cajero de lo que
está pasando, para que pueda decidir qué hacer sin ir a revisar el equipo.

## Requirements

### Requirement: El punto de venta espera lo que dura la intención

El tiempo que el punto de venta espera la resolución de un cobro DEBE derivarse del plazo con el que
se creó esa intención, y no de un valor propio que haya que mantener sincronizado a mano.

La espera DEBE conceder un margen sobre ese plazo, para que el proveedor alcance a informar el
vencimiento antes de que el punto de venta deje de esperar por su cuenta.

#### Scenario: La intención vence sin cobrarse

- **WHEN** se lanza un cobro a la terminal y nadie paga hasta que la intención vence
- **THEN** el cajero recibe el aviso de que la intención expiró y que debe generar un cobro nuevo
- **AND** no se le pide que verifique el estado en la terminal, porque no hay nada que verificar

#### Scenario: Cambia el plazo de la intención

- **WHEN** se cobra con un plazo de intención distinto al anterior
- **THEN** el punto de venta espera conforme a ese plazo, sin que haya que tocar nada más

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

### Requirement: El cajero entiende qué pasó y qué puede hacer

Cuando un cobro no se completa, el aviso que recibe el cajero DEBE describir la situación en sus
términos e indicarle qué hacer a continuación.

El motivo DEBE tomarse del pago cuando lo hay, y no de la intención de cobro. El aviso DEBE usar el
mensaje que el proveedor publica para ese motivo y NO DEBE presentar un código como si fuera la
explicación. NO DEBE afirmar una causa que el proveedor no haya informado.

#### Scenario: La tarjeta no tiene fondos

- **WHEN** el cobro se rechaza porque la tarjeta no tiene saldo suficiente
- **THEN** el cajero recibe un aviso de que la tarjeta no tiene fondos suficientes y de que puede
  reintentar o cobrar con otro medio
- **AND** no se le indica contactar al proveedor ni se presenta como un problema de seguridad

#### Scenario: La intención informa un desenlace distinto al del pago

- **WHEN** el pago informa un motivo de rechazo y la intención informa otro, como los intentos
  excedidos
- **THEN** el aviso explica el motivo del pago

#### Scenario: El proveedor informa un motivo que no está en su catálogo

- **WHEN** el motivo informado no tiene un mensaje publicado por el proveedor
- **THEN** el cajero recibe la descripción de la situación y qué hacer, sin motivo

#### Scenario: La intención se dio de baja con un motivo conocido

- **WHEN** la intención se da de baja y el proveedor informa por qué, como una cancelación en la
  terminal
- **THEN** el aviso dice ese motivo y que puede generarse un cobro nuevo

#### Scenario: La intención se dio de baja sin motivo

- **WHEN** la intención se da de baja y el proveedor no informa por qué
- **THEN** el aviso dice que el cobro ya no está disponible y que puede generarse uno nuevo
- **AND** no afirma una causa

#### Scenario: El cobro queda reintentable

- **WHEN** el cobro termina en cualquiera de estas situaciones
- **THEN** la línea de pago queda en condiciones de reintentarse, sin dar la venta por cobrada

### Requirement: Lo que pide la soporte queda a mano

Cuando un cobro no se completa, el aviso DEBE incluir, separados de la explicación y rotulados como
datos para soporte, el código que informó el proveedor y los identificadores del cobro.

El desenlace de cada cobro DEBE quedar registrado en el servidor, con su estado, su motivo y sus
identificadores, aunque el cajero cierre el aviso.

#### Scenario: El cajero llama a soporte después de un rechazo

- **WHEN** un cobro se rechaza y el cajero necesita consultarlo con la soporte del proveedor
- **THEN** el aviso le muestra, bajo un rótulo de soporte, el código tal como lo informó el
  proveedor y los identificadores del pago y de la intención

#### Scenario: El aviso ya se cerró

- **WHEN** el cajero cerró el aviso y hay que averiguar qué pasó con un cobro
- **THEN** el registro del servidor tiene el estado, el motivo y los identificadores de ese cobro

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
- **AND** si lo confirma, el cobro queda cobrado; si no lo confirma, no se da por cobrado
- **AND** mientras el cajero no responde, el punto de venta no resuelve el cobro por su cuenta

#### Scenario: Una respuesta llega después de dar el cobro por terminado

- **WHEN** un cobro quedó cobrado y después llega otra respuesta sobre ese mismo cobro
- **THEN** el cobro sigue cobrado y el cajero no recibe avisos sobre él

#### Scenario: Otros medios de pago

- **WHEN** el cajero fuerza la terminación de un pago que no es de Nave
- **THEN** el punto de venta se comporta como lo hacía antes de este cambio

### Requirement: El método de pago indica de dónde sale su identificador

La configuración de un método de pago presencial de Nave DEBE indicar de dónde obtener el `pos_id`
del dispositivo y cómo reconocer su fila en el archivo de identificadores que entrega Nave, porque
cada terminal y cada QR tienen el suyo y un identificador cruzado hace que Nave rechace el cobro sin
decir cuál está mal.

#### Scenario: Administrador configura una terminal

- **WHEN** un administrador configura un método de pago con una terminal Nave Point
- **THEN** la ayuda del identificador indica de dónde descargar el archivo de identificadores de Nave
- **AND** indica que la fila es la de la terminal, reconocible por el número de serie impreso en el
  equipo

#### Scenario: Administrador configura un QR

- **WHEN** un administrador configura un método de pago con un QR
- **THEN** la ayuda indica que la fila es la del QR, reconocible por su nombre junto con el del local
  al que pertenece

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

### Requirement: La línea en espera dice qué espera el cobro

Mientras un cobro presencial espera al cliente, la línea de pago DEBE decirle al cajero qué tiene
que hacer el cliente: apoyar o insertar la tarjeta en la terminal, o escanear el QR.

Con el QR fijo, el cliente tiene que escanear después de que el cobro exista. Si escanea antes, la
billetera le pide el monto y el pago queda fuera del punto de venta, sin ningún aviso. Que la línea
diga que se espera el escaneo le marca al cajero ese momento.

#### Scenario: Cobro con el QR fijo

- **WHEN** un cobro con el QR fijo del local queda esperando al cliente
- **THEN** la línea de pago dice que espera el escaneo del QR

#### Scenario: Cobro con la terminal

- **WHEN** un cobro con la terminal queda esperando al cliente
- **THEN** la línea de pago dice que espera la tarjeta, como hasta ahora
