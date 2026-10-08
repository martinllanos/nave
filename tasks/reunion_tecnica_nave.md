# Reunión técnica con Nave — consultas

Preparado el 2026-10-07 a partir de la homologación (`tasks/plan_homologacion_nave.md`). Las
consultas van ordenadas por prioridad: la primera bloquea la homologación y el resto afina cómo se
comporta la integración. Cada una tiene un espacio para anotar la respuesta en vivo.

**Datos para identificarnos:** Be onlyone, CUIT 20-26253453-8.

- `client_id` de sandbox: termina en `…8hFy`.
- `client_id` de producción: termina en `…OZ0u`.
- URL de notificación: `https://www.onlyone.ar/payment/nave/webhook`.

**Para tener abierto:**

- `docs/nave_codigos_referencia.md`: lo que dice su documentación, con la fecha en que se tomó.
- `docs/homologacion/evidencias/`: capturas de cada caso.

---

## 1. 🔴 Devoluciones por API — bloquea la homologación

**Qué pasa.** No podemos cancelar ni devolver un pago desde Odoo. Afecta a los tres medios: checkout,
link de pago y punto de venta.

**Lo que probamos:**

| Endpoint | Sandbox | Producción |
|---|---|---|
| `POST /integrations/payments/{id}/refunds`, el documentado | 403 de IAM | 403 de IAM |
| `DELETE /api/payments/{id}`, de la documentación anterior | 403 de IAM | — |
| Una ruta inventada (control) | 403 *"Invalid key=value pair"* | — |

El 403 de IAM dice: *"User is not authorized to access this resource because no identity-based
policy allows the execute-api:Invoke action"*. Lo distinguimos del control: la ruta existe, pero no
tenemos permiso para usarla.

Los tokens de los dos ambientes traen
`scope = write.payment_request read.payment read.payment_request`. No incluyen ningún permiso de
escritura sobre pagos.

**Preguntas:**

1. ¿Nos pueden agregar el permiso de devoluciones en los dos `client_id`? ¿Cómo se llama ese
   permiso, para verificarlo en el token?
   - Respuesta:
2. ¿Las devoluciones están habilitadas en el perfil del comercio? Según la documentación, si no lo
   están responde `REFUND_NOT_ENABLED`.
   - Respuesta:
3. ¿Una devolución total se pide con el body vacío o con `amount`? El único ejemplo trae sólo
   `tip_amount`.
   - Respuesta:
4. La respuesta del `POST`, ¿trae el estado final (`CANCELLED` o `REFUNDED`) o hay un estado
   intermedio? La documentación anterior hablaba de `CANCELLING` y un webhook posterior.
   - Respuesta:
5. ¿Notifican la devolución por webhook a la URL de notificación?
   - Respuesta:
6. ¿Cuál es la ventana de tiempo para devolver? La documentación menciona
   `REFUND_PERIOD_EXPIRED` pero no da el plazo.
   - Respuesta:
7. ¿`DELETE /api/payments/{id}` está discontinuado? Lo vamos a reemplazar por el `POST`.
   - Respuesta:

**Según la respuesta:** con el permiso habilitado, migramos los dos módulos al endpoint documentado y
cerramos los casos de devolución de la matriz (A14, A15, C13 y H9).

---

## 2. Checklist oficial de homologación

**Pregunta:** ¿Tienen un checklist o un set de casos oficial que quieran ver aprobado antes de dar la
integración por homologada? El nuestro lo armamos nosotros (`plan_homologacion_nave.md` §4), y
algunos requisitos son suposiciones nuestras.

- Respuesta:

**Según la respuesta:** ajustamos la matriz a lo que pidan, y descartamos lo que no les importe.

---

## 3. Por qué se dio de baja un cobro presencial

**Qué pasa.** La documentación de Nave Point publica los motivos de baja de una intención
(`manual_disabled_by_user`, `disabled_by_user_timeout`, `low_battery`,
`device_already_on_payment_flow`, …). Nos servirían para decirle al cajero qué pasó. Pero no nos
llegan:

- consultar una intención dada de baja responde
  `400 {"code":"payment_request_is_disabled","message":"Payment request is disabled"}`, sin motivo;
- sólo recibimos webhooks de **pagos** (`payment_id`, `payment_check_url`, `external_payment_id`),
  nunca de intenciones. La documentación describe una notificación de intención con
  `disabled_reason`.

**Un caso con causa conocida** (`plan_homologacion_nave.md` §3.37): el 2026-10-08 el cliente tocó
*volver* en la terminal, en *"Elegí cómo querés cobrar"*. La intención `d0081b39…` quedó dada de
baja, el motivo esperable es `manual_disabled_by_user` y la consulta respondió igual, sin motivo.

**Preguntas:**

1. ¿Por qué vía se informa el motivo de una baja? ¿Hay una consulta que lo devuelva?
   - Respuesta:
2. ¿La notificación de intención existe para Nave Point? ¿Hay que configurarla aparte?
   - Respuesta:

**Según la respuesta:** el módulo ya está preparado para mostrar esos motivos. Hoy el cajero ve
*"El cobro ya no está disponible"* porque no sabemos la causa.

---

## 4. La terminal corta antes que la intención

**Qué pasa.** Creamos las intenciones de la terminal con `duration_time` de 300 s. Vimos dos
desenlaces distintos en las mismas condiciones:

| Prueba | Qué pasó |
|---|---|
| C9 | La terminal mostró *"Se cumplió el tiempo de espera para pagar"* y dio de baja la intención **a los 189 s** (`DISABLED`) |
| C6, primera vez | Baja (`DISABLED`) |
| C6, segunda vez | `EXPIRED` a los **303 s** |

**Preguntas:**

1. ¿La terminal tiene un tope propio de espera? ¿Cuánto es, y se puede configurar?
2. ¿Por qué a veces termina en `DISABLED` y a veces en `EXPIRED`?
3. ¿Qué `duration_time` recomiendan para Nave Point?

- Respuesta:

**Según la respuesta:** alineamos el plazo de la intención con el de la terminal, para que el POS no
espere de más.

---

## 5. Una tarjeta rechazada bloquea la intención

**Qué pasa.** Con una tarjeta sin fondos, el pago queda `REJECTED` con `no_amount_available` y la
intención pasa a `BLOCKED` con *"payment retries limit reached"*, **después de un solo intento**. La
intención tiene un campo `payment_retries_allowed`.

**Preguntas:**

1. ¿Cuántos intentos permite una intención de Nave Point?
2. ¿Se puede enviar `payment_retries_allowed` al crearla? Así el cliente podría probar otra tarjeta
   en la misma intención, sin que el cajero genere un cobro nuevo.
3. `BLOCKED` es *"fraude o intentos excedidos"*. Para distinguir un fraude, ¿alcanza con el
   `reason_code` del pago (`fraud_identification`, `risky_payment`, `fraud_suspected`)?

- Respuesta:

---

## 6. Webhooks de cobros presenciales

**Qué pasa.** Los pagos de la terminal también se notifican a nuestra URL de notificación. El módulo
de cobros online no los reconoce, porque no son transacciones del e-commerce, y responde 500. Nave
reintenta: en una misma venta vimos tres entregas en unos 7 minutos.

**Preguntas:**

1. ¿Se puede configurar una URL de notificación por medio de cobro o por `pos_id`?
2. Si respondemos 200 a una notificación que no nos corresponde, ¿lo toman como entregada y dejan
   de reintentar?
3. Cuando se agotan los reintentos, ¿pasa algo de su lado, por ejemplo una alerta o que se
   deshabilite la URL?

- Respuesta:

**Ya resuelto de nuestro lado (2026-10-08, `plan_homologacion_nave.md` §3.39):** respondemos 200 a
los avisos que no son del sitio, y vimos que eso corta los reintentos. La pregunta 2 quedó
contestada en la práctica; la 1 y la 3 siguen abiertas.

---

## 7. Conciliación y liquidación

**Preguntas:**

1. ¿A qué hora es el cierre de lote? ¿Cuándo se liquida?
2. ¿Hay un archivo o un endpoint de conciliación?

- Respuesta:

**Por qué importa:** la diferencia entre una cancelación (`CANCELLED`) y una devolución
(`REFUNDED`) depende del cierre de lote. El comercio tiene que poder conciliar lo que cobró.

---

## 8. Límites de la API

**Pregunta:** ¿Hay límite de consultas por minuto, de monto por operación o de intenciones
simultáneas por terminal? El POS consulta el estado de un cobro cada 3 segundos.

- Respuesta:

---

## 8b. Alta de comercios y archivo de `pos_id`

Conviene verlo con la pantalla abierta. El detalle está en
`docs/requerimientos_publicacion_odoo_apps.md` §6.

**El circuito que seguimos:** tienda en *Tienda online propia* → código de vinculación → correo a
`integraciones@` con CUIT, código y medios a habilitar → `pos_id` → archivo `POS_ID-<CUIT>.xlsx` en
*Sistema de gestión*.

**Preguntas:**

1. ¿Es ese el circuito correcto para un comercio que integra desde Odoo?
2. En el archivo, una tienda de e-commerce se identifica sólo por su nombre. ¿Pueden agregar el código
   de vinculación o la URL? Nosotros tenemos dos tiendas con la misma URL.
3. ¿Una tienda se puede dar de baja o archivar?
4. Los QR se llaman *"QR 1"*, *"QR 2"*, y el nombre se repite entre locales. ¿Cómo sabe el comercio
   cuál es cada QR físico?
5. ¿Qué términos usa la mesa de ayuda para credenciales, `pos_id`, tienda y medio de cobro? Los
   necesitamos para los modelos de correo de la guía de alta.
6. ¿El formato del archivo `POS_ID-<CUIT>.xlsx` es estable, con esas cuatro columnas y los valores
   `ECOMMERCE`, `LDP`, `NAVE POINT` y `QR`? La ayuda de los campos de Odoo los va a citar.

- Respuesta:

---

## 8c. La descripción del motivo de baja tiene que ser un texto fijo

**Qué pasa.** `DELETE /api/payment_requests/{id}` rechaza con `400 Invalid input reason` cualquier
`reason.description` que no sea un texto fijo por código: `disabled_from_saas` sólo pasa con
`disabled from SAAS`, exacto. La documentación la presenta como texto libre. Por eso ninguna
cancelación desde Odoo funcionó hasta ahora (`plan_homologacion_nave.md` §3.36).

**Preguntas:**

1. ¿Cuál es la lista oficial de pares código + descripción? `not_specified` no pasó con
   `not specified`.
2. ¿Pueden documentarlo, o aceptar una descripción libre como dice la documentación?
3. ¿Qué motivo corresponde a una baja pedida por el sistema del comercio? Usamos `disabled_from_saas`.

- Respuesta:

---

## 9. Observaciones menores para ellos

- **Cupón de rechazo con datos inconsistentes.** El cupón de la prueba C3 dice *"VISA CREDIT 3370"*
  en el detalle y *"VISA DEBIT"* al pie (`docs/homologacion/evidencias/C3/`). Se repitió en un pago
  **aprobado** (C7c): *"MASTERCARD CREDIT 9537"* en el detalle, *"Debit Mastercard"* al pie, y la
  terminal mostró *"MASTERCARD Crédito"* (`docs/homologacion/evidencias/C7/c_4_cupon.png`).
- **Impresión del cupón.** A veces la terminal imprime el cupón de rechazo y a veces no. ¿Se
  configura desde el sistema de gestión?
- **Documentación.** El portal sólo se lee con un navegador. ¿Tienen una versión descargable, por
  ejemplo una especificación OpenAPI, o un registro de cambios? El cambio de endpoint de
  devoluciones lo descubrimos por casualidad.

- Respuestas:

---

## 10. Publicación en Odoo Apps (si está la persona indicada)

Lo detalla `docs/requerimientos_publicacion_odoo_apps.md` y el borrador 5 del correo: logo, textos
de la ficha, canal de soporte y licencia (hoy LGPL-3).

- Respuesta:

---

## Acuerdos y próximos pasos

| Acuerdo | Responsable | Fecha |
|---|---|---|
| | | |
