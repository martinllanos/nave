# Spec Delta

## Purpose

Define cómo se reciben los avisos que Nave manda a la URL de notificación: cuáles se aplican, cuáles
se acusan sin aplicar y cuáles se dejan para que Nave los reintente.

## ADDED Requirements

### Requirement: Un aviso ajeno al sitio se acusa sin error

Cuando un aviso de Nave no corresponde a ninguna transacción del sitio, el sitio DEBE acusarlo como
recibido, para que Nave no lo reintente, y NO DEBE registrarlo como un error.

Nave manda a la misma URL los avisos de todos los pagos del comercio, incluidos los del punto de
venta. Tratar esos avisos como fallas llena el registro de errores falsos, que esconden los
verdaderos, y le devuelve a Nave una falla por cada venta presencial.

#### Scenario: Pago aprobado en el punto de venta

- **WHEN** Nave avisa un pago cuya referencia es la de un cobro del punto de venta
- **THEN** el sitio acusa el aviso como recibido
- **AND** el registro del servidor lo anota como un aviso que no corresponde al sitio, sin error
- **AND** ninguna transacción del sitio cambia

#### Scenario: Referencia inexistente

- **WHEN** llega un aviso con una referencia que no existe en el sitio
- **THEN** el sitio acusa el aviso como recibido y no cambia ninguna transacción

### Requirement: Una falla al verificar el pago no cierra la transacción

Si el sitio no puede consultarle a Nave el estado del pago avisado, la transacción DEBE quedar en el
estado en que estaba, y el sitio DEBE responder de modo que Nave reintente el aviso.

Una falla de red pasajera no dice nada del pago, que pudo haberse cobrado. Cerrar la transacción por
esa falla deja un cobro real sin registrar, y nada vuelve a revisarlo.

#### Scenario: Nave no responde a la consulta del pago

- **WHEN** llega un aviso de una transacción pendiente y la consulta del pago a Nave falla
- **THEN** la transacción sigue pendiente
- **AND** el sitio responde con una falla para que Nave reintente el aviso

#### Scenario: La conciliación periódica no puede consultar el pago

- **WHEN** la conciliación periódica revisa una transacción pendiente y la consulta del pago falla
- **THEN** la transacción sigue pendiente y se vuelve a revisar en la corrida siguiente

#### Scenario: El reintento de Nave encuentra la red repuesta

- **WHEN** Nave reintenta el aviso y la consulta del pago responde aprobado
- **THEN** la transacción queda pagada como con cualquier aviso aprobado

### Requirement: Una falla del sitio no deja el aviso aplicado a medias

Cuando el sitio responde con una falla para que Nave reintente un aviso, NO DEBE quedar aplicado
ningún cambio de ese aviso.

El reintento tiene que encontrar la transacción como estaba antes del primer intento. Si quedara a
medio aplicar, el reintento partiría de un estado que ningún aviso produjo.

#### Scenario: Falla inesperada al procesar un aviso

- **WHEN** el procesamiento de un aviso falla por una causa del sitio, después de haber empezado a
  modificar la transacción
- **THEN** el sitio responde con una falla para que Nave reintente
- **AND** la transacción queda como estaba antes del aviso
