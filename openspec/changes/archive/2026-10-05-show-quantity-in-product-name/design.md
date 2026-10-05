# Design

## Context

Ver `proposal.md` — Why. Lo que condiciona el enfoque:

- `nave_product_entry` arma cada entrada del detalle y hoy antepone la cantidad a la descripción
  cuando no es entera. El nombre se recorta a 100 caracteres y la descripción a 150.
- Nave renderiza del detalle sólo `{cantidad}x {nombre}` y el importe. Comprobado leyendo el DOM del
  checkout, no deducido de la documentación, que no dice nada al respecto.
- El cron de conciliación barre por dominio todas las transacciones Nave pendientes de la base. Eso
  es correcto y es lo que tiene que hacer en producción: el problema es cómo lo verifica el test.

## Goals / Non-Goals

**Goals:**

- Que el dato quede donde está comprobado que el cliente lo lee.
- Que una corrida roja de la suite signifique que el código está mal.

**Non-Goals:**

- Cambiar el dominio del cron. Barrer toda la base es lo que lo hace útil como red ante un webhook
  perdido.
- Cambiar los importes ni la correspondencia entre detalle e importe, que ya están bien.

## Decisions

### La cantidad se antepone al nombre

El nombre pasa a ser `0,15 kg Granel por kilo`, con la cantidad primero para que sobreviva al recorte
de 100 caracteres y al truncado por CSS que hace el checkout.

*Por qué el nombre*: es el único campo del detalle que Nave muestra. La descripción no se renderiza
en ninguna de sus pantallas.

*Por qué se deja también en la descripción*: no estorba, cuesta nada, y Nave podría mostrarla en el
comprobante descargable o en su panel, que no pudimos inspeccionar. Si algún día la muestra, el dato
ya está ahí.

*Qué pasa con el `1x` que antepone Nave*: el cliente va a leer `1x 0,15 kg Granel por kilo`. Es
redundante pero no engañoso, y es la única forma de que vea la cantidad real sin que Nave acepte
decimales. La alternativa —callar la cantidad— es peor: hoy lee `1x Granel por kilo` y se queda
pensando que compró uno.

### El test del cron sólo juzga lo suyo

El test deja de afirmar que el cron no llamó a nadie y pasa a afirmar que no consultó **su**
transacción, mirando las URL con las que se lo invocó.

*Por qué no limpiar la base antes del test*: el test correría en una base que no es la que la gente
tiene, y volvería a fallar en cuanto alguien deje una transacción pendiente. Además borrar datos
desde un test es un arma peligrosa en una base de desarrollo.

*Por qué no acotar el dominio del cron a las transacciones del test*: eso cambiaría el código para
acomodar la prueba, y el barrido completo es justamente lo que hace útil al cron.

*Qué se gana*: el test pasa a verificar la regla que le importa —una transacción reciente no se
consulta— sin pronunciarse sobre transacciones que no creó y que no son asunto suyo.

## Risks / Trade-offs

- **El nombre se vuelve más largo y el checkout lo trunca** → Por eso la cantidad va al principio: lo
  que se pierde al truncar es el final del nombre del producto, no el dato nuevo.
- **La redundancia `1x 0,15 kg`** → Asumida a conciencia: Nave antepone la cantidad que le mandamos y
  no hay forma de suprimirla.
- **El test deja de detectar que el cron consulte una transacción ajena** → Nunca fue su trabajo; los
  tests que cubren a qué transacciones alcanza el cron son los que preparan transacciones viejas y
  verifican que sí se consultan.

## Migration Plan

Ninguna. Afecta sólo al texto que viaja en intenciones nuevas; las ya creadas no se tocan.
