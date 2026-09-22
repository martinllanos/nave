# Plan Integral de Homologación — Módulos Nave (Odoo 18)

> Estado: **BORRADOR PARA REVISIÓN** · Elaborado el 2026-09-20 sobre el commit `c3515d8` (rama `18.0-dev`).
> El código desplegado en `oracle-vps:/home/ubuntu/do-onlyone` es **byte-idéntico** a este working tree
> (32 archivos `.py/.xml/.js` comparados por hash, cero diferencias).

## 0. Resumen ejecutivo

Se relevaron los tres módulos contra el contrato real de Nave (`tasks/doc_checkout.md`, `doc_link.md`,
`doc_point.md`, `doc_qr.md`) y contra el plugin oficial de WooCommerce que Nave publica
(`docs/nave-for-woocommerce/`), que sirve de implementación de referencia.

**Conclusión: no se puede arrancar la homologación todavía.** Hay 11 bloqueantes (§2). Tres de los
cuatro flujos comprometidos no pueden completarse ni en el escenario feliz:

- **Link de pago**: no concilia nunca, el wizard no crea la transacción (B1).
- **Smart Point**: el camino feliz es inalcanzable — el POS consulta el endpoint de la *intención*
  pero espera estados del *pago*, y `APPROVED` no existe en ese vocabulario (**B11**).
- **QR interoperable**: no tiene código (B8). Confirmado en alcance el 2026-09-21 (D4).

Sólo el checkout e-commerce está razonablemente cerca, y arrastra un SSRF en el webhook (B5).

Salvo el QR, ninguno es estructural: son huecos acotados, la mayoría de pocas líneas. Estimación
gruesa: **5 a 7 días** para B1-B7 y B9-B11 (incluye cerrar el ciclo de devolución, que es
transversal a los cuatro flujos), más **3 a 5 días** para el QR (B8), que es desarrollo nuevo. El QR puede ir en paralelo y se puede homologar **sin hardware** usando el endpoint de
simulación de sandbox (`doc_qr.md` §10).

⚠️ **Bloqueo operativo abierto (2026-09-21)**: la terminal de prueba pide un local "test" que no
existe en nuestro Espacio Nave, y el único QR que pudimos descargar es de producción. Todo el testing
sobre dispositivos (bloques C y H) está parado hasta que Nave nos habilite el comercio de prueba
(§3.10). El resto del trabajo —simulador, y los fixes B11/B1/B5/B6— sigue sin depender de eso.

El plan se ordena así:

| Etapa | Contenido | Precondición |
|---|---|---|
| **E0** | Verificación de base: correr las suites existentes | ninguna |
| **E1** | Cerrar bloqueantes §2 | E0 |
| **E2** | Preparar entorno de homologación §3 | en paralelo con E1 |
| **E3** | Ejecutar matriz de casos §4 | E1 + E2 |
| **E4** | Empaquetar evidencias y demo a Nave §6 | E3 |

---

## 1. Alcance

### Dentro de alcance

| Producto | Módulo | Endpoint Nave |
|---|---|---|
| Cobro online / Checkout e-commerce | `payment_nave` | `POST /api/payment_request/ecommerce` |
| Link de pago (factura y pedido) | `payment_nave` (wizard) | `POST /api/payment_request/payment_link` |
| Smart Point (terminal física) | `pos_nave` | `POST /api/payment_request/smart_pos` |
| **QR interoperable (presencial)** | `pos_nave` — **a desarrollar (B8)** | `POST /api/payment_request/static_qr` |

**Devolución total: en alcance para los cuatro flujos** (D5). Está documentada en los cuatro docs de
Nave bajo el mismo contrato — `DELETE {api-base}/api/payments/{payment_id}` → `CANCELLING`, y el
estado final llega asincrónicamente por webhook (`doc_checkout.md` §8, `doc_link.md` §3,
`doc_point.md` §7, `doc_qr.md` §8). La devolución es **sólo total** (`full_only`, confirmado N10): no existe la parcial.

Todo se ejecuta sobre la compañía **4, `(AR) Monotributista`** de la base `www.onlyone.ar`
(confirmado D3): ahí viven el provider Nave `id=18`, el POS "Nave Smart POS" y el website.

### Fuera de alcance — y por qué

- **`sale_nave_simulator`**: no hace una sola llamada a Nave, no toca `payment.transaction` ni
  `payment.provider`, opera sobre precios de lista antes del cobro. Además está incompleto
  (`tasks/todo.md` §Fase 4: motor predictivo e integración UI sin implementar) y sin tests.
  Único punto de contacto a verificar como sanity: que el total del pedido con una lista de precios
  Nave coincida con el `amount.value` enviado (caso G4).

---

## 2. Bloqueantes a resolver ANTES de homologar

Cada ítem lleva la referencia al código. Todos fueron detectados por lectura; **E0 los confirma en ejecución.**

### B11 — El POS consulta el endpoint de la *intención* pero espera estados del *pago* 🔴🔴

**Este es el hallazgo más grave y no requiere sandbox para confirmarse: sale de la documentación.**

Nave expone dos recursos con dos vocabularios de estados distintos:

| Recurso | Endpoint | Estados |
|---|---|---|
| **Intención** (`payment_request`) | `GET /api/payment_requests/{id}` | `PENDING`, `PROCESSED`, `DISABLED`, `SUCCESS_PROCESSED`, `FAILURE_PROCESSED`, `EXPIRED`, `BLOCKED` (`doc_qr.md` §6) |
| **Pago** (`payment`) | `GET /ranty-payments/payments/{payment_id}` | `APPROVED`, `REJECTED`, `CANCELLED`, `REFUNDED`, … (`doc_point.md` §4) |

El POS consulta **el primero** (`pos_nave/models/pos_payment_method.py:133-178`) pero evalúa
**estados del segundo**: el JS corta el polling sólo con `APPROVED`, `REJECTED` o `CANCELLED`
(`pos_nave/static/src/app/payment_nave.js:127-137`).

**`APPROVED` nunca puede aparecer en ese endpoint.** Un cobro exitoso devuelve `SUCCESS_PROCESSED`,
que cae en la rama "cualquier otro estado" → vuelve a consultar a los 3 s → **para siempre**.

Consecuencia: **el camino feliz del Smart Point no puede completarse**. El caso C2 no es que "puede
fallar": no puede pasar. Y como el único escape es "Force done" (B4), el cajero terminaría cerrando
como cobrada una venta que en Nave sí se cobró pero que Odoo nunca reconoció.

Esto reordena las prioridades: **B11 antes que B4**. Corregirlo implica decidir el flujo correcto —
probablemente mapear los estados de intención (`SUCCESS_PROCESSED` → traer el `payment_id` y
consultar `/ranty-payments/payments/{id}` para obtener marca, últimos 4 y cupón), que de paso
resuelve B3 y habilita C12.

El comentario del propio código lo anticipaba (`payment_nave.js:124`: *"suponiendo estructura
{status: {name: '...'}}"*). La suposición era razonable; el vocabulario, no.

**Confirmación empírica sin hardware**: los casos **S2 y S3** (§Bloque S) comparan la respuesta de los
dos endpoints para el mismo pago usando el simulador de Nave. Hacerlos **antes** de escribir el fix.

### B1 — El link de pago no concilia: no crea `payment.transaction` 🔴

`payment_nave/models/nave_link_wizard.py:149-275` genera el link contra Nave y lo postea al chatter,
pero **nunca crea una `payment.transaction`**. Cuando el cliente paga, Nave envía el webhook con
`external_payment_id = FAC/2026/00001`; `_get_tx_from_notification_data`
(`payment_nave/models/payment_transaction.py:221-236`) no encuentra nada y lanza `ValidationError`;
el controller responde 500 a propósito (`payment_nave/controllers/main.py:51-53`) y Nave reintenta
5 veces (10 s, 70 s, 490 s, 3340 s, 24010 s) hasta rendirse.

**Resultado: la factura nunca se marca como pagada.** Es el hueco más grande del módulo y afecta a
uno de los tres productos a homologar.

**Fix**: crear la `payment.transaction` en `draft` dentro de `action_generate_link()`, con
`reference` = el mismo `external_payment_id` truncado que se manda a Nave, vinculada a
`invoice_ids`/`sale_order_ids`.

### B2 — Reembolso desde POS hardcodeado con `"REFUND-CIEGO"` 🔴

`pos_nave/static/src/app/payment_nave.js:75-82` manda literalmente el string `"REFUND-CIEGO"` como
`transaction_id`, produciendo `DELETE /api/payments/REFUND-CIEGO`. Los comentarios del propio archivo
lo admiten: *"intentamos un reembolso ciego"*, *"Se debería adaptar para recibir el trans original"*.
Falla siempre, en cualquier ambiente. Peor: si la API devolviera 2xx por cualquier motivo, marca la
línea como `done` sin devolución real (`:90`).

**Fix**: recuperar el `payment_id` real del pago original (ver B3) y pasarlo. O, si no llega a la
fecha, **desactivar la rama** y declarar la devolución POS fuera de alcance de esta homologación.

### B3 — `transaction_id` del POS guarda el id de la intención, no del pago 🔴

`pos_nave/static/src/app/payment_nave.js:52,130` setea `line.transaction_id` con el
`payment_request_id`. Pero `DELETE /api/payments/{payment_id}` (`tasks/doc_point.md:179-184`) espera
el **`payment_id`**, que es otro identificador. Aunque se arregle B2, la devolución seguiría fallando.

Causa raíz: el módulo sólo consulta `GET /api/payment_requests/{id}` (estado de la *intención*) y
nunca `GET /ranty-payments/payments/{payment_id}` (estado del *pago*), que es donde vive el
`payment_id`, el `payment_code`, la marca de tarjeta, los últimos 4 dígitos y el plan de cuotas.

### B4 — Polling del POS sin timeout: loop infinito silencioso 🔴

`pos_nave/static/src/app/payment_nave.js:103-155`. Intervalo 3 s, **sin contador de intentos ni
watchdog**. Sólo `APPROVED`, `REJECTED` y `CANCELLED` cortan el loop; **cualquier otro estado
re-consulta para siempre**. Y `EXPIRED` y `DISABLED` no son casos raros: son lo que Nave devuelve
cuando vence el `duration_time` de 300 s (`pos_nave/models/pos_payment_method.py:93`) o cuando el
cajero da de baja el cobro desde la terminal (`tasks/doc_point.md:196-205`).

Agravante: el frontend usa `pos.data.silentCall`, que captura **toda** excepción y devuelve `false`
(`point_of_sale/static/src/app/services/data_service.js:631-639`). Con el servidor caído,
`data?.status?.name` queda `undefined` → `statusName = 'PENDING'` → sigue girando. Los `try/catch` de
`:148-154` y el diálogo "Pérdida de conexión con Nave" son **código muerto en la práctica**.

**Consecuencia operativa**: ante cualquier incidente, la única salida del cajero es el botón
**"Force done"** nativo de Odoo, que marca la línea como cobrada **sin consultar nada a Nave, sin
cancelar la intención y dejando el polling corriendo** (`point_of_sale/.../payment_screen.js:604-612`).
Se puede cerrar una venta que la terminal rechazó. Esto, si Nave lo ve en la demo, es un hallazgo grave.

**Fix mínimo**: timeout de polling (sugerido 90 s, igual que `pos_razorpay`), manejo explícito de
`EXPIRED`/`DISABLED`/`PROCESSING`, y distinguir `data === false` (error de transporte) de una
respuesta válida.

### B5 — Webhook sin firma + SSRF en la verificación 🔴

El endpoint `/payment/nave/webhook` es `auth='public'`, `csrf=False`, CORS `*`
(`payment_nave/controllers/main.py:13-26`) y **no valida firma alguna** — correctamente, porque
**Nave no firma sus webhooks**: el payload son tres campos y no hay header de firma documentado
(`tasks/doc_checkout.md` §4). O sea, `tasks/todo.md` §Fase 2 tiene tildado *"validación estricta de
firma/hash"* y **eso no está implementado ni es implementable** con el contrato actual.

La defensa real es el GET de verificación server-side (`payment_transaction.py:254-278`), que es el
patrón correcto. **Pero la URL de ese GET sale del propio payload del webhook**
(`notification_data['payment_check_url']`, `:256-259`, introducido en el último commit `c3515d8`).
Un atacante que adivine una `reference` puede apuntar `payment_check_url` a un host propio que
responda `{"status":{"name":"APPROVED"}}` y **marcar una factura como pagada**.

**Fix**: allowlist de host. Aceptar `payment_check_url` sólo si su dominio es `ranty.io` o subdominio;
si no, usar el fallback construido localmente. Son ~5 líneas y es el hallazgo de seguridad más
probable de una revisión de Nave.

⚠️ **No eliminar la rama.** Según §4.2, usar el `payment_check_url` del webhook es justamente lo que
destrabó el checkout el 2026-08-11 — el fallback local no alcanzaba. La allowlist conserva el
comportamiento que funciona y cierra el agujero.

### B6 — El ciclo de devolución no cierra en ningún flujo 🔴

Confirmado en alcance (D5). Hoy la devolución está rota en **cuatro puntos encadenados**, y cada uno
basta por sí solo para que el caso no pase:

**1. El botón no existe en el backend.** `payment_nave` no sobreescribe
`_compute_feature_support_fields`, así que `provider.support_refund` queda en `'none'`
(`payment/models/payment_provider.py:245`) y `account_payment/models/account_payment.py:58` exige
`!= 'none'` para mostrarlo. `_send_refund_request` (`payment_nave/models/payment_transaction.py:307-344`)
**sólo es alcanzable desde código o tests**.

**2. ~~El monto se ignora~~ — resuelto por N10.** `amount_to_refund` no se usa y siempre hace DELETE
del pago entero (`:322`). **Eso es correcto**: Nave sólo admite devolución total (`full_only`). Lo que
hay que arreglar es la *declaración*, no el comportamiento — ver punto 5 y §3.8.

**3. Se cancela el registro equivocado.** El `_set_canceled` posterior se aplica a la transacción
**origen**, que está en `done`; esa transición no está permitida
(`payment/models/payment_transaction.py:738`) → warning en el log y sin efecto. Lo correcto es actuar
sobre la transacción hija de refund que crea el `super()`.

**4. El estado final nunca llega.** Nave responde `CANCELLING` y confirma después por webhook con
`REFUNDED` o `CANCELLED`. Pero `_process_notification_data` mapea ambos a `_set_canceled`
(`payment_transaction.py:297-299`), que otra vez rechaza una tx en `done`. **Aunque la devolución se
ejecute correctamente del lado de Nave, Odoo nunca la refleja.**

**5. El módulo declara una capacidad que la API no tiene.** `data/payment_method_data.xml:33` pone
`support_refund='partial'` en el método `nave_qr`. **Confirmado con Nave (N10): es `full_only`.**
Ojo con el `noupdate="1"` del archivo — ver §3.8.

Arreglar esto es más que "mostrar el botón": es cerrar el ciclo completo
`DELETE → CANCELLING → webhook → estado en Odoo`.

### B7 — En el checkout sólo aparece "QR Interoperable Nave" 🟠

`payment_nave` no sobreescribe `_get_default_payment_method_codes()`, que devuelve `set()` vacío por
defecto (`payment/models/payment_provider.py:737-745`). `_activate_default_pms()` no activa nada, y
`payment.payment_method_card` y `payment.payment_method_naranja` vienen `active=False` de base.

**El efecto es no determinístico y varía por base** (verificado el 2026-09-22):

| Método | Base local (instalación limpia) | Base de homologación |
|---|---|---|
| `card` | inactivo | **activo** |
| `naranja` | inactivo | inactivo |
| `nave_qr` | **inactivo** | activo |

O sea: el módulo **nunca activa sus propios métodos**, y que aparezcan o no depende de factores
ajenos (otro proveedor que activó `card`, una activación manual). En una instalación limpia no
aparece **ninguno**, ni siquiera el QR propio. Corregir mi lectura anterior: no es "sólo se ve el
QR", es "no se ve nada salvo que algo más los haya activado".

**Confirmar en A1** qué ve realmente el cliente en el checkout de homologación.

Relacionado: `_get_supported_currencies()` (`payment_provider.py:49-54`) hace `search([('name','=','ARS')])`
**sin `active_test=False`**; si la moneda ARS está archivada devuelve vacío y Odoo lo interpreta como
"sin restricción", aceptando cualquier moneda.

### B8 — QR interoperable: a desarrollar 🔴

**Confirmado en alcance (D4).** No hay ninguna referencia a `static_qr`, `qr_data` ni al endpoint
`POST /api/payment_request/static_qr` en `pos_nave`. La única rama existente es Smart POS. El
`payment.method` `nave_qr` existe como dato (`data/payment_method_data.xml:25-44`) y se muestra en el
checkout, pero **el flujo presencial QR no tiene código**.

No es una prueba pendiente: es desarrollo. El delta contra Smart POS es acotado (`doc_qr.md` §3):

| Aspecto | Smart POS (existe) | QR interoperable (falta) |
|---|---|---|
| Endpoint | `/api/payment_request/smart_pos` | `/api/payment_request/static_qr` |
| Campo extra | — | `transactions[].qr_amount = "close"` (obligatorio) |
| `products[].description` | requerido | opcional |
| `pos_id` | el de la terminal física | **el del QR físico registrado en la plataforma** |
| Respuesta | `status: PENDING`, sin `checkout_url` | datos del QR a renderizar |
| Estado final | polling | mismo polling (afectado por B11) |
| Errores propios | catálogo de baja | `ERROR_ENCODE_DYNAMIC_QR`, `NO_GATEWAYS_AVAILABLE` |

Decisiones de diseño a tomar antes de codificar:

1. **¿Método de pago POS separado o selector dentro del mismo?** Hoy `use_payment_terminal == 'nave'`
   siempre rutea a Smart POS. Lo más limpio es un segundo método de pago POS ("Nave QR") con su
   propio `nave_terminal_id` = el `pos_id` del QR físico, reutilizando toda la maquinaria de polling.
2. **Reutilizar `PaymentNave`** parametrizando el endpoint, en vez de duplicar la clase JS.
3. Registrar los QR físicos en la plataforma de Nave para obtener sus `pos_id` (`doc_qr.md` §1) — es
   un trámite previo, igual que el de la terminal.

**A favor: se puede homologar sin hardware.** `doc_qr.md` §10 documenta un endpoint de simulación de
sandbox que dispara el pago y el webhook end-to-end:

```
GET https://api-sandbox.ranty.io/instore/external/resolve?data={QR_FIJO}&access_token={TOKEN}
```

Eso permite automatizar el bloque H completo y no depender de una billetera real para las pruebas.

### B9 — Sin cron de respaldo si se pierde el webhook 🟠

No existe ningún `ir.cron` en `payment_nave` (confirmado también en la base del servidor: cero crones
con "nave" en el nombre). Nave reintenta durante ~7h45m y se rinde. Si el sitio estuvo caído más que
eso, la transacción queda en Pendiente **para siempre**.

El plugin oficial de Nave resuelve esto con un cron cada 15 min que re-consulta órdenes pendientes
(`docs/nave-for-woocommerce/src/Handler/CronHandler.php:27-28,72-93`). Recomiendo replicarlo: es la
diferencia entre "se nos perdió un pago" y "se recupera solo".

### B10 — La suite de `pos_nave` está desalineada con el código 🟠

`pos_nave/tests/test_pos_nave_payment.py` — 4 de 5 tests apuntan a un host y a paths que el código ya
no genera (`e3-api.ranty.io/instore/payment_intents` vs. `api-sandbox.ranty.io/api/payment_request/smart_pos`),
uno parchea `requests.post` cuando el código usa `requests.delete` (`:117-138`), y `test_05` no mockea
nada y **dispara una llamada HTTP real al sandbox** (`:140-150`).

Da falsa sensación de cobertura. **E0 lo confirma.** Además no hay un solo test JS ni tour: todo el
polling, la cancelación y el "force done" están sin cobertura automatizada.

---

## 3. Preparación del entorno (E2)

### 3.1 Entorno — resuelto ✅

`do-onlyone` en `oracle-vps` **es el entorno de homologación**, y la base `www.onlyone.ar` contiene
datos de homologación. El naming de la infra despista (el router de traefik se llama `odoo-prod` en
`stack.yaml:35`) pero no refleja el propósito del entorno.

Consecuencias para el plan:

- **No hace falta levantar una base separada.** Se homologa acá.
- Los movimientos existentes (sesión POS/00005 abierta, dos pagos en efectivo, las 3 transacciones
  Nave de agosto) son datos de prueba: no hay que preservarlos ni limpiar con cuidado especial.
- A favor: el entorno ya es **públicamente alcanzable** (`https://www.onlyone.ar` responde 200, y
  `/payment/nave/webhook` responde 200 al preflight OPTIONS), que es el requisito duro para recibir
  webhooks de Nave. No hace falta túnel ni ngrok.
- Sigue en pie registrar esa `notification_url` del lado de Nave (P3): no se envía en el payload.

### 3.2 Checklist de preparación

| # | Ítem | Responsable | Estado |
|---|---|---|---|
| P1 | ~~Base de homologación separada~~ — **no aplica**: `do-onlyone` ya es el entorno de homologación | — | ✅ |
| P2 | Obtener de Nave el **checklist oficial de homologación** | Comercial | ⬜ |
| P14 | **Correo enviado a Nave el 2026-09-22** con N9 (acceso al comercio de prueba y `pos_id`), N12 (devoluciones por API) e ingreso manual de tarjetas | Comercial | ⏳ **esperando respuesta** |
| P3 | Registrar la `notification_url` del lado de Nave | Comercial | ✅ **hecho**. Es **la misma URL para homologación y producción**: `https://www.onlyone.ar/payment/nave/webhook`. Lo que cambia es el estado `test`/`enabled` del provider — ver §3.7 |
| P4 | Terminal Smart Point física de prueba | Comercial | ⚠️ **recibida (serie `L40000978`) pero NO vinculable**: pide un local "test" que no existe en nuestro portal — ver §3.10 |
| P13 | 🔴🔴 Obtener acceso al **comercio/local de prueba** de Nave, con su terminal y sus QR de sandbox | Comercial | ⬜ **bloquea todo el testing presencial** |
| P12 | 🔴 Obtener de Nave el **`pos_id` (UUID) que corresponde a la terminal `L40000978`** y cargarlo en `nave_terminal_id`. Hoy ese campo tiene `f71ba756-1d80-4ab3-9f43-5dc247fd6c4a`, que es **el mismo UUID que el `nave_pos_id` de e-commerce** del provider — ver §3.5 | Técnico | ⬜ |
| P5 | Confirmar con Nave el host de sandbox de Smart POS: `e3-api.ranty.io` (doc) vs `api-sandbox.ranty.io` (código) | Técnico | ⬜ |
| P6 | Confirmar path de auth para QR: `m2ms` vs `m2msPrivate` | Técnico | ⬜ |
| P7 | Cargar credenciales de sandbox en el provider, estado **Test**, publicado | Técnico | ✅ (ya está en la base actual, provider `id=18`, compañía 4) |
| P8 | Cliente de prueba con CUIT válido y email real | Funcional | ⬜ |
| P9 | Producto de prueba en ARS con precio que permita montos variados | Funcional | ⬜ |
| P10 | Acceso a logs en vivo (`docker service logs -f do-onlyone_odoo \| grep payment_nave`) | Técnico | ⬜ |
| P11 | Herramienta de captura: video de pantalla + cámara para la terminal (Nave pide ver ambas a la vez, según nuestros docs internos — confirmar en P2) | Funcional | ⬜ |

### 3.3 Ambientes y credenciales (de la doc de Nave)

| | Sandbox | Producción |
|---|---|---|
| Auth checkout/link/point | `homoservices.apinaranja.com/security-ms/api/security/auth0/b2b/m2msPrivate` | `services.apinaranja.com/...` |
| API checkout/link | `https://api-sandbox.ranty.io` | `https://api.ranty.io` |
| API Smart POS | `https://e3-api.ranty.io` *(según doc — ver P5)* | `https://api.ranty.io` |

`audience` siempre `https://naranja.com/ranty/merchants/api`. Moneda: ARS únicamente.
`external_payment_id` ≤ 36 caracteres.

### 3.5 ⚠️ El `pos_id` de la terminal está duplicado del de e-commerce

Estado actual en la base de homologación:

| Registro | Campo | Valor |
|---|---|---|
| `pos.payment.method` id 3 ("Tarjeta") | `nave_terminal_id` | `f71ba756-1d80-4ab3-9f43-5dc247fd6c4a` |
| `payment.provider` id 18 (Nave) | `nave_pos_id` | `f71ba756-1d80-4ab3-9f43-5dc247fd6c4a` |

**Son el mismo UUID.** El payload de Smart POS manda `seller.pos_id = nave_terminal_id or provider.nave_pos_id`
(`pos_nave/models/pos_payment_method.py:64`), así que hoy las intenciones de cobro presencial salen
apuntando al identificador de la **tienda de e-commerce**, no al de la terminal física `L40000978`.

Dos lecturas posibles, y hay que confirmar cuál aplica (pregunta N9):

1. Nave asigna un `pos_id` distinto por terminal física → hay que pedirlo y cargarlo, porque de lo
   contrario el cobro nunca llega al equipo.
2. Nave usa un único `pos_id` por comercio y la terminal se resuelve del lado de ellos → el campo
   `nave_terminal_id` sobra y conviene documentarlo.

Hasta resolverlo, **C2 no puede pasar**: no hay forma de saber si el cobro debería aparecer en la
terminal. Es la primera prueba a hacer apenas se encienda el equipo.

Nota colateral: esta duplicación es también la razón por la que `test_05_missing_terminal_id`
(`pos_nave/tests/test_pos_nave_payment.py:140-150`) no levanta el `UserError` que espera — el
fallback a `nave_pos_id` lo enmascara.

### 3.10 🔴🔴 BLOQUEANTE: no tenemos acceso al ambiente de prueba del comercio

Hallazgo del 2026-09-21, y es el que frena hoy **todo** el testing presencial.

**Los hechos:**

1. La terminal Nave Point recibida (serie `L40000978`) **se identifica a sí misma como dispositivo
   TEST** e indica que hay que vincularla a un local llamado **"test"** en *Negocios > Locales*.
2. **Ese local no existe** en el Espacio Nave al que accedemos
   (`navenegocios.com/business/virtual-branch/385213`).
3. El QR que sí pudimos descargar es **de producción**: corresponde al local real
   *"Be onlyone Jujuy - QR 1"*, con acreditación en la cuenta de Banco Galicia del comercio.

**La conclusión:** la separación sandbox/producción de Nave **no es sólo de credenciales de API**.
Hay también una separación **a nivel de comercio, local y dispositivo**: existe (o debe crearse) un
comercio/local de prueba, con su propia terminal, sus propios QR y sus propios `pos_id` de sandbox.
Nuestras credenciales de sandbox apuntan a ese ambiente, pero **desde el portal sólo vemos el de
producción**.

Esto además **reencuadra N9**: probablemente la pregunta no sea "cuál de nuestros `pos_id` usar",
sino "cómo accedemos al local de prueba, del que saldrán los `pos_id` correctos".

**⚠️ Riesgo inmediato — no usar el QR descargado para pruebas.** Es de producción y está atado a la
cuenta real del comercio. Cualquier pago contra ese QR es **dinero real acreditándose en la cuenta de
Galicia**, no una simulación. Guardarlo y no mezclarlo con el material de homologación.

**Qué queda bloqueado hasta resolverlo:**

| Bloque | Estado |
|---|---|
| C — Smart Point completo | 🚫 La terminal no se puede vincular |
| H — QR interoperable | 🚫 No tenemos un QR de sandbox ni su `pos_id` |
| C0 / §3.5 | 🚫 No se puede verificar el ruteo por `pos_id` |

**Qué NO queda bloqueado** (y por eso el trabajo sigue): el bloque **S** con el simulador web de Nave
(§3.6), que no necesita hardware ni local de prueba, y todo el trabajo de código sobre B11, B1, B5 y
B6. El camino crítico no se detiene; lo que se detiene es la verificación contra dispositivos.

### 3.9 Hallazgos del Espacio Nave (portal del comercio, 2026-09-21)

Relevado del panel y de la ayuda de `navenegocios.com`. Varias cosas no están en la doc de API.

**a) Identidades separadas online vs presencial.** El local **"Be onlyone"**
(`/business/virtual-branch/385213`, tienda `www.tienda.onlyone.ar`, acreditación en Banco Galicia)
expone en *Números de identificación del local*:

| Marca | N° comercio Tienda Online | N° comercio Nave Point |
|---|---|---|
| Visa y Mastercard | `315305` | `315306` |
| Naranja X | `823043843` | `823043850` |

**Online y presencial tienen identidades distintas del lado de Nave.** No son el `pos_id` de la API
(el panel aclara que se usan para promociones), pero refuerzan N9: es poco probable que un único
`pos_id` sirva para ambos flujos.

**b) El `L40000978` es el número de serie de vinculación, no el `pos_id`.** La ayuda de Nave Point
indica vincular con *"el número de serie (9 caracteres alfanuméricos), ubicado en la parte inferior de
la pantalla de la terminal"* — `L40000978` tiene exactamente 9. El `pos_id` de la API es un UUID:
son dos cosas distintas. **Esto afina N9: tenemos la serie, nos falta el UUID.**

**c) Las terminales no se trasladan entre locales**, aunque sean del mismo comercio, y se solicitan
por local. Otra señal de identidad por dispositivo.

**d) El QR se descarga desde la plataforma.** *Nave > Negocios > elegí el local > Descargar*. Y
atención: **si el comercio tiene habilitada la opción de Nave Point, NO recibe el kit POP con el QR
físico preimpreso**. Como tenemos terminal, el QR hay que bajarlo del panel. Eso desbloquea H1.

**e) No hay límite de QR por comercio**, y puede haber varios incluso en un mismo punto de venta.
Consistente con un `pos_id` por QR.

**f) 🔴 Los pagos con tarjeta se hacen escaneando, no tipeando.** La ayuda de Link de Pago dice:
*"Para pagos con tarjeta, no está habilitado el ingreso manual de datos. El pago debe realizarse
escaneando el QR desde una billetera virtual o app bancaria"*. Y en Cobros con QR: *"Pagos con
tarjeta de crédito o débito: el cliente debe escanear el QR desde MODO o una app bancaria adherida a
MODO"*, con un *"no se debe usar la cámara del celular"*.

**Esto afecta directamente a los casos A2 a A6 y B3c**, que redacté asumiendo que se tipean las
tarjetas de prueba de `doc_checkout.md` §11. Y explica la transacción aprobada del 2026-08-11: se
pagó con **billetera Mercado Pago**, no con tarjeta tipeada. Ver N11.

**g) Vencimiento del link: 24 h, 48 h o 7 días.** Son las tres opciones del panel. Nuestro wizard
expone `duration_hours` libre (default 24, sin tope ni validación). **Esto le da fuente al pendiente
de `todo.md`** sobre "la expiración de 24 horas": no es un límite duro de la API —la doc admite
`duration_time` en segundos con default de 1 semana— sino la opción por defecto del panel. El tope
razonable es 7 días = 168 h, que es justo lo que el help del campo ya recomienda.

**h) Cada link es único y de un solo uso.** Refuerza B6c: regenerar el link de la misma factura
reusando el mismo `external_payment_id` truncado puede ser rechazado.

**i) Estados del link en el panel**: `Aprobado` y `Devuelto`. Vocabulario a contrastar con el de la API.

### 3.8 Devolución: `full_only` (N10 resuelta)

Nave sólo admite devolución **total**. Eso simplifica B6 y obliga a dos cambios concretos:

**1. Corregir el dato del método de pago.** `payment_nave/data/payment_method_data.xml:33` declara
`<field name="support_refund">partial</field>`. Debe ser `full_only`.

⚠️ El archivo abre con `<odoo noupdate="1">`, así que **cambiar el XML no actualiza el registro
existente** en la base de homologación: hace falta un script de migración (el módulo ya tiene el
patrón en `migrations/18.0.1.2.0/end-migrate.py`) o un `write` manual sobre el registro.

**2. Declararlo en el provider.** `_compute_feature_support_fields` —que hoy no existe (B6.1)— tiene
que setear `support_refund = 'full_only'` para `code == 'nave'`. Los valores válidos en
`payment.provider` son `none` / `full_only` / `partial` (`payment/models/payment_provider.py:166-169`).

**Efecto colateral bueno**: con `full_only`, Odoo no ofrece el campo de monto parcial en la UI de
reembolso, así que el hecho de que `_send_refund_request` ignore `amount_to_refund` deja de ser un
bug y pasa a ser el comportamiento correcto. **B6 se reduce de cinco problemas a cuatro.**

### 3.7 ⚠️ El ambiente se deriva del provider, no de la transacción — riesgo de go-live

La `notification_url` es única para homologación y producción (P3), y lo que discrimina el ambiente
es el campo `state` del provider (`test` → sandbox, cualquier otro → producción,
`payment_provider.py:131-143`). Eso funciona hoy, pero **el modelo se rompe el día del go-live**,
porque la URL base **se recalcula en cada llamada a partir del estado actual del provider** y nunca
se guarda en la transacción:

| Punto del código | Qué recalcula |
|---|---|
| `payment_transaction.py:44` | URL de creación de la intención |
| `payment_transaction.py:261` | URL del GET de verificación (sólo el **fallback**) |
| `payment_transaction.py:321` | URL de la **devolución** |
| `pos_payment_method.py:58,145,192,229` | Todas las llamadas del POS |
| `nave_link_wizard.py:169` | URL del link de pago |

Consecuencias de pasar el provider `id=18` de `test` a `enabled`:

1. **Las devoluciones de pagos de homologación se rompen.** `_send_refund_request` apuntaría a
   `https://api.ranty.io/api/payments/{id_de_sandbox}` — ese pago no existe en producción.
2. **El token cacheado no se invalida.** `_nave_get_access_token` sólo mira `nave_token_expiry`
   (`payment_provider.py:70`), no qué ambiente lo emitió. El token de sandbox dura hasta 24 h, así que
   durante ese lapso el módulo mandaría **un token de sandbox a la API de producción** → 401 en cada
   llamada, sin reintento ni invalidación reactiva.
3. **Las credenciales son un solo par de campos.** `nave_client_id`/`nave_client_secret` no están
   duplicados por ambiente: cambiar el estado sin cambiar las credenciales autentica contra
   producción con credenciales de sandbox.

La alternativa —**dos providers**, uno `test` y uno `enabled` con sus credenciales— choca con **G2**:
`_get_nave_payment_provider` (`pos_payment_method.py:30-43`) filtra por `state != 'disabled'` con
`limit=1` y **sin preferir `enabled`**, así que el POS elegiría uno u otro según el orden por defecto.

**Ninguno de los dos caminos está listo.** No bloquea la homologación, pero sí el go-live, y se
arregla barato: invalidar el token al cambiar `state`, guardar la URL base usada en la transacción (o
derivarla del `payment_check_url`), y dar orden explícito a la búsqueda del provider en el POS.

**Checklist de cutover a producción** (para cuando llegue el momento):

- [ ] Cambiar las credenciales a las de producción **antes** de cambiar el estado.
- [ ] Vaciar `nave_access_token` y `nave_token_expiry` a mano.
- [ ] Verificar que no queden transacciones de sandbox en `pending` que puedan recibir un webhook tardío.
- [ ] Primera transacción de producción por monto mínimo, verificada de punta a punta.

### 3.6 Simulador de cobros presenciales de Nave

Nave expone un simulador web en **`navenegocios.ar/home/developers`** que genera cobros presenciales
sin hardware. Campos:

- **Tipo de pago** (excluyente): `Pago aprobado con tarjeta`, `Pago rechazado con tarjeta`,
  `Pago aprobado con QR`, `Pago rechazado con QR`.
- **Monto total** y **External payment id**.
- **Notificación**: URL propia donde recibir los webhooks (con botón Guardar). La propia UI sugiere
  `webhook.site` o `beeceptor` para inspeccionarlos.
- Botón **Generar intención de pago**.

**Qué cubre y qué no** — importante no sobrestimarlo:

| | Cubierto |
|---|---|
| ✅ | El **webhook de Nave**: payload real, timing, reintentos |
| ✅ | El **vocabulario de estados** real de ambos endpoints (lo que confirma B11) |
| ✅ | Los cuatro desenlaces presenciales: tarjeta ok/rechazada, QR ok/rechazado |
| ✅ | El procesamiento **inbound** de Odoo (webhook → transacción) |
| ❌ | La **intención que crea Odoo**: el simulador genera la suya, con su propio id |
| ❌ | El ruteo por `pos_id` — sigue necesitando la terminal física (caso C0) |
| ❌ | El polling del POS: Odoo consulta *su* intención, no la del simulador |

O sea: valida la mitad entrante del contrato, que es justamente la que hoy tenemos mal mapeada.

### 3.4 Tarjetas de prueba (`tasks/doc_checkout.md` §11)

| Tarjeta | Resultado | Número | Venc | CVV |
|---|---|---|---|---|
| Naranja crédito | APPROVED | 5895 6248 4026 3355 | 04/40 | 928 |
| Naranja crédito | REJECTED | 5895 6248 9347 1379 | 07/40 | 374 |
| Naranja crédito | REJECTED | 5895 6134 3478 9277 | 04/40 | 990 |
| Visa crédito 1 cuota | APPROVED | 4025 2200 0000 0139 | cualquiera | cualquiera |
| Visa crédito 6 cuotas | APPROVED | 4761 2299 9900 0231 | 12/31 | 078 |
| Visa crédito 1 cuota | REJECTED | 4025 2200 0000 0127 | cualquiera | cualquiera |

---

## 4. Matriz de casos de prueba

### 4.0 Qué se puede ejecutar HOY, sin esperar ningún fix

La matriz la ejecutás vos (D6). Dado que 11 bloqueantes están abiertos, **no arranques por el
principio**: la mayoría de los casos van a fallar por razones ya conocidas y sólo generan ruido.
Este es el orden que rinde:

**Tanda 0 — lo primero, con el simulador de Nave** (§3.6): **S1 a S8**. No requiere terminal, no
requiere tocar código, y S2/S3 confirman o desmienten B11 — que es el bloqueante que reordena todo
el trabajo sobre el POS. Quince minutos bien invertidos.

**Tanda 1 — ahora mismo, sin tocar código** (línea de base y confirmación de diagnósticos):

| Caso | Por qué ahora |
|---|---|
| E0.1 a E0.4 | Línea de base. Confirma B10 y deja flake8/bandit en verde antes de tocar nada |
| A1 | 30 segundos: abrí el checkout del sitio y mirá qué métodos aparecen. Confirma o descarta B7 |
| C0 | Encendé la terminal `L40000978` y lanzá un cobro. Confirma o descarta el `pos_id` duplicado (§3.5). **No sigas con el bloque C hasta resolver esto** |
| D1c a D3c | `curl` contra el webhook. D1c ya está ✅ |
| E1c | La prueba de SSRF. Es la que más conviene tener documentada antes de arreglarla |
| E3c | Abrí el provider con un usuario de contabilidad y mirá qué campos ve |

**Tanda 2 — después de B11** (destraba el POS entero): C1, C2, C2b, C3, C4, y S9/S10 contra Odoo.

**Tanda 3 — después de B1** (destraba el link): todo el bloque B.

**Tanda 4 — después de B6**: A14, A15, B9c, C13.

**Tanda 5 — después de B8**: bloque H completo.

Lo que **no** conviene ejecutar todavía: A8, C5 a C9, C14, D8c, D9c. Ya sabemos que fallan y por qué;
ejecutarlos ahora sólo consume terminal y tiempo. Se corren como regresión después de los fixes.

### 4.2 Precedente: el checkout ya funcionó end-to-end una vez

Las tres transacciones del 2026-08-11 en la base son de Nave (provider 18), con URLs
`sandbox-hosted-checkout.ranty.io/nave?payment_request=…` y sus `payment_request_id` / `payment_id`
de Nave. El provider `mercado_pago` (id 8) tiene cero transacciones.

| tx | Ref | Estado | Monto | Qué muestra |
|---|---|---|---|---|
| 2 | `S00043` | `draft` | 750,00 | Intención creada, abandonada |
| 3 | `S00043-1` | `error` | 750,00 | Webhook **sí llegó** (tiene `nave_payment_id`), pero el GET de verificación falló |
| 4 | `S00043-2` | `done` | 810,00 | **Camino feliz completo**: intención → pago por billetera → webhook → GET de verificación OK → `done` |

**Esto es la mejor noticia del relevamiento**: el caso A2 tiene precedente real. El flujo de checkout
—crear intención, redirigir al hosted checkout, cobrar, recibir el webhook, verificar server-side y
marcar `done`— ya funcionó una vez de punta a punta contra el sandbox.

**Y explica el último commit.** Correlación de horarios (la base guarda UTC, los commits hora local
AR = UTC-3):

| Hora UTC | Evento |
|---|---|
| 14:16 | tx 3 creada → el GET de verificación falla una y otra vez |
| 15:55 | commit `c3515d8` *"prioritize payment_check_url from webhook payload"* |
| 16:10 | tx 4 creada |
| 16:18 | tx 4 en `done` |

O sea: el fallback `{api_base}/ranty-payments/payments/{id}` no alcanzaba, y usar el
`payment_check_url` que manda Nave en el webhook fue lo que destrabó el flujo.

**Consecuencia directa para B5**: la rama que habilita el SSRF **es la que hace funcionar el
checkout**. El fix no puede ser sacarla — tiene que ser una allowlist de dominio: aceptar
`payment_check_url` sólo si el host es `ranty.io` o subdominio, y si no, caer al fallback.

Pendiente menor: entender por qué falló el GET de la tx 3 (token vencido, host equivocado, 404 del
fallback). No bloquea, pero si vuelve a aparecer en la homologación ya sabemos dónde mirar.

### 4.1 Cómo registrar cada caso

Para cada caso ejecutado, mandame:

1. **ID del caso** y resultado (✅ / ❌ / ⚠️).
2. **Qué viste** en pantalla, en una línea.
3. **Log del servidor** del momento exacto:
   ```bash
   ssh oracle-vps "docker service logs --since 5m do-onlyone_odoo 2>&1 | grep -iE 'nave|payment'"
   ```
4. Si hubo request a Nave: el payload y la respuesta cruda.

Con eso actualizo la matriz, diagnostico y te digo si es un bloqueante conocido o algo nuevo.


Convención de estado: ⬜ pendiente · ✅ pasa · ❌ falla · ⚠️ pasa con observación · 🚫 bloqueado

### Bloque E0 — Verificación de base (antes que nada)

| ID | Caso | Resultado esperado | Estado |
|---|---|---|---|
| E0.1 | `odoo-bin -c odoo.conf -d nave_test -i payment_nave --test-enable --stop-after-init` | 10/10 tests pasan | ⬜ |
| E0.2 | Ídem `pos_nave` | Se espera **4 de 5 fallando** (ver B10). Confirma el diagnóstico | ⬜ |
| E0.3 | `flake8 --config=setup.cfg payment_nave/ pos_nave/ sale_nave_simulator/` | 0 errores | ✅ **0 errores** (2026-09-21). Se limpiaron las 22 marcas preexistentes; AST verificado idéntico a HEAD en los 3 archivos de `payment_nave` | ✅ |
| E0.4 | `bandit -r payment_nave/ pos_nave/ sale_nave_simulator/ --exclude '*/demo,docs,tests' -ll` | 0 hallazgos ≥ medio | ✅ **0 issues** (2026-09-21, bandit 1.9.4, 1233 líneas). El comando de `.agent/rules.md` llevaba `-c setup.cfg`, que hacía abortar la corrida — corregido | ✅ |

### Bloque S — Simulador presencial (sin hardware)

> Se ejecuta en `navenegocios.ar/home/developers` (§3.6). **Es la tanda de mayor valor hoy**: confirma
> B11 empíricamente y deja documentado el contrato real antes de escribir una línea de fix.

| ID | Caso | Pasos | Resultado esperado | Estado |
|---|---|---|---|---|
| S1 | Capturar el webhook real | Notificación → URL de `webhook.site` → Guardar. Tipo: **aprobado con tarjeta**. Monto 100. External id `HOMOL-S1`. Generar | Llega el POST. Anotar los campos exactos: ¿`payment_id` + `payment_check_url` + `external_payment_id`, como en `doc_point.md` §3? | ⬜ |
| S2 | **Vocabulario del pago** 🔴 | `GET {payment_check_url}` con el Bearer de sandbox | `status.name == "APPROVED"` | ⬜ |
| S3 | **Vocabulario de la intención** 🔴 | `GET /api/payment_requests/{payment_request_id}` con el mismo token | **Se espera `SUCCESS_PROCESSED`, no `APPROVED`** → confirma B11 | ⬜ |
| S4 | Rechazo con tarjeta | Tipo: **rechazado con tarjeta**. Repetir S1-S3 | Pago: `REJECTED` + `reason_code`. Intención: `FAILURE_PROCESSED`. Anotar ambos | ⬜ |
| S5 | Aprobado con QR | Tipo: **aprobado con QR** | Mismo contrato + **`wallet.name`** presente (`doc_qr.md` §5) | ⬜ |
| S6 | Rechazado con QR | Tipo: **rechazado con QR** | Ídem S4, y confirmar si aparecen `ERROR_ENCODE_DYNAMIC_QR` / `NO_GATEWAYS_AVAILABLE` | ⬜ |
| S7 | Diferencias tarjeta vs QR | Comparar los cuatro payloads de S1-S6 | Documentar si el contrato de webhook es idéntico o difiere por tipo | ⬜ |
| S8 | Campos del ticket | Del JSON de S2 | Verificar presencia de `payment_code`, `card_brand`, `card_last4`, `installment_plan` (insumo de C12) | ⬜ |
| S9 | Webhook contra Odoo | Notificación → `https://www.onlyone.ar/payment/nave/webhook`, External id = referencia de una tx existente | Odoo procesa el webhook de punta a punta. Valida el controller con tráfico real de Nave | ⬜ |
| S10 | Reintentos | En S9, devolver 500 adrede (External id inexistente) | Nave reintenta a los 10 s, 70 s, … Confirma el comportamiento de `doc_point.md` §3 | ⬜ |

**S2 y S3 son los dos casos más importantes de todo el plan hoy**: son quince minutos de trabajo y
deciden cómo se escribe el fix de B11.

### Bloque A — Checkout e-commerce

| ID | Caso | Pasos | Resultado esperado | Estado |
|---|---|---|---|---|
| A1 | Métodos visibles en checkout | Carrito → Pagar | Se listan los métodos habilitados de Nave. **Hoy se espera que sólo aparezca QR** (B7) | ⬜ |
| A0 | ⚠️ Forma de pago en sandbox | Llegar al hosted checkout y ver qué ofrece | ¿Formulario de tarjeta, o sólo QR para escanear con billetera? **Define si A2-A6 son ejecutables como están redactados** (N11, §3.9.f) | ⬜ |
| A2 | Pago aprobado con tarjeta Naranja | Carrito → Nave → `5895 6248 4026 3355` | Redirige a `checkout_url`, vuelve a `/payment/status`, webhook llega, tx `done`, pedido confirmado. **Tiene precedente: ya pasó el 2026-08-11 (§4.2)** | ⬜ |
| A3 | Pago aprobado con Visa 1 cuota | `4025 2200 0000 0139` | Ídem A2 | ⬜ |
| A4 | Pago aprobado con Visa 6 cuotas | `4761 2299 9900 0231` | Ídem A2 + verificar que el plan de cuotas queda registrado | ⬜ |
| A5 | Rechazo por fondos | `4025 2200 0000 0127` | tx → `cancel` con el `reason_code` de Nave en el chatter | ⬜ |
| A6 | Rechazo Naranja | `5895 6248 9347 1379` | Ídem A5 | ⬜ |
| A7 | Abandono del checkout | Llegar a Nave y cerrar la pestaña | tx queda `draft`/`pending`, el pedido no se confirma, sin asientos | ⬜ |
| A8 | Expiración de la intención | Crear intención y esperar los 3000 s del `duration_time` hardcodeado (`payment_transaction.py:80`) | Nave marca `EXPIRED`. **Se espera `_set_error` "Estado desconocido"** — `EXPIRED` no está mapeado | ⬜ |
| A9 | Monto con decimales | Pedido por $1.234,56 | `amount.value == "1234.56"` (string, 2 decimales) en el payload | ⬜ |
| A10 | Cliente sin CUIT ni email | Partner incompleto | Se envían los defaults `'00000000'` / `'correo@temporal.com'` (`payment_transaction.py:199,205`). Confirmar que Nave los acepta | ⬜ |
| A11 | CUIT con guiones | Partner con `20-05536168-2` | El módulo no limpia guiones (`:196-200`). Verificar si Nave lo rechaza | ⬜ |
| A12 | Descuadre productos vs total | Pedido con IVA | Los `products[]` van **sin IVA** (`price_reduce_taxexcl`, `:157`) pero `amount` **con** IVA. Confirmar que Nave no valida la suma | ⬜ |
| A14 | Devolución total desde backend 🔴 | Factura pagada → botón Reembolsar | `DELETE /api/payments/{id}` → `CANCELLING`, tx hija creada. Odoo **no debe ofrecer monto parcial** (`full_only`, N10). 🚫 Hoy el botón no existe (B6) | ⬜ |
| A15 | Cierre del ciclo de devolución 🔴 | Tras A14, esperar el webhook `REFUNDED` | La transacción y la factura reflejan la devolución. 🚫 Hoy el webhook **no cambia nada** (B6.4) | ⬜ |
| A13 | Cantidad fraccionaria | Línea con qty 0,5 | `int(qty) or 1` → se envía 1 (`:151`). Verificar impacto | ⬜ |

### Bloque B — Link de pago

> 🚫 **Todo este bloque está bloqueado por B1** hasta que el wizard cree la `payment.transaction`.

| ID | Caso | Pasos | Resultado esperado | Estado |
|---|---|---|---|---|
| B1c | Generar link desde factura | Factura confirmada → Acción → Generar Link | Link `https://checkout.ranty.io/link/...` en el wizard y posteado al chatter | ⬜ |
| B2c | Generar link desde pedido de venta | Ídem sobre `sale.order` | Ídem | ⬜ |
| B3c | Pago del link → conciliación | Abrir el link en incógnito y pagar | Webhook llega, **factura pasa a Pagada**. 🚫 Hoy: 500 + reintentos + factura impaga (B1) | ⬜ |
| B4c | Duración del link | Probar 24 h, 48 h y 168 h (las tres opciones del panel, §3.9.g) | El link expira al plazo indicado. Verificar el estado que notifica Nave | ⬜ |
| B5c | Duración inválida | `duration_hours = 0`, negativo, o > 168 | Debería rechazarse; **hoy no hay validación** (`nave_link_wizard.py:71-75`). El tope razonable es 168 h (§3.9.g) | ⬜ |
| B6c | Regenerar link de la misma factura | Generar dos veces | Mismo `external_payment_id` truncado (`:179`). **El panel dice que cada link es único y de un solo uso** (§3.9.h) → verificar si Nave lo rechaza | ⬜ |
| B7c | Retorno del pagador | Pagar el link | El payload del link **no incluye `callback_url`** → el pagador no vuelve a Odoo. Confirmar si Nave lo exige | ⬜ |
| B9c | Devolución de un pago por link | Pago del link aprobado → devolver | Mismo ciclo que A14/A15. Depende de B1 (sin tx no hay nada que devolver) | ⬜ |
| B8c | Link sobre nota de crédito | Acción sobre un `out_refund` | El wizard abre y cobraría (`:108-118`). Definir si debe bloquearse | ⬜ |

### Bloque C — Smart Point (terminal física)

> Terminal disponible: **serie `L40000978`**.
> 🔴 **Bloqueado por P12** hasta confirmar qué `pos_id` corresponde a esa terminal (§3.5).

| ID | Caso | Pasos | Resultado esperado | Estado |
|---|---|---|---|---|
| C0 | Ruteo a la terminal correcta 🔴 | Lanzar un cobro con el `pos_id` actual | El cobro **aparece en la terminal `L40000978`**. Si no aparece, el `pos_id` es el de e-commerce (§3.5) y hay que pedirle a Nave el de la terminal | ⬜ |
| C1 | Contrato de estados 🔴 | Cobrar y capturar la respuesta cruda de `GET /api/payment_requests/{id}` | Documentar la forma exacta de `status` y el catálogo completo de valores. **Todo el polling depende de una suposición del código** (`payment_nave.js:124`: *"suponiendo estructura {status:{name:...}}"*) | ⬜ |
| C2 | Cobro aprobado con chip | Orden POS → Tarjeta → insertar chip → aprobar | Línea `done`, orden validada, `transaction_id` guardado | ⬜ |
| C3 | Cobro rechazado | Tarjeta de rechazo en la terminal | Diálogo con el `reason_code`, línea en `retry`, el cajero puede reintentar | ⬜ |
| C4 | Cancelación desde Odoo | Iniciar cobro → botón Cancel | `DELETE` a Nave y la **terminal vuelve a reposo**. Ojo: `send_payment_cancel` retorna `true` siempre, incluso si el DELETE falló (`payment_nave.js:185-190`) | ⬜ |
| C5 | Cancelación desde la terminal | Iniciar cobro → cancelar en el equipo | Nave notifica `DISABLED` con `manual_disabled_by_user`. **Se espera loop infinito** (B4) | ⬜ |
| C6 | Expiración de la intención | Iniciar cobro y no tocar nada 300 s | Nave marca `EXPIRED`. **Se espera loop infinito** (B4) | ⬜ |
| C7 | Salir de la pantalla de pago | Iniciar cobro → botón Back | La intención queda viva: **la terminal sigue cobrable**. No hay `close()` implementado | ⬜ |
| C8 | Corte de red durante el polling 🔴 | Iniciar cobro y cortar la conexión de Odoo | **Se espera spinner infinito sin diálogo de error** (B4). Verificar que la única salida es "Force done" | ⬜ |
| C9 | "Force done" con pago rechazado | Rechazar en la terminal y presionar Force done | La venta se cierra como cobrada sin cobro real. **Hallazgo a documentar y mitigar** | ⬜ |
| C10 | Terminal ocupada | Lanzar un cobro con otro en curso | `device_already_on_payment_flow` (`doc_point.md` §6). Verificar el mensaje al cajero | ⬜ |
| C11 | Terminal con batería < 5% | Descargar la terminal | `low_battery`. Verificar manejo | ⬜ |
| C12 | Datos en el ticket | Cobro aprobado → imprimir | **Hoy no se llama a `set_receipt_info()`**: el ticket no imprime marca, últimos 4 ni cupón, aunque la API los devuelve (`doc_point.md:104-138`). Confirmar si Nave lo exige | ⬜ |
| C13 | Devolución desde POS | Orden de devolución → Tarjeta | 🚫 Falla por B2/B3 (`REFUND-CIEGO`) | ⬜ |
| C14 | Webhook de baja de intención | Provocar un `DISABLED` | Es un **segundo contrato de webhook** con payload distinto (`payment_request_id`, `disabled_reason`, `doc_point.md` §8) que el módulo **no maneja** | ⬜ |
| C15 | Cierre de caja | Cerrar la sesión POS con cobros Nave | Los pagos quedan en el diario del método. No hay conciliación contra Nave | ⬜ |

### Bloque H — QR interoperable presencial

> 🚫 **Bloqueado por B8** (desarrollo pendiente). Se puede ejecutar **sin billetera real** usando el
> endpoint de simulación de sandbox: `GET /instore/external/resolve?data={QR_FIJO}&access_token={TOKEN}`
> (`doc_qr.md` §10), que dispara el pago y el webhook end-to-end.

| ID | Caso | Pasos | Resultado esperado | Estado |
|---|---|---|---|---|
| H1 | Alta y descarga del QR | *Nave > Negocios > elegí el local > Descargar* (§3.9.d). Ojo: con Nave Point habilitado **no llega el kit POP impreso** | Se obtiene el QR y su `pos_id` (`doc_qr.md` §1) | ⬜ |
| H2 | Crear intención | Orden POS → método "Nave QR" | `POST /static_qr` con `qr_amount: "close"` y `amount.value` string de 2 decimales | ⬜ |
| H3 | Pago simulado aprobado | Llamar al endpoint de simulación | Webhook llega, línea `done`, orden validada | ⬜ |
| H4 | Billetera usada | Ídem H3 | `wallet.name` (ej. `"mercado pago"`, `"modo"`) queda registrado para conciliación | ⬜ |
| H5 | Pago con billetera real | Escanear el QR físico desde una app | Mismo resultado que H3 | ⬜ |
| H6 | Expiración | Crear intención y esperar el `duration_time` | `EXPIRED` manejado sin loop (depende de B11/B4) | ⬜ |
| H7 | Cancelar intención | Cancelar desde el POS | `DELETE /api/payment_requests/{id}`, el QR deja de cobrar | ⬜ |
| H8 | Errores propios de QR | Forzar la condición | `ERROR_ENCODE_DYNAMIC_QR` y `NO_GATEWAYS_AVAILABLE` con mensaje claro al cajero (`doc_qr.md` §9) | ⬜ |
| H9 | Devolución | Devolver un pago QR aprobado | `DELETE /api/payments/{payment_id}` → `CANCELLING` → estado final asincrónico | ⬜ |
| H10 | Path de auth | Capturar el request de token | `doc_qr.md` §2 usa `m2ms`, el código usa `m2msPrivate` (N3) | ⬜ |

### Bloque D — Webhooks y resiliencia

| ID | Caso | Pasos | Resultado esperado | Estado |
|---|---|---|---|---|
| D1c | Preflight OPTIONS | `curl -X OPTIONS .../payment/nave/webhook` | 200 con headers CORS. ✅ **verificado: responde 200** | ✅ |
| D2c | JSON inválido | POST con body roto | 400 "Invalid JSON" | ⬜ |
| D3c | Campos faltantes | POST sin `payment_id` | 400 | ⬜ |
| D4c | Referencia inexistente | POST con `external_payment_id` inventado | **500 + Nave reintenta en loop**. Evaluar responder 200 ante fallos permanentes | ⬜ |
| D5c | Webhook duplicado | Enviar el mismo webhook dos veces | Idempotente: sin doble asiento | ⬜ |
| D6c | Webhook fuera de orden | `APPROVED` y después `PENDING` | La tx no debe retroceder de `done` | ⬜ |
| D7c | Reintentos de Nave | Devolver 500 en el primer intento | Nave reintenta a los 10 s y concilia en el segundo | ⬜ |
| D8c | Pérdida total del webhook | Bajar el sitio > 7h45m y pagar | 🚫 La tx queda pendiente para siempre — **no hay cron de respaldo** (B9) | ⬜ |
| D9c | `REFUNDED` sobre tx `done` | Simular el webhook | `_set_canceled` no admite `done` → **warning y sin efecto** (`payment_transaction.py:297-299`) | ⬜ |
| D10c | Token vencido a mitad de sesión | Forzar expiración | No hay reintento ni invalidación reactiva ante 401 (`payment_provider.py:60-129`) | ⬜ |

### Bloque E — Seguridad

| ID | Caso | Pasos | Resultado esperado | Estado |
|---|---|---|---|---|
| E1c | SSRF vía `payment_check_url` 🔴 | POST al webhook con una `reference` válida y `payment_check_url` apuntando a un host propio que responda `APPROVED` | **Debe rechazarse.** Hoy se marca la factura como pagada (B5) | ⬜ |
| E2c | Webhook sin autenticación | POST anónimo con datos plausibles | Mitigado sólo por el GET de verificación. Documentar la postura ante Nave | ⬜ |
| E3c | Secret expuesto | Usuario sin `base.group_system` abre el provider | `nave_client_secret` oculto; **`nave_client_id` no tiene `groups`** y sí se ve (`payment_provider.py:21-25`) | ⬜ |
| E4c | Bandit sobre los tres módulos | E0.4 | 0 hallazgos ≥ medio | ✅ **0 issues** (2026-09-21). ⚠️ Bandit **no detecta el SSRF de B5**: pasar este chequeo no sustituye a E1c | ⬜ |

### Bloque F — Contabilidad y conciliación

| ID | Caso | Pasos | Resultado esperado | Estado |
|---|---|---|---|---|
| F1 | Asiento del cobro online | A2 completo | Asiento en el diario del provider, factura conciliada | ⬜ |
| F2 | Asiento del cobro POS | C2 + cierre de sesión | Asiento correcto en el diario del método de pago | ⬜ |
| F3 | Trazabilidad | Cualquier cobro | `nave_payment_id` visible en la transacción. Nota: **`provider_reference` queda vacío** — Odoo lo usa para trazabilidad estándar | ⬜ |
| F4 | Total vs monto cobrado | Pedido con lista de precios Nave | Total del pedido == `amount.value` == monto en el panel de Nave | ⬜ |

### Bloque G — Multi-compañía

> La demo corre íntegra sobre la compañía 4 (D3), así que este bloque **no está en el camino crítico**.
> Excepción: **G2 y G4 sí importan**, porque se disparan al pasar a producción — el día que se agregue
> un provider `enabled` junto al `test` actual, la selección deja de ser determinística.

| ID | Caso | Pasos | Resultado esperado | Estado |
|---|---|---|---|---|
| G1 *(secundario)* | Provider por compañía | Segunda compañía sin provider Nave | El wizard no encuentra provider y avisa claramente (`nave_link_wizard.py:134-141`) | ⬜ |
| G2 🔴 | Dos providers en la misma compañía | Uno `test` y uno `enabled` — **el escenario exacto del go-live** | `_get_nave_payment_provider` toma el primero por orden por defecto, **sin preferir `enabled`** (`pos_payment_method.py:30-43`): riesgo de cobrar contra el ambiente equivocado | ⬜ |
| G3 *(secundario)* | Mensaje de error engañoso | Provider faltante en compañía B | El mensaje usa `self.env.company.name` aunque la búsqueda usó `self.company_id` (`:41`) | ⬜ |
| G4 | Provider `disabled` | Poner el provider en `disabled` y forzar una llamada | `_nave_get_api_url()` cae en la **rama de producción** con `disabled` (`payment_provider.py:138-143`) | ⬜ |

---

## 5. Criterios de aceptación

La homologación se considera lista para presentar a Nave cuando:

1. **B1 a B6 cerrados** y con test de regresión que los cubra.
2. **Bloque A completo en verde**, con al menos un aprobado y un rechazo por cada marca de tarjeta.
3. **Bloque B completo en verde** — incluyendo B3c, que hoy es el corazón del problema.
4. **Bloque C**: C1 a C4 y C12 en verde; C5 a C9 con comportamiento **definido y documentado**
   (no necesariamente perfecto, pero nunca un loop infinito ni un cobro fantasma).
5. **Devolución total demostrable de punta a punta** en los cuatro flujos: botón visible, DELETE
   aceptado por Nave, y el webhook de confirmación reflejado en Odoo (A14, A15, B9c, C13, H9).
6. **E1c cerrado**: el SSRF no es negociable.
7. **E0.1 a E0.4 en verde**: tests, flake8 y bandit limpios (§6 de `.agent/rules.md`).
8. Evidencias completas según §6.

---

## 6. Evidencias para Nave

Para cada caso ejecutado:

- Captura o video de la pantalla de Odoo (checkout, wizard o POS).
- Para los presenciales: **video simultáneo de la pantalla del POS y de la terminal** (requisito
  presunto de nuestros docs internos — confirmar en P2).
- Log del servidor filtrado por `[payment_nave]` / `[pos_nave]` con timestamp.
- Captura del panel de Nave mostrando la transacción del lado de ellos.
- Payload del request y de la respuesta (anonimizando credenciales).
- Para el ticket POS: foto del cupón impreso con últimos 4 dígitos y número de autorización.

Estructura sugerida: `evidencias/<ID_caso>/` con `pantalla.mp4|png`, `odoo.log`, `payload.json`, `nave_panel.png`.

---

## 7. Preguntas abiertas

> 📌 **Actualización 2026-09-22**: se relevó la documentación oficial vigente del DevPortal de Nave.
> Ver `tasks/doc_actualizada_2026-09-22.md`. Resolvió N2, N3, N5, N9 y N11, confirmó B11, destrabó B3
> y abrió N12. Los `doc_*.md` locales quedaron marcados como supersedidos.

### Para Nave (bloquean el arranque)

- **N1** — ¿Cuál es el **checklist oficial de homologación**? Lo que tenemos internamente
  (`docs/Modulo Nave - Cobros Online.md` §Fase 3 y `docs/Modulo Nave - Pagos Presenciales.md`
  §Consideraciones) está prefaciado con *"Probablemente…"*: son **suposiciones nuestras, no
  requisitos confirmados**. Todo el §5 se recalibra con la respuesta.
- **N2** ✅ **RESUELTA por la doc (2026-09-22)** — Nave Point usa **`https://e3-api.ranty.io`** en
  sandbox; checkout, link y QR usan `api-sandbox.ranty.io`. Nuestro código usa uno solo para todo, y
  para Nave Point es el equivocado. El test que esperaba `e3-api` tenía razón.
- **N3** ✅ **RESUELTA por la doc (2026-09-22)** — Las cuatro páginas usan `m2msPrivate` en sus
  cuadros de endpoint. Nuestro código está bien.
- **N4** ✅ **Resuelta por la doc (2026-09-21)** — `doc_qr.md` §8 y `doc_point.md` §7 confirman
  `DELETE {api-base}/api/payments/{payment_id}`, que es exactamente lo que usa el módulo
  (`payment_transaction.py:322`). El host `punku` del plugin de WooCommerce es otra API, no la
  vigente. Queda sólo confirmar si la devolución **parcial** existe: `doc_point.md` §7 dice "total o
  parcial" pero no documenta cómo enviar el monto.
- **N5** ✅ **RESUELTA por la doc (2026-09-22)** — `PARTIALLY_REFUNDED` **no figura** en la tabla de
  estados de pago vigente. No existe: coherente con N10 (`full_only`).
- **N6** — Conciliación y settlement: ningún doc define cut-off de lote, liquidación ni archivo de
  conciliación, pero los estados `CANCELLED` ("antes del cierre de lote") y `PURCHASE_REVERSED`
  ("antes de liquidarse") implican un ciclo que no está documentado.
- **N7** — ¿Hay rate limit de API, límite de monto o límite de intenciones concurrentes?
- **N8** ✅ **RESUELTA (2026-09-21)** — Trámite hecho. Una sola `notification_url`
  (`https://www.onlyone.ar/payment/nave/webhook`) sirve para ambos ambientes.
- **N12** 🔴 **NUEVA (2026-09-22)** — **¿Cómo se dispara una devolución por API?** El endpoint
  `DELETE /api/payments/{payment_id}` que usa nuestro código **ya no aparece en ninguna de las cuatro
  páginas** de la documentación vigente (verificado: cero ocurrencias de `api/payments/`). Los estados
  `REFUNDED` y `CANCELLED` siguen existiendo, así que la devolución existe. ¿Sigue vigente ese
  endpoint, se mueve a otro, o las devoluciones se hacen sólo desde el panel? **Bloquea B6 y D5.**
- **N10** ✅ **RESUELTA (2026-09-21)** — **No existe la devolución parcial: es `full_only`.** La
  mención "total o parcial" de `doc_point.md` §7 es un error de la doc. Ver §3.8 para el cambio que
  implica.
- **N11** ✅ **RESUELTA por la doc (2026-09-22)** — El ingreso manual de tarjetas es un **flag del
  comercio**: *"si el ingreso manual de tarjetas se encuentra habilitado, puede completarse el pago
  ingresando datos manuales"*. En desktop se muestra QR; en mobile se redirige a MODO. **A2-A6 son
  ejecutables sólo si lo tenemos habilitado** — falta confirmar si es nuestro caso.
- **N9** ✅ **RESUELTA por la doc (2026-09-22)** — Hay **un `pos_id` por punto de venta y por tipo de
  pago**. Se descargan desde **Nave > Integraciones > Sistema de gestión**. Los QR se dan de alta en
  **Nave > Negocios > Agregar medios de cobro > QR**. Lo confirma el error `INVALID_POS` (409):
  *"Given POS is for a different payment type"*. **Acción: bajar ese archivo del panel** — puede
  destrabar el `pos_id` sin esperar el correo.

### Para vos (definen el alcance)

- **D1** ✅ **RESUELTO (2026-09-20)** — `do-onlyone` es el entorno de homologación y la base
  `www.onlyone.ar` tiene datos de homologación. Se homologa ahí, sin base separada. Ver §3.1.
- **D2** ✅ **RESUELTO (2026-09-21)** — Terminal Smart Point de prueba disponible, serie `L40000978`.
  Queda el punto derivado de §3.5: confirmar qué `pos_id` le corresponde (ver N9).
- **D3** ✅ **RESUELTO (2026-09-21)** — Se homologa contra la compañía **4, `(AR) Monotributista)`**,
  donde ya están el provider Nave, el POS "Nave Smart POS" y el website `https://www.onlyone.ar`.
- **D4** ✅ **RESUELTO (2026-09-21)** — Alcance comprometido: **Cobros online (Checkout + Link de
  pago)** y **Cobros presenciales (Nave Point + QR)**. El QR interoperable entra, así que B8 pasa de
  "decisión pendiente" a **desarrollo comprometido**, con su propio bloque de pruebas (H).
- **D5** ✅ **RESUELTO (2026-09-21)** — La devolución **entra**, porque está documentada en los cuatro
  docs de Nave. Alcance: **devolución total** en checkout, link, Smart Point y QR. La parcial queda
  sujeta a N10. Esto convierte B2, B3 y B6 en bloqueantes comprometidos, no opcionales.
- **D6** ✅ **RESUELTO (2026-09-21)** — **La matriz la ejecutás vos**, con guía y soporte mío. Yo
  preparo los casos con pasos concretos, reviso las evidencias y diagnostico los fallos; vos operás
  Odoo, el sitio, la terminal y el QR. Ver §4.0 para el orden de ataque.
- **D7** ✅ **RESUELTO (2026-09-21)** — Las tres son transacciones **de Nave**, no de Mercado Pago
  (el provider `mercado_pago` id 8 tiene **cero** transacciones). "MERCADO PAGO" en el mensaje de la
  aprobada es la **billetera** con que el cliente pagó el QR del checkout de Nave — el campo
  `wallet.name` que describe `doc_qr.md` §5. Ver §4.2: son evidencia útil, no ruido.

---

## 8. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Sin local de prueba: terminal no vinculable | Bloques C y H parados por completo | P13, escalado a Nave hoy (§3.10) |
| Usar por error el QR de **producción** en una prueba | **Cobro real** en la cuenta del comercio | Apartar el QR descargado; no usarlo hasta tener el de sandbox |
| `pos_id` equivocado en la terminal | Los cobros presenciales no llegan al equipo; el Bloque C no arranca | C0 como primera prueba; N9 a Nave |
| "Force done" usado en la demo ante un incidente | Nave ve una venta cobrada sin cobro | Cerrar B4 antes de la demo |
| ~~Descubrir en la demo que el contrato de estados es otro~~ | **Ya ocurrió**: el POS usa el vocabulario equivocado | B11, antes que cualquier otro trabajo sobre el POS |
| QR subestimado por tratarse como "una prueba más" | Desarrollo nuevo descubierto tarde | B8 arranca en paralelo con B11; homologable sin hardware vía simulación |
| SSRF detectado por Nave en su revisión | Homologación rechazada por seguridad | Cerrar B5 (≈5 líneas) |
| Go-live: token de sandbox enviado a producción por hasta 24 h | Caída de cobros el día del switch | §3.7: invalidar token al cambiar `state`; checklist de cutover |
