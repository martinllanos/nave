# Design

## Context

Ver `proposal.md` — Why. Lo que condiciona el enfoque:

- **Cuándo aparece el botón.** Odoo muestra *Forzar terminación* mientras la línea está en `waiting`
  (el POS está creando la intención, hasta 30 s) o en `waitingCard` (el POS consulta el estado cada
  3 s, hasta 5,5 min), y también en `force_done`, un estado que este módulo nunca usa. Después de un
  desenlace la línea queda en `retry` o `done`, y el botón desaparece.
- **Qué hace el botón.** `sendForceDone` (`point_of_sale/.../payment_screen.js:606`) pone la línea
  en `done`, libera la terminal y, si la validación automática está activa, valida la venta. No
  avisa al medio de pago.
- **Por qué la línea volvió a reintentable en C9.** El cobro sigue en curso cuando se toca el
  botón: `line.pay()` espera lo que devuelve `send_payment_request`, y con eso fija el estado de la
  línea (`point_of_sale/.../pos_payment.js:72-89`). En C9, la baja hizo que esa espera terminara en
  `false`, y el core devolvió la línea a `retry` por encima del `done` del botón. Si el cajero
  hubiera validado antes, ese mismo mecanismo habría tocado una venta ya cerrada.
- **Cómo cortan hoy los problemas de red.** Con 3 fallos de transporte seguidos (unos 9 s) o un
  error de Nave, el polling se detiene y deja la línea en `retry`. Después de eso el botón ya no
  aparece.
- **Quién clasifica hoy.** El backend devuelve el estado crudo de la intención, y el navegador lo
  clasifica con `NAVE_STATUS`. El POS no tiene infraestructura de tests de JavaScript, así que esa
  clasificación sólo está vigilada por un test que lee el fuente.
- **Medios cubiertos.** Nave Point y QR interoperable usan la misma clase en el navegador, así que
  los dos tienen el mismo problema y reciben la misma corrección.

## Goals / Non-Goals

**Goals:**

- Que la decisión de dar un cobro de Nave por cobrado la tome Nave, y que esa decisión se pueda
  probar.
- Que un cobro confirmado al forzar la terminación siga el mismo camino que uno detectado por el
  polling: datos de la tarjeta, validación automática y ticket.

**Non-Goals:**

- Cambiar *Forzar terminación* para otros medios de pago.
- Ocultar el botón. Lo dibuja el core, y sigue haciendo falta para el caso en que Nave no responde.
- Resolver qué pasa cuando se corta la red durante un cobro (C8). Hoy el polling se detiene y la
  línea queda reintentable, lo que puede llevar a un segundo cobro si la terminal llegó a aprobar
  el primero. Es un riesgo distinto y se trata aparte.

## Decisions

### El botón adelanta la consulta y deja que el cobro termine por su camino normal

En una línea de Nave, *Forzar terminación* no marca nada por sí mismo: consulta a Nave en el acto
y, si el cobro ya tiene un desenlace, hace que el cobro en curso termine con ese desenlace. Si Nave
lo aprobó, el cobro termina como exitoso y el core lo da por cobrado y valida la venta como con
cualquier cobro aprobado. Si Nave lo rechazó, lo dio de baja o venció, el cobro termina como fallido,
con el aviso que corresponde, y la línea queda reintentable.

*Por qué*: es la única forma de que un cobro confirmado así sea indistinguible de uno detectado por
el polling. Se cargan los datos de la tarjeta, se respeta la validación automática y no hay un
segundo camino para mantener.

*Alternativa descartada — llamar al botón del core cuando Nave confirma*: marcaría la línea sin los
datos de la tarjeta. Además, el cobro en curso seguiría vivo, y su resolución podría volver a
validar la venta o reabrir la línea, que es el mecanismo que se vio en C9.

*Alternativa descartada — ocultar el botón en las líneas de Nave*: lo dibuja la plantilla del core
para todos los medios, y hace falta para el caso en que Nave no responde.

### Si Nave todavía no decidió, no cambia nada

Si Nave informa que todavía espera la tarjeta, el cobro sigue como estaba: el polling continúa y el
cajero recibe un aviso de que la terminal sigue esperando, de que Nave no confirmó ningún cobro y de
que puede esperar o cancelar. Si todavía no existe la intención, porque se está creando, el aviso
dice que el cobro todavía se está enviando a la terminal.

Un estado que el módulo no reconoce se trata igual que una espera: no se da nada por cobrado.

### Sin respuesta de Nave, el cajero confirma

Si la consulta no obtiene respuesta, el POS le pide al cajero que confirme que vio la aprobación en
la terminal o en el cupón. Si confirma, el cobro termina como exitoso, sin los datos de la tarjeta,
y el polling se detiene. Si no confirma, no cambia nada.

*Por qué*: es el uso legítimo del botón, y es el único caso en que el POS no tiene otra fuente que
el cajero. La confirmación explícita impide que se use por reflejo para salir de la espera, que es
lo que se reprodujo en C9.

Se usa el diálogo de confirmación que el POS ya trae (`ask`, de `make_awaitable_dialog`).

### Un cobro terminado no se reabre

Cuando el cobro termina, sea por el polling o por el botón, cualquier respuesta posterior sobre ese
mismo cobro se descarta: no cambia el estado de la línea ni muestra avisos.

*Por qué*: entre que se pide una consulta y llega la respuesta pueden pasar varios segundos, y una
consulta del polling puede estar en vuelo cuando se toca el botón. Sin esta regla, esa respuesta
tardía podría pisar el desenlace, que es el problema de C9 visto desde el otro lado.

### Sin cobro en curso, el desenlace se aplica a la línea

Si la línea muestra el botón pero no hay un cobro en curso en esta pantalla, por ejemplo porque se
recargó el POS con una línea esperando, se consulta igual a Nave y el desenlace se aplica a la línea
directamente. Un cobro aprobado se delega en el comportamiento del core, que ya sabe marcar la línea
y validar la venta. Es lo que hace `pos_razorpay` al montar la pantalla.

### La clasificación del desenlace pasa al backend

La consulta de estado devuelve, además del estado crudo, el desenlace ya clasificado: aprobado,
rechazado, dado de baja, vencido, en espera o desconocido. El polling y el botón usan esa
clasificación, y la del navegador (`NAVE_STATUS`) desaparece.

*Por qué*: el botón toma una decisión que mueve plata, y tiene que poder probarse. En Python se
prueba con los tests que ya existen; en el navegador no hay cómo. Además, el polling y el botón
tienen que clasificar igual, y una sola clasificación no puede desincronizarse.

*Consecuencia*: el test que lee el fuente del JS para vigilar `BLOCKED` se reemplaza por un test
del backend que comprueba que `BLOCKED` se clasifica como rechazo.

*Alternativa descartada — tests de JavaScript con Hoot*: es la infraestructura correcta para la
orquestación del navegador, pero armarla excede este cambio. La parte que se queda sin test
automatizado es la orquestación, y se verifica con la terminal.

### El aviso de espera lleva los datos de soporte

El aviso de *"la terminal sigue esperando"* reutiliza el armado de los demás avisos de desenlace,
con el bloque *"Para soporte"*. Si el cajero llama porque no entiende por qué el botón no hizo nada,
tiene el identificador de la intención a mano.

## Risks / Trade-offs

- **[Riesgo] Nave aprobó, pero la consulta falla en ese momento** → El cajero recibe la
  confirmación manual y puede marcarlo si vio la aprobación. Si no lo marca, el polling, que sigue
  corriendo, lo va a detectar en la próxima consulta.
- **[Riesgo] El cajero confirma una aprobación que no ocurrió** → Queda como hoy, pero tras una
  pregunta explícita y sólo cuando Nave no responde. Es el mismo margen que Odoo concede con
  cualquier terminal local.
- **[Riesgo] La orquestación del navegador no tiene test automatizado** → La decisión sí lo tiene,
  porque está en el backend. La orquestación se verifica con la terminal en cada uno de los
  desenlaces.
- **[Trade-off] Un estado desconocido bloquea el botón** → Es preferible a dar por cobrado algo que
  no se entiende. El estado queda en el log para agregarlo.

## Migration Plan

Ninguna. Se despliegan juntos el backend y el navegador del POS, y hay que recargar la pantalla del
POS para que tome el JavaScript nuevo. Si hiciera falta volver atrás, se revierte el módulo
completo: el navegador nuevo depende del desenlace clasificado que agrega el backend.

## Open Questions

- ¿Cuándo actúa el tope propio de la terminal, de unos 3 minutos? En C9 dio de baja la intención a
  los 189 s, y en la reprueba de C6 la dejó vencer a los 300 s. No cambia este diseño, porque los
  dos desenlaces ya se manejan, pero conviene preguntárselo a Nave.
