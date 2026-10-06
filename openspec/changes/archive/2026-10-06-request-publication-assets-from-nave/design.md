# Design

## Context

Ver `proposal.md` — Why. Lo que condiciona el enfoque:

- El destinatario es el cliente, no el equipo: el documento lo van a leer personas que no conocen la
  estructura del repositorio ni los nombres técnicos de los campos del manifiesto.
- Las respuestas llegarán por partes y en distintos momentos. El documento tiene que servir también
  como registro de qué se pidió, qué llegó y qué falta.
- `docs/` ya aloja la documentación funcional de Nave y el plugin de WooCommerce de referencia, así
  que es el lugar natural.
- Los pedidos pendientes a Nave vienen acumulándose en `tasks/correo_nave_n9.md`, que es donde viven
  los borradores de correo.

## Goals / Non-Goals

**Goals:**

- Que Nave pueda responder todo de una sola lectura, sin tener que preguntar qué significa cada
  pedido.
- Que quede claro para qué se usa cada dato, porque alguno —la licencia— tiene consecuencias que
  ellos deberían poder evaluar antes de responder.

**Non-Goals:**

- Modificar los manifiestos. Eso se hace cuando lleguen las respuestas, con los valores reales.
- Reabrir lo ya decidido: que la distribución es gratuita, que publica Nave y que el soporte se
  reparte por niveles.
- Cubrir el proceso de revisión de Odoo. Es posterior a la publicación y no depende de estos datos.

## Decisions

### Un documento en `docs/`, en Markdown

Vive en `docs/` junto al resto de la documentación del proyecto, en el mismo formato que todo lo
demás.

*Por qué no en `tasks/`*: ahí viven el plan de homologación y los borradores de correo, que son
material de trabajo interno. Este documento se entrega al cliente.

*Por qué Markdown y no un PDF o una planilla*: se versiona con el repositorio, así queda registro de
qué se pidió y cuándo, y se puede actualizar a medida que llegan las respuestas. Si Nave prefiere
otro formato, convertirlo es trivial; al revés no.

### Cada pedido explica para qué se usa el dato

Cada ítem lleva el campo o archivo concreto que va a alimentar y, cuando corresponde, la regla de
Odoo que lo exige.

*Por qué*: un pedido que dice sólo "necesitamos el correo de soporte" invita a mandar cualquier
casilla. Uno que dice que va a figurar públicamente en la ficha de Apps Store y que Odoo exige
respuesta en tiempo razonable para apps de pago, se responde con el criterio correcto.

### El inventario de manifiestos va en el documento, no aparte

Una tabla por módulo con lo que declara hoy y lo que pasaría a declarar.

*Por qué*: es lo que vuelve concreto el pedido. Ver que hoy dice `'author': 'Be onlyone'` y que va a
pasar a decir el nombre de ellos hace evidente por qué se pide el nombre legal exacto.

### Lo ya verificado se lista, no se omite

El documento abre diciendo qué requisitos ya cumplen los módulos.

*Por qué*: evita que pidan material que no hace falta, y muestra que el pedido está acotado a lo que
realmente falta.

### Lo decidido se registra como decidido, no se vuelve a preguntar

La distribución gratuita, el esquema de soporte por niveles y que publique Nave ya están resueltos.
El documento los enuncia como contexto, no como pregunta.

*Por qué*: un documento que vuelve a preguntar lo acordado da la impresión de que no se escuchó, y
alarga la respuesta.

### La licencia sí se pregunta, con su consecuencia

Siendo gratuita lo coherente es LGPL-3, pero el documento lo plantea igual y explica qué habilita:
que cualquiera redistribuya y modifique el módulo, frente a OPL-1 que no lo permite.

*Por qué*: es lo único de la dimensión legal que queda abierto, y la consecuencia no es obvia para
quien no trabaja con licencias de Odoo todos los días.

### El esquema de soporte se documenta aunque Odoo no lo exija

Odoo sólo obliga a dar soporte en las apps de pago, y ésta es gratuita. Aun así el documento pide el
canal de primer nivel y cómo se escala a tercero.

*Por qué*: el canal va a figurar en la ficha pública, así que tiene que ser uno que Nave quiera
atender. Y el escalamiento a tercer nivel nos involucra: conviene que esté escrito antes de que
llegue el primer caso y no después.

## Risks / Trade-offs

- **El documento queda desactualizado a medida que llegan las respuestas** → Lleva una columna de
  estado por ítem, de modo que actualizarlo sea anotar lo recibido y no reescribirlo.
- **Nave responde sólo una parte** → Los pedidos están agrupados de forma que cada bloque se pueda
  responder por separado, y marcados según si bloquean la publicación o no.

## Open Questions

- Si Nave prefiere recibirlo como correo en lugar de como documento adjunto. No cambia el contenido
  ni el trabajo: el texto se reusa tal cual en el cuerpo del correo.
