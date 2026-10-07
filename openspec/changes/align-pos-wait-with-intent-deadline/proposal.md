# Proposal

## Why

Cuando una intención de cobro presencial vence sin pagarse, el cajero puede recibir dos mensajes
distintos para la misma situación, y cuál le toca depende de la latencia de la red.

El backend le pide a Nave una intención con un plazo de 300 segundos. El bucle de espera del POS
corta a los 300 segundos también, con su propia constante. A los cinco minutos disparan los dos a la
vez: si gana el aviso de Nave, el cajero lee *"La intención de cobro expiró sin recibir el pago.
Generá un cobro nuevo"*; si gana el tope local, lee *"Se agotó el tiempo de espera. Verificá el
estado en la terminal antes de reintentar"*.

El segundo mensaje existe para cuando **no sabemos** qué pasó —se cortó la red, Nave no responde— y
manda al cajero a revisar el equipo. Acá no hace falta revisar nada: la intención venció. Con gente
esperando en la caja, esa diferencia importa.

De fondo hay algo peor: son dos números que hay que mantener iguales a mano, uno en el servidor y
otro en el navegador. El propio comentario del código dice que el tope *"debe acompañar al
`duration_time` que manda el backend"*. Hoy lo acompaña por coincidencia. Si alguien cambia uno, se
desincronizan en silencio y el síntoma —un mensaje equivocado al cajero— no lleva a la causa.

## What Changes

- **El plazo pasa a tener una sola fuente.** El POS deja de decidir por su cuenta cuánto esperar: usa
  el plazo con el que se creó la intención.
- **El tope local pasa a ser red de seguridad, no competencia.** Se concede un margen sobre el plazo
  de la intención, de modo que Nave alcance siempre a informar el vencimiento y el cajero reciba el
  mensaje que describe lo que pasó.

El tope local no desaparece: sigue siendo lo que evita una espera infinita cuando Nave no contesta.

## Capabilities

### New Capabilities

- `nave-pos-collection`: cómo el Punto de Venta de Odoo cobra con Nave de forma presencial —cómo
  espera la resolución de un cobro lanzado a la terminal o al QR, y qué entiende el cajero de lo que
  está pasando.

### Modified Capabilities

<!-- Ninguna: las cuatro capacidades existentes cubren el flujo online. -->

## Impact

- `pos_nave/models/pos_payment_method.py` — la creación de la intención y lo que devuelve al POS.
- `pos_nave/static/src/app/payment_nave.js` — el cálculo del tope de espera.
- Pruebas: `pos_nave/tests/`.
- Sin impacto en `payment_nave` ni en los flujos online.

### De dónde sale

Apareció al preparar el caso **C6** de la matriz, que prueba qué ve el cajero cuando una intención
expira. El pronóstico del plan para ese caso —*"se espera loop infinito"*— ya no aplica: el bucle
corta bien por vencimiento informado por Nave, por tope local, por errores de transporte repetidos y
por excepción inesperada. Lo que queda mal es cuál de los dos cortes gana.

Conviene resolverlo antes de ejecutar el resto del bloque C, porque son pruebas manuales con la
terminal física y habría que repetirlas si el código cambia después.
