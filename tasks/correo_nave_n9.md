# Borradores de correo a Nave

## Borrador 5 — datos para publicar en Odoo Apps (2026-10-06)

> Correo **nuevo**, con el documento `docs/requerimientos_publicacion_odoo_apps.md` adjunto.
> Va **separado del borrador 4** a propósito: aquel pide habilitaciones técnicas urgentes a
> `integraciones@` para poder terminar la homologación, y esto es material de marca y decisiones de
> producto, que probablemente lee otra persona. Mezclarlos diluiría los dos.

---

**Asunto:** Material necesario para publicar los módulos de Odoo — Be onlyone

Hola, buen día.

Les escribo desde **Be onlyone**. Como quedamos, los tres módulos de integración con Odoo se van a
publicar en **apps.odoo.com desde la cuenta de ustedes**, figurando Nave como autor y con
distribución gratuita.

Para eso necesitamos material y datos que sólo pueden aportar ustedes: el logo y el icono oficiales,
los textos de la ficha, el canal de soporte que quieran publicar y algunos datos de identidad que
aparecen públicamente.

Les adjunto un documento que lo detalla todo, agrupado por tema. Cada pedido indica para qué se usa y
si bloquea la publicación, así pueden responder por partes sin esperar a tenerlo completo.

Dos aclaraciones que están en el documento y conviene adelantar:

- Si les resulta más cómodo, podemos redactar nosotros los textos y preparar las capturas, y
  enviárselos para que los aprueben.
- Hay un punto a confirmar sobre la licencia. Hoy los módulos son **LGPL-3**, que es lo habitual para
  una app gratuita y permite que cualquiera los redistribuya o modifique. Si prefieren restringir
  eso, conviene que lo hablemos, porque afecta el esquema completo.

Quedamos a disposición para cualquier duda.

Saludos cordiales,

**Martín Llanos**
Be onlyone
martinllanos@onlyone.com.ar

---

## Borrador 4 — los dos bloqueos que quedan (2026-10-05)

> Correo **nuevo** a `integraciones@navenegocios.com`, con copia a Jonathan Castillo.
> Mismo criterio que el borrador 3: pedidos puntuales, sin explicar de más. Van los dos juntos
> porque son lo único que falta para terminar la homologación, y cada uno lleva la respuesta
> textual de la API, que es más difícil de desatender que una consulta en abstracto.
> Ver `plan_homologacion_nave.md` §3.21 y §3.24.

---

**Asunto:** Dos habilitaciones pendientes — Be onlyone, CUIT 20-26253453-8

Hola, buen día.

Les escribo desde **Be onlyone** (CUIT **20-26253453-8**). Tenemos la integración funcionando en
sandbox y nos quedan dos cosas por habilitar de su lado para poder terminar las pruebas.

### 1. El `pos_id` de LINK DE PAGO del comercio de prueba

Sólo contamos con el `pos_id` de tienda. Al generar un link de pago con él, la API responde:

```
POST /api/payment_request/payment_link
400 — {"code": "invalid_pos", "message": "Given POS is for a different payment type"}
```

El mismo `pos_id` funciona correctamente contra `/api/payment_request/ecommerce`, así que entendemos
que falta el identificador del medio **link de pago**. ¿Nos lo pueden proporcionar para el comercio
de sandbox?

### 2. Habilitación de devoluciones por API

Necesitamos **habilitar las devoluciones** para nuestras credenciales. Al invocar

```
DELETE /api/payments/{payment_id}
```

con un token válido, la API responde:

```
403 — "User is not authorized to access this resource because no identity-based policy
       allows the execute-api:Invoke action"
```

Por lo que entendemos, el recurso existe y a nuestro `client_id` le falta el permiso sobre ese
método. ¿Nos lo pueden habilitar, en sandbox y en producción?

Dos consultas que acompañan a este segundo pedido:

1. El endpoint no figura en la documentación del DevPortal. ¿Sigue siendo el vigente para
   devoluciones, o hay otro que debamos usar?
2. ¿La devolución admite importe parcial, o es siempre por el total del pago?

Quedamos a la espera. Muchas gracias.

Saludos cordiales,

**Martín Llanos**
Be onlyone — CUIT 20-26253453-8
martinllanos@onlyone.com.ar

---

## Borrador 3 — credenciales de producción (2026-10-05)

> Correo **nuevo** a `integraciones@navenegocios.com`, con copia a Jonathan Castillo.
> Deliberadamente breve: sólo se pide lo que hace falta.

---

**Asunto:** Solicitud de credenciales de producción — Be onlyone, CUIT 20-26253453-8

Hola, buen día.

Les escribo desde **Be onlyone** (CUIT **20-26253453-8**). Tenemos la integración con la API de Nave
funcionando en sandbox y estamos pasando a producción.

Les solicitamos las **credenciales de producción** (`client_id` y `client_secret`) para nuestro CUIT.

La URL de notificación (webhook) es la misma para ambos ambientes:

```
https://www.onlyone.ar/payment/nave/webhook
```

Quedamos a la espera. Muchas gracias.

Saludos cordiales,

**Martín Llanos**
Be onlyone — CUIT 20-26253453-8
martinllanos@onlyone.com.ar

---

## Borrador 2 — nuevo código de vinculación para la terminal (2026-09-22)

> Va como **respuesta en el hilo ya abierto**: *"Nave Point: S/N: L40000978 (DEBUG) - Pide soporte
> técnico"*, con `integraciones@navenegocios.com`. Mantener el hilo evita volver a explicar el caso.

---

**Asunto:** Re: Nave Point: S/N: L40000978 (DEBUG) - Pide soporte tecnico

Hola, buen día.

Retomo este hilo. El 14/08 nos pasaron el `pos_id` de la terminal y un código de vinculación de
6 dígitos, con la indicación de reiniciar el equipo e ingresarlo.

Reintenté la vinculación ahora y **el código ya no es aceptado**, entiendo que por vencimiento.

¿Nos pueden generar un **código de vinculación nuevo** para la terminal **S/N `L40000978`**?

Aprovecho para confirmar dos datos, así lo dejamos configurado de una:

1. ¿Sigue vigente el `pos_id` `b1c04ade-dec9-4ca0-9fd9-8464c9006764` para esa terminal?
2. Ese `pos_id`, ¿es el mismo para sandbox y para producción, o hay uno por ambiente?

3. **¿Cómo se da de baja una intención de pago de Nave Point?** Al llamar a
   `DELETE /api/payment_requests/{id}` sobre una intención `smart_pos` recibimos:

   ```
   400 Bad Request — payment_request_delete_failed
   "The payment request could not be deleted. It does not belong to a payment_link,
    dynamic_qr, static_qr..."
   ```

   Entendemos entonces que las intenciones de terminal no se dan de baja por ese endpoint. ¿Hay
   otra forma de cancelarlas desde el sistema de gestión, o la única opción es cancelar desde la
   propia terminal y esperar a que la intención expire por `duration_time`?

Quedamos atentos. Muchas gracias.

Saludos cordiales,

**Martín Llanos**
Be onlyone — CUIT 20-26253453-8
martinllanos@onlyone.com.ar

---

## Borrador 1 — acceso al ambiente de prueba y `pos_id`

> ⚠️ **Parcialmente superado (2026-09-22)**: la pregunta 2 (qué `pos_id` corresponde a la terminal)
> ya estaba respondida en el hilo de agosto, y el punto 1 sobre el comercio de prueba se replantea:
> Nave no pidió un local "test", pidió reiniciar la terminal con el código de vinculación. Siguen
> vigentes las preguntas 3 a 7 (QR, ambientes, devoluciones, ingreso manual de tarjetas).


> Destinatario: `integraciones@navenegocios.com`, con copia al ejecutivo de cuentas Galicia.
> Sólo falta el teléfono de contacto (y confirmar el nombre de la firma).
> Actualizado 2026-09-21: la consulta pasó de ser sólo por el `pos_id` (N9) a ser un **bloqueo
> operativo** — la terminal de prueba no se puede vincular (§3.10 del plan de homologación).

---

**Asunto:** Homologación API — terminal de prueba sin local "test" asociado (Be onlyone, CUIT 20-26253453-8)

---

Hola, buen día.

Les escribo desde **Be onlyone** (CUIT **20-26253453-8**). Estamos integrando **Odoo 18** con la API
de Nave para cobros online y presenciales, de cara a la homologación.

El cobro online (Checkout) ya nos funciona contra sandbox. Al pasar a los **cobros presenciales** nos
encontramos con un bloqueo que no podemos resolver desde nuestro lado.

**La situación:**

1. Recibimos la terminal Nave Point de prueba, **número de serie `L40000978`**. Al encenderla, la
   terminal **se identifica como dispositivo TEST** e indica que debemos vincularla a un local
   llamado **"test"**, en *Negocios > Locales*.
2. **Ese local no aparece** en nuestro Espacio Nave. Sólo vemos nuestros locales productivos.
3. Intentamos avanzar con el QR interoperable y el único QR que pudimos descargar es **de
   producción**: corresponde al local real *"Be onlyone Jujuy"* y está asociado a nuestra cuenta de
   acreditación de Banco Galicia. Obviamente no queremos usarlo para pruebas.

Entendemos entonces que la separación entre sandbox y producción no es sólo de credenciales de API,
sino que también existe un **comercio/local de prueba** con sus propios dispositivos, y que hoy no
tenemos acceso a él.

**Consultas:**

1. **¿Cómo accedemos al comercio/local de prueba** al que debe vincularse la terminal `L40000978`?
   ¿Hay que crearlo nosotros, nos lo habilitan ustedes, o se accede desde un portal de sandbox
   distinto al Espacio Nave habitual?

2. Una vez habilitado ese local: en `POST /api/payment_request/smart_pos` y
   `POST /api/payment_request/static_qr` el campo `seller.pos_id` es obligatorio y es un UUID.
   **¿Qué `pos_id` corresponde a la terminal `L40000978`?** ¿Lo vemos nosotros desde el panel del
   local de prueba, o nos lo informan ustedes?

3. Para el **QR interoperable en sandbox**: ¿cómo generamos un QR de prueba y obtenemos su `pos_id`?
   Si generamos varios QR para el mismo local, ¿cada uno tiene su propio `pos_id`?

4. ¿El `pos_id` es **único por comercio** o **uno por dispositivo** (cada terminal y cada QR)? Lo
   preguntamos porque en el Espacio Nave vemos que nuestro local tiene **números de comercio
   distintos para Tienda Online y para Nave Point** (Visa/Mastercard `315305` y `315306`
   respectivamente), lo que nos sugiere que online y presencial son identidades separadas. Hoy
   estamos usando el `pos_id` que nos entregaron al vincular la tienda online, y sospechamos que no
   es el correcto para los flujos presenciales.

5. ¿El `pos_id` **cambia entre sandbox y producción**, o es el mismo en ambos ambientes?

6. **Devoluciones por API.** Veníamos usando `DELETE /api/payments/{payment_id}` para devolver un
   pago aprobado, siguiendo una versión anterior de la documentación. En el DevPortal actual ese
   endpoint ya no aparece en ninguna de las cuatro secciones: el único `DELETE` documentado es el de
   intenciones (`/api/payment_requests/{id}`). Sin embargo, los estados `REFUNDED` y `CANCELLED`
   siguen figurando entre los estados posibles de un pago. ¿Sigue vigente ese endpoint, se reemplazó
   por otro, o las devoluciones se gestionan únicamente desde el panel de Nave?

7. **Ingreso manual de tarjetas.** La documentación de Checkout indica que el pago con datos de
   tarjeta ingresados manualmente está disponible "si el ingreso manual de tarjetas se encuentra
   habilitado". ¿Está habilitado para nuestro comercio, en sandbox y en producción? De eso depende si
   podemos usar las tarjetas de prueba o si toda la homologación online debe hacerse escaneando el QR
   desde una billetera.

El punto 1 es el que nos está frenando: sin ese local no podemos vincular la terminal ni avanzar con
las pruebas presenciales. Si hace falta que enviemos alguna solicitud formal o completemos algún
formulario, indíquennos por favor.

Quedamos a la espera. Muchas gracias.

Saludos cordiales,

**Martín Llanos**
Be onlyone — CUIT 20-26253453-8
martinllanos@onlyone.com.ar
[Teléfono de contacto]

---

## Bloque opcional — ya no hace falta

> ⚠️ **2026-09-22: BORRAR ESTE BLOQUE.** Las dos preguntas quedaron respondidas por la documentación
> actualizada del DevPortal: el host de sandbox de Nave Point es `e3-api.ranty.io`, y el ingreso
> manual de tarjetas es un flag del comercio (esto último pasó a ser la pregunta 7 del cuerpo).
> Se conserva sólo como registro de lo que ya no hay que preguntar.

~~6. **Host de sandbox para Nave Point.** En la documentación de Smart Point los endpoints de sandbox
   figuran bajo `https://e3-api.ranty.io`, mientras que en la de Checkout y QR el host de sandbox es
   `https://api-sandbox.ranty.io`. En nuestras pruebas `e3-api.ranty.io` devolvió `404` y
   `api-sandbox.ranty.io` respondió correctamente. ¿Cuál es el host correcto de sandbox para Nave Point?

7. **Pagos con tarjeta en sandbox.** La documentación de Checkout publica tarjetas de prueba (Naranja
   y Visa) con número, vencimiento y CVV. Pero en la ayuda del Espacio Nave leemos que, para link de
   pago y QR, *no está habilitado el ingreso manual de datos de tarjeta* y que el pago debe hacerse
   escaneando desde MODO o una app bancaria adherida. ¿Cómo se usan entonces esas tarjetas de prueba
   en sandbox: se ingresan en un formulario del checkout, o el flujo de prueba también requiere
   billetera virtual?~~
