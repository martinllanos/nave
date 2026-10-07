# Design

## Context

Ver `proposal.md` — Why. Lo que condiciona el enfoque:

- La intención la crea el backend (`nave_send_payment_request`) y devuelve al POS la respuesta de
  Nave tal cual, de la que el JS usa `data.id`. El plazo que se pidió no viaja en esa respuesta.
- Hay un segundo canal hacia el POS: `_load_pos_data_fields` ya lleva `nave_terminal_id` y
  `nave_fast_payments` al frontend cuando abre la sesión.
- El bucle de espera corta por cuatro motivos distintos —desenlace informado por Nave, vencimiento
  informado por Nave, tope local, errores de transporte repetidos— y cada uno tiene su mensaje. Eso
  ya funciona; lo que falla es el orden entre dos de ellos.

## Goals / Non-Goals

**Goals:**

- Que el plazo se declare una sola vez y el resto se derive.
- Que el mensaje que recibe el cajero corresponda a lo que realmente pasó.

**Non-Goals:**

- Hacer configurable el plazo del cobro presencial. Cinco minutos es razonable con el cliente parado
  frente a la caja, y agregar un ajuste ahora mezcla dos cosas. Si hace falta, se hace después y este
  cambio lo deja preparado, porque el plazo pasa a estar en un solo lugar.
- Tocar los otros tres motivos de corte ni sus mensajes.

## Decisions

### El plazo viaja en la respuesta de la intención, no en la configuración

El backend agrega el plazo a lo que devuelve al crear la intención, junto al `id`.

*Por qué no por `_load_pos_data_fields`*: esos datos se cargan al abrir la sesión del POS y describen
la **configuración** del método de pago. El plazo describe **esta** intención: es el que se usó al
crearla. Si mañana el plazo dependiera del importe, del medio o de un ajuste por compañía, el valor
cargado al abrir la sesión ya no sería el correcto, y el desfasaje volvería por otra puerta.

*Por qué no que el JS lo lea de la intención consultando a Nave*: agregaría una llamada extra al
inicio de cada cobro para un dato que el backend ya tiene en la mano.

### El margen es un porcentaje con un piso, no un número suelto

El tope local se calcula como el plazo de la intención más un margen; el margen acompaña al plazo en
lugar de ser una constante aparte.

*Por qué*: con un plazo de cinco minutos, treinta segundos alcanzan de sobra para que llegue el aviso
de Nave. Pero si alguien baja el plazo a treinta segundos, un margen fijo de treinta sería el doble
del plazo, y el tope local dejaría de ser una red para volverse una espera larga sin sentido. Un
margen proporcional se adapta; un piso evita que con plazos muy cortos quede por debajo de lo que
tarda una consulta.

### El tope local conserva su mensaje, que ahora sí es excepcional

El aviso de *"verificá el estado en la terminal"* se mantiene tal cual. Lo que cambia es cuándo
aparece: hasta ahora competía con el vencimiento normal, y a partir de este cambio queda reservado
para cuando Nave efectivamente no contestó.

*Por qué importa*: un aviso que aparece en situaciones normales deja de leerse. Que sólo salga cuando
hay algo raro es lo que lo hace útil.

## Risks / Trade-offs

- **El backend podría devolver la respuesta sin el plazo**, por ejemplo si cambia el formato → el JS
  conserva su valor actual como respaldo, de modo que un cobro nunca quede sin tope de espera.
- **El margen se vuelve otro número que alguien puede tocar** → Pero es un solo número y su efecto es
  acotado: alargar o acortar la red de seguridad. El dato que importa, el plazo, queda en un lugar.

## Migration Plan

Ninguna. Afecta sólo a cobros nuevos; los que estén en curso al actualizar siguen con el tope que ya
tenían en la pestaña abierta.
