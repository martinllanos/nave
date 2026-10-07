# Proposal

## Why

Un corte de red durante un cobro presencial puede terminar con el cliente pagando dos veces. Lo
verificamos con la terminal y pagos reales en C8 (`tasks/plan_homologacion_nave.md` §3.34, evidencia
en `docs/homologacion/evidencias/C8/`).

El defecto depende de cómo falla la red:

- **Si la consulta a Nave falla al instante**, el punto de venta da el cobro por fallido a los ~9
  segundos y deja la línea para reintentar, mientras la terminal sigue cobrando. En la tercera
  corrida, Nave aprobó $150 veintiocho segundos después y Odoo nunca se enteró. El cajero no tiene
  forma de registrar esa aprobación: una línea para reintentar no ofrece *Forzar terminación*.
  *Volver a intentar* crea un cobro nuevo, y cobrar en efectivo lleva al mismo resultado.
- **Si la consulta queda colgada**, por ejemplo con el cable de red desenchufado, el punto de venta
  espera sin límite y sin avisar, aun pasado el plazo de la intención. Si la red vuelve, se entera
  del desenlace real. Si no vuelve, queda trabado, y *Forzar terminación* tampoco responde porque
  su consulta a Nave se cuelga igual.

En los dos casos el problema es el mismo: el punto de venta deja de saber qué pasó con un cobro que
quizás sí se cobró, y nada impide cobrarlo de nuevo.

## What Changes

- **Un corte de red no termina el cobro: sólo lo termina el plazo de la intención.** Mientras no
  haya conexión, el punto de venta sigue esperando y le avisa al cajero que el cobro puede seguir
  activo en la terminal y que no lo cobre de nuevo. Cuando vuelve la conexión, se entera del
  desenlace real.
- **Ninguna consulta a Nave queda esperando sin límite.** Una consulta que no responde a tiempo
  cuenta como falta de respuesta. Así el plazo se respeta y *Forzar terminación* siempre llega a
  preguntarle al cajero.
- **Antes de cobrar de nuevo, el punto de venta revisa el cobro anterior.** Si la línea ya tuvo una
  intención, *Volver a intentar* le pregunta a Nave por ella antes de crear otra:
  - si se aprobó, la línea queda cobrada con los datos de la tarjeta y no se crea un cobro nuevo;
  - si sigue en curso, se retoma la espera;
  - si se rechazó, se dio de baja o venció, se crea el cobro nuevo como hasta ahora;
  - si Nave no responde, no se crea un cobro nuevo a ciegas: se avisa y la línea queda como estaba.

## Capabilities

### New Capabilities

<!-- Ninguna. -->

### Modified Capabilities

- `nave-pos-collection`: el requisito de dejar de esperar cuando el proveedor no contesta se
  precisa. Un corte de conexión no adelanta el fin del cobro, y ninguna consulta espera sin límite.
  Se agrega que reintentar un cobro no puede cobrarle dos veces al cliente.

## Impact

- `pos_nave/static/src/app/payment_nave.js`: el polling, el tiempo máximo de cada consulta, el aviso
  de falta de conexión y la revisión del cobro anterior al reintentar.
- Sin cambios en el backend: la consulta de estado y la clasificación del desenlace ya existen y
  tienen tests.
- Verificación con la terminal: el pedido 104 del punto de venta de producción quedó abierto con la
  línea para reintentar y $150 aprobados en Nave. Es el caso real de la corrección: al reintentarlo,
  el punto de venta tiene que encontrar el pago aprobado.
