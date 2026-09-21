# Borrador de correo a Nave — acceso al ambiente de prueba y `pos_id`

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

## Bloque opcional — agregar sólo si quieren resolver también N2 y N11

> Misma audiencia técnica, ahorra idas y vueltas de calendario.
> Si prefieren que el correo se enfoque en destrabar la terminal, borrar este bloque.

Aprovechamos para consultar dos puntos más de la integración:

6. **Host de sandbox para Nave Point.** En la documentación de Smart Point los endpoints de sandbox
   figuran bajo `https://e3-api.ranty.io`, mientras que en la de Checkout y QR el host de sandbox es
   `https://api-sandbox.ranty.io`. En nuestras pruebas `e3-api.ranty.io` devolvió `404` y
   `api-sandbox.ranty.io` respondió correctamente. ¿Cuál es el host correcto de sandbox para Nave Point?

7. **Pagos con tarjeta en sandbox.** La documentación de Checkout publica tarjetas de prueba (Naranja
   y Visa) con número, vencimiento y CVV. Pero en la ayuda del Espacio Nave leemos que, para link de
   pago y QR, *no está habilitado el ingreso manual de datos de tarjeta* y que el pago debe hacerse
   escaneando desde MODO o una app bancaria adherida. ¿Cómo se usan entonces esas tarjetas de prueba
   en sandbox: se ingresan en un formulario del checkout, o el flujo de prueba también requiere
   billetera virtual?
