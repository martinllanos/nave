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

### B9 — Sin cron de respaldo si se pierde el webhook ✅ RESUELTO

No existe ningún `ir.cron` en `payment_nave` (confirmado también en la base del servidor: cero crones
con "nave" en el nombre). Nave reintenta durante ~7h45m y se rinde. Si el sitio estuvo caído más que
eso, la transacción queda en Pendiente **para siempre**.

El plugin oficial de Nave resuelve esto con un cron cada 15 min que re-consulta órdenes pendientes
(`docs/nave-for-woocommerce/src/Handler/CronHandler.php:27-28,72-93`). Recomiendo replicarlo: es la
diferencia entre "se nos perdió un pago" y "se recupera solo".

**Resuelto** en `_cron_nave_poll_pending_transactions` (`payment_transaction.py`): re-consulta las
transacciones Nave en `draft` o `pending` con más de 30 minutos y menos de 2 días, con un savepoint
por transacción para que una falla no se lleve puesto el lote. Los dos límites se ajustan con
`payment_nave.poll_min_age_minutes` y `payment_nave.poll_max_age_days`. Verificado con datos reales
en §3.19.

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
| P13 | Vincular la terminal `L40000978` | Comercial | ✅ **RESUELTO 2026-09-23**. Nave mandó un código nuevo y la terminal quedó vinculada. Confirmó además el mismo `pos_id` `b1c04ade-…` |
| P16 | Cobro con tarjeta física | Comercial | ⏳ **destrabado**: la terminal de **producción** `L40037644` llegó antes de lo previsto y ya está vinculada (2026-09-26). Se prueba con plástico real bajo los topes de §3.11. Los rechazos se provocan con tarjeta vencida o CVV incorrecto (§3.16) |
| P17 | 🔴 Obtener el **`pos_id` de la terminal de producción** `L40037644` | Comercial | ⏳ Terminal vinculada el 2026-09-26. Su `pos_id` no figura en la planilla de *Sistema de gestión* descargada antes de la vinculación: hay que bajarla de nuevo. Ver la tabla de §3.16 |
| P15 | Cargar el `pos_id` de la terminal (`b1c04ade-…`) en el método de pago POS | Técnico | ✅ **hecho 2026-09-23**. Requirió cerrar la sesión POS/00005: Odoo no deja modificar un método de pago con sesiones abiertas |
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

### 3.5 ✅ RESUELTO: el `pos_id` de la terminal es otro (y ya lo teníamos)

**Nave lo respondió el 2026-08-14**, en el hilo *"Nave Point: S/N: L40000978 (DEBUG) - Pide soporte
técnico"* con `integraciones@navenegocios.com`:

```
Terminal: L40000978
pos_id: b1c04ade-dec9-4ca0-9fd9-8464c9006764
2FA: <código de vinculación>   (no se transcribe: es de un solo uso)
Nota: Reiniciar la terminal e ingresar el código de vinculación
```

| | `pos_id` |
|---|---|
| Terminal Nave Point `L40000978` | `b1c04ade-dec9-4ca0-9fd9-8464c9006764` |
| Tienda e-commerce (cargado hoy en `nave_pos_id` **y** en `nave_terminal_id`) | `f71ba756-1d80-4ab3-9f43-5dc247fd6c4a` |

**Son distintos, y el que está cargado en el POS es el de e-commerce.** Queda confirmado todo lo que
veníamos sospechando:

- Hay un `pos_id` por dispositivo y por tipo de pago (§3.9.k y el error `INVALID_POS`).
- El POS venía mandando el identificador de la tienda online en `seller.pos_id` para `smart_pos`.
- **Esa es, casi con certeza, la causa del "404" que motivó el commit `ffb524b`**, que cambió el host
  de `e3-api` a `api-sandbox` para esquivarlo. El host estaba bien; lo que estaba mal era el `pos_id`.

**Acción**: cargar `b1c04ade-dec9-4ca0-9fd9-8464c9006764` en el `nave_terminal_id` del método de
pago POS "Tarjeta" (id 3), y dejar `f71ba756-…` sólo en el `nave_pos_id` del proveedor.

**Y destraba la vinculación de la terminal**: Nave no pidió un local "test", sino reiniciar el equipo
e ingresar el código de vinculación que mandó. Ver §3.10.

<details>
<summary>Diagnóstico original (previo a encontrar la respuesta de Nave)</summary>

### El `pos_id` de la terminal estaba duplicado del de e-commerce

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

### 3.12 Primer cobro real contra la terminal (2026-09-23)

Se lanzó un cobro de $ 1.925,45 desde el POS con el código nuevo desplegado. Resultado:

```
Error al solicitar cobro
HTTPSConnectionPool(host='e3-api.ranty.io', port=443): Read timed out. (read timeout=10)
```

**Lo que confirma:**

- El host es **`e3-api.ranty.io`**: el fix de N2 está efectivamente corriendo.
- **B11 y B4 verificados en un cobro real**: el POS cortó, mostró el diálogo y dejó la línea en
  "Volver a intentar". Con el código anterior habría sido un spinner infinito cuya única salida era
  "Force done".

**No es un problema de red.** Medido desde adentro del contenedor de Odoo:

| Host | Respuesta |
|---|---|
| `e3-api.ranty.io` | 403 en 0,30 s |
| `api-sandbox.ranty.io` | 403 en 0,27 s |
| `api.ranty.io` | 403 en 0,23 s |

Los tres resuelven a las mismas IPs de Cloudflare. **El commit `ffb524b` esquivaba un host que
siempre estuvo sano.**

**Causa probable**: crear una intención `smart_pos` obliga a Nave a alcanzar la terminal física
antes de contestar, y la terminal **todavía no está vinculada** (§3.10). El timeout se subió a 30 s
(`65feb6e`), lo que ordena el comportamiento para un equipo lento en 4G, pero **no destraba el bloque
C**: si el dispositivo no responde, con 30 s va a tardar más en fallar y va a fallar igual.

Si una vez vinculada la terminal el cobro vuelve a dar timeout con 30 s, es un problema distinto y
hay que reportárselo a Nave con esta evidencia.

### 3.43 H8: errores al crear el cobro con QR (2026-10-09)

**Lo que documenta Nave hoy** (página del QR interoperable, *Códigos de errores*; leída del
`chunk-3SROTMK6.js` el 2026-10-09). Son errores al **crear** la intención, no desenlaces de un pago:

| Código | Qué significa, según Nave | HTTP del ejemplo |
|---|---|---|
| `ERROR_ENCODE_DYNAMIC_QR` | Falló la generación del QR (*"Error-timeout of 2500ms exceeded"*) | 500 |
| `NO_GATEWAYS_AVAILABLE` | Ningún gateway del tipo de pago está disponible | 409 |
| `PAYMENT_TYPE_IS_NOT_OPERATIVE` | El circuito del tipo de pago está fuera de servicio | 503 |
| `INVALID_POS` | El `pos_id` es de otro tipo de integración | 409 |
| `APPLICATION_ERROR_SERVICE` | No hay aplicación asociada al `client_id` | 404 |
| `CLIENT_VALIDATION_FAILED` | Faltan campos o son inválidos | 404 |
| `INTERNAL_SERVER_ERROR` | Error genérico, por ejemplo un JSON mal formado | 500 |

La página de Nave Point documenta un subconjunto con otra forma: `api_status_error` (*"Payment type
is not operational"*), `invalid_pos` e `internal_server_error`.

**Lo que devuelve la API de verdad.** Sólo se puede provocar `INVALID_POS`. Sondeado en producción
con un cobro de $15 que Nave rechazó, sin tocar la configuración:

- QR con el `pos_id` de la terminal → `400 {"code":"invalid_pos","message":"Given POS is for a different payment type"}`
- Nave Point con el `pos_id` del QR → la misma respuesta

La forma real es la de Nave Point (`code` en minúsculas, HTTP 400), no la del ejemplo del QR
(`message` en mayúsculas, 409). `payment_nave` ya contempla las dos formas para registrar
`invalid_pos` en los cobros online (`_nave_log_invalid_pos`, test 34).

**Lo que ve hoy el cajero.** `_nave_error_message` arma el texto con lo que mande Nave. Para
`invalid_pos`, el cajero lee *"Given POS is for a different payment type (HTTP 400)"*. Para
`ERROR_ENCODE_DYNAMIC_QR` leería *"ERROR_ENCODE_DYNAMIC_QR: Error-timeout of 2500ms exceeded
(HTTP 500)"*. Está en inglés, es técnico y no dice qué hacer. H8 pide un mensaje claro. Tampoco se
registra el `invalid_pos` con el medio y el `pos_id`, como sí se hace en los cobros online.

**Para resolver:** un catálogo de errores al crear el cobro, que reconozca las dos formas, con un
mensaje en castellano que diga qué pasó y qué hacer, y el código para soporte. Es el mismo criterio
de *speak-to-the-cashier-not-the-api*. Los errores que no se pueden provocar se prueban con las
respuestas documentadas.

**Corregido en `explain-intent-errors-to-the-cashier`** (`payment_nave 18.0.1.12.4`, `pos_nave
18.0.1.11.3`). Hay un catálogo de los siete errores, que reconoce las dos formas de Nave; lo que no
está en el catálogo sigue como antes. Lo verifican 9 tests con las respuestas documentadas y la real.

Verificado en producción el 2026-10-09 con un sondeo por shell sin guardar nada: un método QR
temporal con el `pos_id` de la terminal, descartado al terminar. Nave respondió
`400 invalid_pos`, y el servidor devolvió al POS:

> El ID del punto de venta de este método de pago pertenece a otro medio de cobro de Nave. Avisá al
> administrador para que lo corrija en el método de pago.
>
> Para soporte: Código: invalid_pos · HTTP: 400

El log registró la respuesta de Nave y el `invalid_pos` con el medio (`static_qr`) y el `pos_id`. La
prueba en la pantalla del POS se omitió de común acuerdo: con una sesión abierta, Odoo no deja
modificar el método de pago, y el POS muestra el texto del servidor tal cual.

**Pendiente menor:** el registro de `_nave_log_invalid_pos` dice *"revisá la configuración del
proveedor"*; en el POS, lo que hay que revisar es el método de pago.

### 3.42 Cierre de caja y asientos del POS (2026-10-09)

Cierre de la sesión `POS/00001`, abierta desde el 2026-10-06: 16 órdenes por $5.154,34, todas
facturadas. La ventana de cierre mostró Nave Point $1.623,44 y Nave QR $147,00, los dos sin
diferencia, y el efectivo se contó en lo esperado.

| Qué se revisó | Resultado |
|---|---|
| Asiento de la sesión `POSS/2026/10/0017` | ✅ Publicado y cuadrado. Mueve *Créditos por ventas (PoS)* por método: $1.623,44, $147,00 y $3.383,90, todo conciliado |
| Cobros de Nave (C15) | ✅ Un `account.payment` por método en el diario **Banco**: `PBNK1/2026/00012` (Nave Point, $1.623,44) y `PBNK1/2026/00013` (Nave QR, $147). Debitan *1.1.1.02.003 Recibos pendientes* y quedan *en proceso* hasta conciliarlos con el extracto. Es el circuito estándar de Odoo |
| Facturas (F2) | ✅ Las 16 quedan pagadas, incluidas las 8 cobradas con Nave |
| Efectivo | El extracto del diario Efectivo registra $3.383,90 |

**Lo que falta para conciliar con el banco (F4):**

- **Nave acredita el neto.** Por los $147 del QR llegaron $145,57, y por los $150 del QR de la
  terminal, $148,55: alrededor de 0,97 % de comisión. En Odoo el cobro queda por el bruto, así que al
  conciliar el extracto queda una diferencia por cada acreditación, y la comisión no está asentada en
  ninguna parte.
- **Un pago por método y por sesión.** Si Nave acredita cada cobro por separado, como en los dos
  pagos con QR, un solo pago de $1.623,44 se concilia contra varias líneas del extracto. Con
  *Identificar cliente* (`split_transactions`) en los métodos de Nave, Odoo crea un pago por cobro, y
  cada uno se concilia con su acreditación.

**El resumen del panel de Nave** (*Detalles > Descargar resumen*, Excel, consultado el 2026-10-09).
Trae una fila por cobro con fecha de operación y de acreditación, código de operación, terminal,
medio de pago, **monto bruto, comisión, IVA de la comisión y neto**, y el **ID externo de pago**: la
referencia que manda Odoo, o sea el `uuid` de la línea de pago del POS. El archivo no se guarda en el
repo, porque trae nombre y CUIT de quien pagó. De las dos filas que cubrió el rango pedido:

| Medio | Bruto | Comisión | IVA comisión | Neto | Acreditación |
|---|---|---|---|---|---|
| Dinero en cuenta (Bind) | $15,00 | $0,00 | $0,00 | $15,00 | el mismo día |
| American Express crédito | $50,00 | $2,40 | $0,50 | $47,10 | el mismo día |

Con los dos QR del 2026-10-08 (§3.40 y §3.41), la comisión fue de ~0,97 %.

**Lo que dice eso:**

- **Nave acredita cada cobro por separado y en el día**, también con tarjeta.
- **La comisión depende del medio**: va de 0 % a casi 6 % con IVA. Un modelo de conciliación con un
  porcentaje fijo no sirve. La diferencia exacta de cada cobro está en el resumen.
- **La comisión lleva IVA discriminado.** Para la contabilidad argentina son dos asientos: el gasto
  por comisión y el IVA crédito fiscal. No alcanza con mandar la diferencia a una sola cuenta.
- **El ID externo de pago une el resumen con Odoo.** Es la referencia de cada línea de pago del POS
  y de cada transacción online.

**La sesión `POS/00001` contra el resumen** (descargado otra vez el 2026-10-09, del 09/09 al
09/10):

| Pago en Odoo | Cobros en Nave | Bruto | Comisión | IVA comisión | Neto acreditado |
|---|---|---|---|---|---|
| `PBNK1/2026/00012` Nave Point | 7, todos con ID externo de Odoo | $1.623,44 | $71,93 | $15,10 | $1.536,41 |
| `PBNK1/2026/00013` Nave QR | 1 (`SMI542294163`) | $147,00 | $1,18 | $0,25 | $145,57 |

- **El bruto coincide al centavo** con los dos pagos de la sesión, y cada cobro de Odoo aparece con su
  `uuid` como ID externo. Los dos pagos sueltos de Belo (`HNP400101313`, `BXL589327838`) figuran
  con ID externo *"-"*: Nave sabe que no salieron de ninguna integración.
- **Tarifas observadas:** tarjeta (Mastercard prepaga, Amex crédito) **4,8 %**, y QR o dinero en
  cuenta **0,8 %**, las dos más el 21 % de IVA sobre la comisión. Un cobro de $15 con dinero en cuenta
  del 05/10 no tuvo comisión. Las cuentas cierran al centavo: bruto − comisión − IVA = neto.
- Para conciliar esta sesión a mano hay que registrar $73,11 de comisiones y $15,35 de IVA crédito
  fiscal, y repartir los dos pagos de Odoo entre las ocho acreditaciones del extracto.

**Identificar cliente con Consumidor Final:** el core sólo exige que la orden tenga cliente
(`_askForCustomerIfRequired`), y el POS ya pone *Consumidor Final Anónimo* por defecto, así que el
cajero no ve ninguna diferencia. Lo que cambia es la contabilidad: un `account.payment` por cobro en
lugar de uno por sesión. Pero la referencia de ese pago es genérica (*"Nave Point POS payment of
Consumidor Final Anónimo in POS/00001"*), así que todos se distinguen sólo por el monto, y el banco
acredita el neto, no el bruto.

**Propuesta:** dejar la conciliación automática para después del MVP. Sería una historia que lea el
resumen de Nave, o una API si existe (consulta 7), y concilie cada acreditación con su cobro por el
ID externo, asentando la comisión y su IVA. Para el MVP alcanza con documentar la conciliación manual
en el manual.

### 3.41 Nave Point con *Código QR* en la terminal (2026-10-08)

Cobro real de $150 con *Nave Point* en Odoo, eligiendo *Código QR* en la terminal y pagando con la
app de Galicia (MODO). Evidencia en `docs/homologacion/evidencias/C2_qr_terminal/`.

| Paso | Resultado |
|---|---|
| Envío | ✅ *"Enviando el cobro a la terminal 5d0ab925…"* a las 20:42:58 UTC. Odoo, *"Esperando la tarjeta"* |
| Pago | ✅ La terminal mostró su QR con el monto. Nave aprobó a las 20:45:49, el webhook respondió 200 sin reintentos y el POS lo registró en esa misma consulta: *Pago exitoso* |
| Cupón de la terminal | ✅ *"Código QR - Dinero en cuenta"*, código de operación `ONQ625134352`. Sin la mezcla de crédito y débito de los cupones con tarjeta |
| Ticket del POS | ✅ *"Billetera: banco galicia - modo"*, cupón `ONQ625134352` y autorización (`7_ticket_pos.png`) |

**Lo que informa Nave del pago:** `payment_input: wallet`, `payment_method.type: transfer_payment`
y `wallet.name: "banco galicia - modo"`, con `wallet.coelsa_id: "88"` y el CUIT de la entidad. Para
este pago, el nombre ya es el de la billetera que usó el cliente; con Belo había llegado el del
procesador. El `coelsa_id` es un candidato a clave para el diccionario de
`name-the-wallet-the-customer-used`. Nave también manda el CBU de la cuenta del cliente: no se
registra en el repo.

**Una sola caja, dos medios:** para el cajero no cambia nada. Elige *Nave Point* y el cliente decide
en la terminal si paga con tarjeta o con QR. El texto *"Esperando la tarjeta"* no sirve para el QR de
la terminal, pero Odoo no sabe qué va a elegir el cliente. Queda como está.

**Nave acredita el neto:** Galicia avisó *"Cobraste $148,55 con Nave"* por los $150, es decir $1,45
de comisión. Es la misma proporción que en el QR fijo (§3.40). Va al bloque F.

### 3.40 Nave QR fijo: cobro real con billetera (2026-10-08)

`pos_nave 18.0.1.11.1`, método *Nave QR* con el `pos_id` del *QR 1* del local. Evidencia en
`docs/homologacion/evidencias/H/`.

| Prueba | Resultado |
|---|---|
| **H6** — dejar vencer el cobro | ✅ `EXPIRED` a los 5 min justos (19:07:00 → 19:12:03 UTC). *"Cobro expirado"*, la línea queda para reintentar y no hay loop |
| **Pagos sin cobro activo** | Dos pagos de $147 con Belo, uno al *QR 1* y otro al *QR 2*. La billetera **pidió el monto**: no había un cobro de Odoo en ese QR, porque en el *QR 1* se escaneó antes de que existiera y el *QR 2* no lo usa Odoo. Quedaron como transferencias sueltas al comercio y Nave **no avisó nada**. Odoo no se enteró, como corresponde |
| **H2 a H5** — cobro real, $147, POS 1/0014 | ✅ Con *"Esperando"* en Odoo, Belo leyó el *QR 1* y mostró los **$147 ya cargados**. Nave aprobó a las 19:36:44, el webhook respondió 200 sin reintentos, y el POS lo registró en la consulta de ese mismo segundo. Factura `FA-C 00001-00000017`, *"Pagado usando Nave QR"* |

**Lo que quedó registrado en la línea de pago:** modo `wallet`, billetera *"bind pago"* (el
procesador que usa Belo, no el nombre de la app), cupón `SMI542294163` y autorización. Sin marca ni
últimos cuatro, como era de esperar en un pago con billetera.

**El ticket del POS** imprime *"Billetera: bind pago"*, el cupón y la autorización
(`7_ticket_pos.png`). El cliente pagó con Belo y lee *"bind pago"*: el nombre que manda Nave es el
del procesador, no el de la app. Es lo que informa Nave, así que no se corrige en Odoo; se puede
consultar en la reunión si hay un campo con el nombre de la billetera que vio el cliente.

**Reintentos:** cada *Volver a intentar* consultó primero la intención anterior, la encontró vencida y
recién después creó la nueva. Las tres intenciones llevaron la misma referencia de la línea, y Nave
las aceptó.

**Hallazgos:**

- **El cajero tiene que esperar a ver el cobro en Odoo antes de que el cliente escanee.** Si escanea
  antes, la billetera pide el monto y el pago queda fuera del cobro, sin aviso. Conviene decirlo en
  la pantalla y en el manual. El texto *"Esperando la tarjeta"*, que es del core, confunde con un QR;
  el usuario propone *"Esperando el escaneo del QR"*.
- **Nave acredita el neto.** Galicia avisó *"Cobraste $145,57 con Nave"* por los $147: $1,43 de
  comisión. Odoo registra $147 en el diario Banco. Va al bloque F (F4, total contra monto cobrado).
- **Tokens pedidos de más.** Entre 19:10 y 19:12, cada consulta pidió un token nuevo (~25 en un
  minuto y medio). Hipótesis: con menos de 5 minutos de vida, Nave devuelve el mismo token con lo que
  le queda, y el margen de 5 minutos de `_nave_get_access_token` lo sigue dando por vencido.
- **El log del QR dice *"Enviando solicitud Smart POS a la terminal"*.**
- **Los dos pagos sueltos** ($294) quedaron en la cuenta del comercio. Si hay que devolverlos, es
  desde el panel de Nave.

**Corregido en `fix-loose-ends-from-qr-tests`** (`payment_nave 18.0.1.12.3`, `pos_nave 18.0.1.11.2`,
verificado en producción el 2026-10-08):

- con *Nave QR* la línea en espera dice *"Esperando el escaneo del QR"*, y con *Nave Point* sigue
  diciendo *"Esperando la tarjeta"* (`8_espera_qr_texto_nuevo.png`, `9_espera_terminal_sin_cambios.png`);
- el log del envío dice *"Enviando el cobro al QR …"* o *"… a la terminal …"*;
- el token se reusa hasta 30 s antes de vencer: Nave devuelve el mismo token mientras no vence,
  comprobado en producción con 84.249 s restantes (`expires_in: 84250`, mismo token);
- el JSON roto del webhook (D2c) queda como advertencia;
- el comentario de `close()` ya no dice que el core lo llama.

Las dos cancelaciones de la prueba, QR y terminal, las aceptó Nave sin error.

### 3.39 El webhook acusa los avisos que no son del sitio (2026-10-08)

Corrección en `acknowledge-webhooks-that-are-not-ours`, `payment_nave 18.0.1.12.2`. Verificado en
producción, contra la URL registrada en Nave. Evidencia en `docs/homologacion/evidencias/D4c/`.

| Prueba | Resultado |
|---|---|
| **D4c** — `curl` con una referencia inventada | ✅ 200. El log anota *"Aviso de Nave que no corresponde a ninguna transacción del sitio… se acusa sin aplicar"*, sin error |
| **D2c** — JSON roto | ✅ 400 |
| **D3c** — sin `payment_id` | ✅ 400, con advertencia |
| **Cobro presencial real**, $150, orden 114 | ✅ Nave avisó una sola vez (18:34:43 UTC) y Odoo respondió 200. En los 10 minutos siguientes no hubo reintentos, cuando antes llegaban a los ~1 y ~7 minutos. El POS registró el pago por su consulta un segundo después |

**Lo que cambió:**

- Un aviso que no corresponde a ninguna transacción del sitio se acusa con 200, como hace el core
  con Stripe. Nave manda a la misma URL los pagos de todo el comercio, también los de la terminal.
- Si la consulta del pago a Nave falla, la transacción online queda como estaba y el webhook responde
  500 para que Nave reintente. Antes quedaba en **error** con un 200: nadie la volvía a revisar.
- El procesamiento corre dentro de un savepoint, así que un 500 no deja el aviso aplicado a medias.

**Pendiente menor:** el JSON roto (D2c) se registraba como error. Corregido en §3.40.

**Para la reunión (consulta 6):** que un 200 corta los reintentos de Nave queda confirmado en la
práctica. Sigue abierta la pregunta de si se puede tener una URL de notificación por medio de cobro.

### 3.38 C7: salir de la pantalla de pago no pierde el cobro (2026-10-08)

`pos_nave 18.0.1.11.1`, POS 1, *Validar automáticamente* apagado. Evidencia en
`docs/homologacion/evidencias/C7/`.

**Lo que hace Odoo 18 al tocar *Regresar*:** nada con la terminal. El core nunca llama a `close()`
de la interfaz de pago (no hay ningún llamador en `point_of_sale` ni en enterprise), así que el
seguimiento del cobro sigue y la línea sigue esperando. Mientras ese cobro esté pendiente, el core
no deja lanzar otro cobro con terminal **en esa pestaña**, ni siquiera en otra orden ni con Nave QR
(`paymentTerminalInProgress`, `payment_screen.js:126`).

| Prueba | Resultado |
|---|---|
| **C7a** — cobro sin pagar, *Regresar*, volver a *Pago* y cancelar | ✅ La terminal siguió pidiendo la tarjeta. Odoo consultó a Nave 20 veces en 66 s, también desde productos (04:07:56 a 04:09:03 UTC). La línea seguía esperando con *Cancelar*. Nave aceptó la baja y la terminal volvió a reposo |
| **C7b** — con un cobro pendiente, orden nueva y Nave Point | ✅ *"Ya hay un pago electrónico en progreso"*: el core no crea un segundo cobro |
| **C7c** — cobro, *Regresar* y pago real de $800 en la terminal | ✅ Nave aprobó a las 04:14:54 y Odoo lo registró en la consulta siguiente (04:14:55), con el cajero en productos. Al volver a *Pago*, la línea estaba en *Pago exitoso*, sin saldo, y quedaba *Validar*. Mastercard crédito terminada en 9537, 1 cuota |

**Lo que eso deja:**

- **Una sola caja no puede chocar dos cobros en la terminal.** El bloqueo es por pestaña: con varias
  cajas sobre la misma terminal, cada una tiene el suyo y no ve los cobros de la otra. Es C10.
- **El comentario de `close()` en `payment_nave.js` es falso**: dice que se llama al salir de la
  pantalla de pago. Hoy no hace daño, y conviene que siga sin llamarse: si el seguimiento se cortara
  al salir, un pago como el de C7c no se registraría. Corregir el comentario en el próximo cambio
  de `pos_nave`.
- **El webhook del pago volvió a responder 500** (04:14:54 y 04:16:03), igual que en los demás cobros
  presenciales: consulta 6 de `tasks/reunion_tecnica_nave.md`.
- **El cupón vuelve a mezclar crédito y débito:** *"MASTERCARD CREDIT 9537"* en el detalle y
  *"Debit Mastercard"* al pie, con la terminal mostrando *"MASTERCARD Crédito"*. Es la misma
  inconsistencia del cupón de C3, ahora en un pago aprobado.

**Bajas que no se explicaron:** entre las 04:04 y las 04:07, tres cobros a la terminal quedaron dados
de baja a los 11, 4 y 4 s de crearse, sin motivo en la respuesta de Nave. Antes, a las 03:56, hubo
un cobro a Nave QR cancelado desde Odoo; Nave aceptó la baja, pero fue una exploración y no una
prueba de H7.

### 3.37 Reprueba de C4: cancelar desde Odoo da de baja el cobro en la terminal (2026-10-08)

Corrección en `send-the-reason-nave-accepts-when-cancelling`, `pos_nave 18.0.1.11.1`. La baja manda
el par que Nave acepta (`disabled_from_saas` / `disabled from SAAS`) y, si igual la rechaza por el
motivo, la repite sin cuerpo. Cuando falla, el log registra el código HTTP y la respuesta de Nave.
Sin dinero. Evidencia en `docs/homologacion/evidencias/C4/reprueba_18.0.1.11.1/`.

| Prueba | Resultado |
|---|---|
| **A** — *Cancelar* en Odoo con la terminal pidiendo la tarjeta | ✅ Nave aceptó la baja al primer intento (23:06:26). La terminal volvió a reposo y el POS no mostró aviso |
| **B** — *Cancelar* en Odoo con el cliente en *"Elegí la cantidad de cuotas"* | ✅ Nave aceptó la baja (23:13:11) aunque el cliente estaba operando la terminal. La terminal volvió a reposo, sin aviso. Antes, *Volver a intentar* consultó la intención anterior (`DISABLED`) y recién después creó la nueva |
| **C** — tocar *volver* en la terminal y después *Cancelar* en Odoo | ✅ No llegó a cancelarse: *volver* en la pantalla *"Elegí cómo querés cobrar"* dio de baja la intención en Nave. El POS lo detectó en la consulta siguiente y mostró *"Cobro dado de baja"*, con *Volver a intentar* en lugar de *Cancelar*. La intención `d0081b39…` se creó a las 03:48:50 UTC y quedó `DISABLED` a las 03:49:22. Odoo no mandó ninguna baja |

**El caso C no llega a la cancelación:** si el cliente sale del cobro en la terminal, Nave da de
baja la intención y el POS lo informa solo. El cajero ya no tiene *Cancelar*, sólo *Volver a
intentar*, y eso pasa por la consulta de la intención anterior (§3.35).

**Distinto de la corrida 2 de §3.35:** allí *volver* no dio de baja la intención; aquella vez la
terminal acababa de recibir el cobro y la pantalla en la que se tocó no consta. La de hoy es la
primera, la de elegir el medio de cobro. Si vuelve a aparecer una intención que sigue viva después
de *volver*, *Cancelar* en Odoo ahora sí la da de baja (pruebas A y B).

**El motivo de la baja sigue sin llegar:** sabemos que la causa fue *volver* en la terminal (el
motivo publicado sería `manual_disabled_by_user`), y Nave igual respondió sólo
`payment_request_is_disabled`. El cajero vio *"El cobro ya no está disponible"*. Es la consulta 3 de
`tasks/reunion_tecnica_nave.md`.

**Para el bloque H:** la terminal siempre ofrece *Tarjetas* o *Código QR* al recibir el cobro. Estas
pruebas usaron *Tarjetas*; el QR de la terminal queda por probar junto con Nave QR.

### 3.36 🔴 C4: cancelar desde Odoo nunca funcionó (2026-10-07)

Prueba A: cobro de $246,90 a la terminal y, sin tocar el equipo, *Cancelar* en Odoo. Evidencia en
`docs/homologacion/evidencias/C4/`.

- Odoo mostró *"La terminal puede seguir cobrando"* con el mensaje de Nave: **`['Invalid input
  reason'] (HTTP 400)`**.
- La terminal siguió pidiendo la tarjeta: el cobro quedó vivo, y el cliente todavía podía pagarlo.

**Causa: Nave valida el par código + descripción del motivo de baja, y la descripción tiene que
ser un texto fijo.** Sondeado en sandbox con una intención inexistente: Nave valida el motivo antes
de buscar la intención, así que un motivo aceptado devuelve 404 y uno rechazado, 400.

| Código | Descripción aceptada | Rechazadas |
|---|---|---|
| `disabled_from_saas` | `disabled from SAAS` | `disabled from saas`, `Disabled from SAAS`, `disabled_from_saas`, el texto en castellano de la doc, `Cancelado desde Odoo POS` (la de Odoo) |
| `manual_disabled_by_user` | `manual disabled by user` | `manual` |
| `low_battery` | `low battery` | `Low battery`, `low_battery`, `x` |
| `device_already_on_payment_flow` | `device already on payment flow` | |
| `disabled_by_user_timeout` | `disabled by user timeout` | |
| `not_specified` | — (rechazó `not specified`) | |

Un cuerpo vacío (`{}`) o ausente también pasa la validación. Sólo `code`, sólo `description` o
`reason` vacío se rechazan.

**La documentación no lo dice:** describe `reason.description` como un texto que *"brinda
información sobre el código de baja"*, y lista `disabled_from_saas` como código válido sin aclarar
que su descripción es fija. El módulo manda el código correcto con una descripción libre, así que
**todas** las cancelaciones desde Odoo fueron rechazadas desde siempre. En sandbox la baja sí había
respondido 200 alguna vez; no consta con qué cuerpo.

**Además:** la cancelación registra en el log sólo el código HTTP, no el cuerpo de la respuesta. Lo
que se supo, se supo porque el aviso al cajero sí muestra el mensaje de Nave.

Las pruebas B y C (cancelar con el cliente operando en la terminal, y después de *volver* en el
equipo) se postergan hasta corregir el cuerpo: hoy fallarían igual, por el mismo motivo.

### 3.35 Reprueba de C8: un corte ya no lleva a cobrar dos veces (2026-10-07)

Corrección en `survive-network-cuts-without-charging-twice`, `pos_nave 18.0.1.11.0`. Un corte de red
ya no termina el cobro: sólo lo terminan Nave, el plazo o el cajero. Cada llamada del navegador
tiene un tope de tiempo, y *Volver a intentar* pregunta primero por la intención anterior. Evidencia
en `docs/homologacion/evidencias/C8/reprueba_18.0.1.11.0/`.

| Prueba | Resultado |
|---|---|
| **Pedido 104** (abierto desde §3.34, $150 aprobados durante el corte) | ✅ La línea conservó el identificador de la intención tras recargar el POS. *Volver a intentar* hizo una sola consulta, Nave informó la intención aprobada con el pago del webhook, y la línea quedó cobrada con la notificación *"Cobro confirmado"*. No se creó ninguna intención nueva |
| **Corrida 3** — navegador sin conexión, pago real de $199,99 | ✅ Notificación *"Sin conexión con Nave"*, sin *"Desconexión"*; la línea siguió esperando. Nave aprobó con el POS desconectado (21:46:38 UTC) y, al volver la conexión (21:47:51), el POS registró el pago con los datos de la tarjeta. Un solo desenlace en el log |
| **Corrida 2** — cable desenchufado, sin pagar ($800) | ✅ A los ~40 s, *"Sin conexión con Nave"*: el POS ya no queda colgado sin avisar. La terminal se rindió a los ~3 min y, al reconectar, *"Cobro dado de baja"*. *Volver a intentar* consultó la intención dada de baja y recién después creó la nueva |

**El aviso tarda ~40 s, no ~30:** hacen falta tres consultas sin respuesta, cada una con su tope de
10 s más el intervalo de 3 s.

**Para C4:** al final de la corrida 2 se cancelaron desde Odoo el cobro nuevo y la terminal respondió
a *volver* sin dar de baja la intención (las consultas siguieron viéndola en espera). El `DELETE` de
Odoo recibió **400**, cuando en sandbox respondía 200 sobre intenciones de terminal. La cancelación
registra sólo el código HTTP y no el cuerpo, así que no se sabe qué dijo Nave: conviene registrarlo
antes de probar C4.

### 3.34 🔴 C8: un corte de red puede hacer que el cliente pague dos veces (2026-10-07)

Tres corridas con la terminal y `pos_nave 18.0.1.10.2`, dos de ellas con pago real. Evidencia en
`docs/homologacion/evidencias/C8/`, una carpeta por corrida.

| Corrida | Cómo se cortó la red | Qué hizo el POS | Desenlace |
|---|---|---|---|
| 1 — $123,45 | Corte de unos 2 min mientras el cliente pagaba | Siguió en *"Esperando la tarjeta"*, sin aviso | Al volver la red, la consulta trajo la aprobación: *"Pago exitoso"* ✅ |
| 2 — $150 | Cable de red desenchufado unos 3 min, sin pagar | Siguió en *"Esperando la tarjeta"*, sin aviso, pasado el plazo | La terminal se rindió (*"Se cumplió el tiempo para pagar"*); al reconectar, *"Cobro dado de baja"* |
| 3 — $150 | Navegador sin conexión (*Archivo › Trabajar sin conexión*) | A los ~9 s, *"Desconexión"* y línea en *"Volver a intentar"* | **Nave aprobó el pago 28 s después** (webhook de las 19:16:45 UTC). Odoo nunca se enteró: la línea sigue para reintentar 🔴 |

**Dos defectos, según cómo falle la red:**

1. **Si la consulta falla al instante (corrida 3), el POS da el cobro por fallido mientras la
   terminal sigue cobrando.** El aviso dice *"Verificá el estado en la terminal antes de
   reintentar"*, pero si el cajero ve la aprobación no tiene cómo registrarla: una línea en
   *"Volver a intentar"* no muestra *Forzar terminación*. *Volver a intentar* crea un cobro nuevo y
   el cliente paga dos veces; cobrar en efectivo tiene el mismo resultado. El pago aprobado no deja
   rastro en Odoo: sólo el webhook, que `payment_nave` responde con 500 porque no lo reconoce (§3.31).
2. **Si la consulta queda colgada (corridas 1 y 2), el POS espera sin límite y sin aviso,** aun
   pasado el plazo de la intención: el tope sólo se revisa entre consultas, y una consulta colgada
   no termina. Si la red vuelve, se entera del desenlace real, como en la corrida 1. Si no vuelve,
   queda trabado, y *Forzar terminación* tampoco responde: su consulta a Nave se cuelga igual y la
   pregunta al cajero nunca aparece.

**Lo que esto confirma de la terminal:** el tope propio de unos 3 minutos (corrida 2, como en C9).

**El pedido de la corrida 3 quedó abierto en el POS a propósito**, con la línea en *"Volver a
intentar"* y el pago aprobado en Nave. Sirve para probar la corrección: reintentar tiene que
encontrar el pago aprobado en lugar de crear otro cobro.

### 3.33 Reprueba de C9: "Forzar terminación" consulta a Nave (2026-10-07)

Corrección en `confirm-force-done-with-nave`. En una línea de Nave, *Forzar terminación* consulta a
Nave y resuelve el cobro en curso con lo que responda; sólo si Nave no responde le pregunta al
cajero si vio la aprobación. Evidencia en `docs/homologacion/evidencias/C9/reprueba_18.0.1.10.0/` y
`reprueba_18.0.1.10.1/`.

| Prueba | Versión | Resultado |
|---|---|---|
| A — forzar mientras la terminal espera la tarjeta | 18.0.1.10.0 | ✅ *"El cobro sigue en curso"*; la línea sigue esperando y *Validar* no se habilita |
| B — rechazo por fondos sobre la misma intención | 18.0.1.10.0 | ✅ Un solo aviso *"Pago rechazado"*, línea reintentable, un solo desenlace en el log |
| C — forzar con la PC sin conexión | 18.0.1.10.0 | 🔴 La pregunta *"No se pudo consultar a Nave"* aparecía, pero el polling cortaba por desconexión mientras el cajero la leía y la dejaba huérfana detrás: confirmar ya no tenía efecto |
| C — repetida | 18.0.1.10.1 | ✅ La pregunta queda sola en pantalla mientras el cajero decide. *Volver* deja la línea esperando, el polling se reanuda y corta por desconexión como siempre, y no se cobra nada |
| D — forzar sobre un cobro que Nave aprobó | — | ⏸️ Pendiente. Exige un cobro real que hoy no se puede devolver (reembolsos bloqueados por N12) y una ventana de 3 s antes de que el polling se entere solo. El camino es el mismo que el de un cobro aprobado normal (C0) |

**Por qué falló C en la primera versión:** la pregunta al cajero y el polling competían por el
mismo cobro. La corrección pausa el polling mientras la pregunta está abierta: el cobro queda en
manos del cajero hasta que responde.

**Durante el despliegue se encontró un token personal de GitHub en texto plano** en el remote del
repo `nave` de `~/do-onlyone/odoo/custom/src/repos.yaml`, en el servidor. Se avisó para revocarlo y
reemplazarlo por una credencial de sólo lectura fuera del archivo.

### 3.32 🔴 C9: "Forzar terminación" da por cobrada una venta que nadie pagó (2026-10-07)

Cobro de $123,45 a la terminal con `pos_nave 18.0.1.9.0`. Mientras la línea decía *"Esperando la
tarjeta"*, se tocó **Forzar terminación** (*Force done*) sin acercar ninguna tarjeta. Evidencia en
`docs/homologacion/evidencias/C9/`, numerada en orden.

**Qué pasó:**

| Momento | POS | Terminal / Nave |
|---|---|---|
| 11:40:48 | Se envía el cobro: *"Esperando la tarjeta"* | Pide la tarjeta |
| Forzar terminación | **"Pago exitoso", restante $0,00, *Validar* habilitado** | Sigue esperando la tarjeta: el cobro sigue vivo |
| Mientras tanto | El POS sigue consultando a Nave cada 3 s | — |
| 11:43:57 (189 s) | Aviso *"Cobro dado de baja"*; la línea vuelve a *"Volver a intentar"* | *"Se cumplió el tiempo de espera para pagar"* |

**El hallazgo:** durante unos tres minutos, el POS muestra como cobrada una venta sin cobro, y el
cajero puede validarla. Si la valida, la venta se cierra y se imprime el ticket como pagada con Nave,
sin que Nave haya cobrado nada. La intención además sigue viva en la terminal, así que el cliente
todavía podría pagar. La validación automática está desactivada en `POS 1`: con ella activa, la
venta se cerraría en el acto, sin que el cajero llegue a tocar *Validar*.

**Por qué:** *Forzar terminación* es del core de Odoo (`payment_screen.js:606`). Marca la línea
como cobrada sin consultar al proveedor, sin detener el polling y sin dar de baja la intención. Está
pensado para terminales locales que pierden la conexión: el cajero vio la aprobación en el equipo y
Odoo no se enteró. Con Nave ese caso no hace falta adivinarlo, porque el estado siempre se puede
consultar a la API.

**Lo que salva parcialmente la situación** es que el polling no se detiene: si el cajero no validó
antes de que Nave informe el desenlace, la línea vuelve a *"Volver a intentar"*. No se probó qué
pasa si el desenlace llega después de validar, porque eso dejaría una venta falsa en producción.

**El escenario de la matriz no puede ocurrir.** La matriz decía *"rechazar en la terminal y
presionar Force done"*. Después de un rechazo, el módulo deja la línea en `retry` y Odoo no muestra
el botón. El riesgo está **antes** del desenlace, mientras se espera la tarjeta.

**Dato al margen: la terminal tiene su propio tope de unos 3 minutos.** Dio de baja la intención a
los 189 s (*"Se cumplió el tiempo de espera para pagar"*), antes de los 300 s que se le piden a
Nave. Eso explica la primera corrida de C6 (§3.28), que terminó en baja. En la reprueba (§3.31)
llegó `EXPIRED` a los 303 s, así que el tope de la terminal no siempre actúa; falta entender cuándo.

### 3.31 Reprueba de C3: el motivo se leía del objeto equivocado (2026-10-07)

Reprueba de C3 con `pos_nave 18.0.1.8.0` desplegado: cobro de $123,45 a la terminal con una tarjeta
sin fondos. Evidencia en `docs/homologacion/evidencias/C3/reprueba_18.0.1.8.0/`.

**Lo que se corrigió se ve:** el título es *"Pago rechazado"*, el aviso indica reintentar y la línea
queda con *"Volver a intentar"*. Ya no hay alarma de seguridad ni instrucción de llamar a Nave. Esta
vez la terminal sí imprimió el cupón *RECHAZADO* (código de operación `RGR230718234`), cosa que en
§3.30 no había hecho: la impresión es opcional en la terminal.

**Lo que salió mal:** el aviso decía *"El pago fue rechazado: payment retries limit reached. Probá
con otra tarjeta."*. La terminal, en el mismo momento, decía que la tarjeta no tenía fondos.

**Por qué:** Nave informa dos motivos y el módulo leía el que no correspondía. Según la
documentación para desarrolladores (transcripta en `docs/nave_codigos_referencia.md`):

- La **intención** quedó en `BLOCKED`, que Nave define como *"bloqueada por fraude o intentos
  excedidos"*, con *"payment retries limit reached"*: los intentos excedidos. Describe a la
  intención.
- El **pago** informa por qué se rechazó la tarjeta en `status.reason_code`. Nave publica el
  catálogo de esos códigos, con un mensaje en castellano para cada uno.

El backend ya traía el pago en cada consulta, para imprimir los datos de la tarjeta, así que el
motivo correcto llegaba al navegador; el JS leía el otro. La heurística de mostrar el motivo "si
parece una frase" partía de que Nave no publicaba su catálogo, y el supuesto era falso.

**Corrección** (`speak-to-the-cashier-not-the-api`, `payment_nave 18.0.1.12.0` y
`pos_nave 18.0.1.9.0`):

- El catálogo de Nave queda en `payment_nave/models/nave_reasons.py`.
- El motivo se toma del pago, y la explicación sale siempre del catálogo.
- Debajo del aviso aparece un bloque *"Para soporte"* con el código y los identificadores.
- El servidor registra el desenlace de cada cobro.

**Reprueba con `pos_nave 18.0.1.9.0` (2026-10-07):** los tres casos pasan. Evidencia en
`docs/homologacion/evidencias/{C3,C5,C6}/reprueba_18.0.1.9.0/`.

| Caso | Lo que informó Nave | Aviso al cajero | Registro en el servidor |
|---|---|---|---|
| C3 | Intención `BLOCKED`; pago `no_amount_available` | *"La tarjeta no tiene fondos suficientes. Podés reintentar o cobrar con otro medio."* + código, pago e intención para soporte | `terminado en BLOCKED … Motivo: no_amount_available (La tarjeta no tiene fondos suficientes.)` |
| C5 | `400 payment_request_is_disabled`, a los 8 s | *"El cobro ya no está disponible. Generá un cobro nuevo."* + intención para soporte | `terminado en DISABLED … Motivo: -` |
| C6 | `EXPIRED`, a los 303 s | *"La intención de cobro expiró sin recibir el pago. Generá un cobro nuevo."* + intención para soporte | `terminado en EXPIRED … Motivo: -` |

En los tres casos la línea queda con *"Volver a intentar"* y no se contabiliza nada.

**Nave no informa el motivo de una baja al consultar la intención.** El cuerpo completo del 400 de
C5 fue `{"code":"payment_request_is_disabled","message":"Payment request is disabled"}`, sin
`reason`. Así que `manual_disabled_by_user`, que Nave documenta, no llega por esta vía, y el aviso
genérico es lo que corresponde. Queda una vía sin explorar: la notificación de intención, que según
la documentación trae `disabled_reason`. En los logs sólo aparecen notificaciones de pagos. Es una
pregunta para Nave.

**Un vencimiento no siempre llega igual.** En la primera corrida de C6 (§3.28), Nave dio de baja la
intención (`DISABLED`). En esta respondió `EXPIRED`, con la misma terminal y el mismo plazo. El
módulo da un aviso correcto en los dos casos, porque ninguno afirma una causa que Nave no informó.

**Detalle menor:** con una baja, la línea del log dice `Cobro -` porque Nave no devuelve la
intención y el backend no conoce la referencia del pedido. El identificador de la intención alcanza
para buscarla.

**De paso, en el log del servidor:** cada cobro del POS dispara un webhook de pago hacia
`/payment/nave/webhook`. `payment_nave` no lo encuentra entre sus `payment.transaction` y responde
500. Nave reintenta cinco veces en unas 7,8 h (10 s, 70 s, 490 s, 3340 s, 24010 s) y después lo
descarta. No afecta al cobro, pero deja errores en el log por cada venta con tarjeta. Es la variante
POS del caso D4c.

### 3.30 🔴 C3: un rechazo por fondos le dice al cajero que llame a Nave (2026-10-07)

Cobro de $123,45 a la terminal, pagado con una tarjeta sin fondos. Evidencia en
`docs/homologacion/evidencias/C3/`.

**Lo que hace bien:** la línea de pago queda reintentable, no se genera orden ni asiento, y la venta
sigue abierta para que el cajero pida otra tarjeta.

**Lo que está mal es lo que lee el cajero:**

> *"Nave bloqueó la operación por motivos de seguridad. **Contactá a Nave antes de reintentar.**"*

La tarjeta no tenía fondos. No hay nada que contactar: hay que pedir otra tarjeta. Ese mensaje manda
al cajero a llamar al proveedor en medio de una venta, con el cliente esperando, por un rechazo de
los más comunes que existen.

El diálogo *"Operación bloqueada"* sólo se muestra cuando el estado es literalmente `BLOCKED`
(`payment_nave.js:247`), así que es lo que Nave devolvió. La terminal, en cambio, mostró un mensaje
genérico: *"No se pudo realizar el pago. Hubo un problema al intentar procesarlo. Podés volver a
intentarlo."*

**Confirmado con una segunda tarjeta distinta.** Repetido el cobro con otra tarjeta sin fondos, el
resultado es idéntico: Nave devuelve `BLOCKED` y Odoo muestra el mismo aviso de seguridad. No fue una
particularidad de la primera tarjeta: **Nave usa `BLOCKED` para rechazos corrientes**, y nuestro
catálogo lo interpreta como fraude siguiendo lo que sugiere el nombre.

El contraste con lo que muestra la propia terminal es lo que mide el daño:

| | Mensaje |
|---|---|
| La terminal | *"La tarjeta con la que se intentó pagar no tiene el dinero necesario. Podés intentar pagar con otra."* |
| Nuestro módulo | *"Nave bloqueó la operación por motivos de seguridad. Contactá a Nave antes de reintentar."* |

Nave le dice al operador qué pasó y qué hacer. El módulo lo convierte en una alarma de fraude.

**El comprobante de un rechazo es opcional, pero existe.** La terminal ofrece "Compartir comprobante"
y puede imprimirlo: sale con `RECHAZADO`, la marca, los últimos cuatro, el importe y el código de
operación. Sirve como evidencia igual que el de un cobro aprobado.

#### Los tres mensajes que hay que corregir

Con C3, C5 y C6 ejecutados, el panorama de lo que lee el cajero queda completo:

| Situación | Lo que lee hoy | Problema |
|---|---|---|
| La intención venció (C6) | *"El cobro fue dado de baja: `payment_request_is_disabled`"* | un código que fabrica nuestro módulo |
| Cancelación en la terminal (C5) | el mismo mensaje | indistinguible del anterior |
| Tarjeta rechazada (C3) | *"Nave bloqueó la operación por motivos de seguridad. Contactá a Nave"* | manda a llamar al proveedor por un rechazo común, confirmado con dos tarjetas |

Los tres comparten la misma causa de fondo: el módulo le muestra al cajero el vocabulario de la API
en lugar de decirle qué pasó y qué puede hacer.

### 3.29 El código que lee el cajero lo fabrica nuestro propio módulo (2026-10-07)

C5 —cancelar desde la terminal— termina en el **mismo diálogo y el mismo motivo** que C6, el
vencimiento: *"El cobro fue dado de baja: `payment_request_is_disabled`"*. La terminal vuelve a
reposo y la línea queda reintentable, que es lo que ambos casos esperan, pero desde Odoo las dos
situaciones son indistinguibles.

Sondeando la API se ve por qué, y el código no viene de Nave como motivo:

```
intención viva          → GET …/payment_requests/{id} → 200 {"status": {"name": "PENDING"}}
intención dada de baja  → GET …/payment_requests/{id} → 400 {"code": "payment_request_is_disabled",
                                                              "message": "Payment request is disabled"}
```

O sea que una intención dada de baja **deja de poder consultarse**: no queda en estado `DISABLED`, y
`payment_request_is_disabled` es el código del **error HTTP**, no un motivo de negocio.

El backend traduce ese error a un estado sintético para que el POS cierre el cobro en vez de mostrar
una falla técnica, lo cual está bien, pero de paso copia el nombre del error en `reason_code`
(`pos_payment_method.py:223-228`). El JS lo imprime literal, y el cajero termina leyendo un código
que inventó nuestro propio módulo.

Lo irónico es que el JS ya tiene un mensaje legible para cuando **no** hay motivo —*"El cobro fue dado
de baja en la terminal."*— que nunca se usa, porque el backend siempre inyecta el código
(`payment_nave.js:237-240`).

Ese mensaje tampoco sería del todo exacto: la baja puede venir de una cancelación en la terminal, de
un vencimiento, o de que Nave no pudiera notificar al equipo. El mensaje correcto no debería afirmar
cuál de las tres fue.

#### 🟢 C4 queda destrabado

El comentario del código sostiene que *"Nave responde 400 al intentar dar de baja una intención de
terminal: su catálogo de errores sólo admite baja para `payment_link`, `dynamic_qr` y `static_qr`"*
(`pos_payment_method.py:405-407`). **Ya no es cierto:**

```
DELETE /api/payment_requests/{id}  →  200 {"message": "Payment request deleted"}
```

Probado contra producción con una intención de Nave Point. La cancelación desde Odoo es posible, así
que C4 deja de estar bloqueado por la API.

### 3.28 C6: el cobro vencido no cuelga el POS, pero el cajero lee un código (2026-10-07)

Se lanzó un cobro de $123,45 a la terminal y no se tocó nada. Evidencia en
`docs/homologacion/evidencias/C6/`.

**El pronóstico del plan ya no aplica.** Decía *"se espera loop infinito"*; el bucle corta, la línea
de pago queda reintentable con su botón "Volver a intentar", y no se contabiliza nada: el POS siguió
con la venta abierta y sin orden generada.

**El vencimiento no llega como `EXPIRED`.** La terminal muestra *"Se cumplió el tiempo para pagar"* y
**da de baja** la intención, así que Nave informa `DISABLED` con motivo `payment_request_is_disabled`.
El módulo tiene las dos ramas y la que ocurre en el presencial es la de baja, no la de expiración.

**El arreglo de `align-pos-wait-with-intent-deadline` hizo su trabajo igual.** El tope local pasó de
300 a 330 segundos, de modo que el aviso de Nave llegó antes de que el POS cortara por su cuenta. Con
los 300 exactos de antes habría ganado el tope local y el cajero habría leído *"verificá el estado en
la terminal"*, que es el aviso de "no sé qué pasó".

#### Lo que queda mal: el cajero lee `payment_request_is_disabled`

El diálogo dice textualmente *"El cobro fue dado de baja: payment_request_is_disabled"*. El motivo se
toma de `status.reason_name || status.reason_code` y se muestra tal cual
(`payment_nave.js:215,237`). Cuando Nave manda un código técnico, el cajero recibe un código técnico.

La propia terminal, en la misma situación, le dice al operador *"Pasaron varios minutos desde que
iniciaste este cobro. Podés crear uno nuevo"*. Esa es la forma de decirlo.

### 3.27 El cobro presencial funciona de punta a punta (2026-10-06)

Primer cobro con la terminal física, ya en producción. Orden `POS 1/0001` por $50,00: el monto salió
del Punto de Venta de Odoo, apareció en la terminal, se pagó con tarjeta y volvió. Evidencia en
`docs/homologacion/evidencias/C0/`.

**C0 — el cobro llega a la terminal correcta.** El cupón impreso dice `Terminal Nº: L40037644`, que
es el dispositivo del `pos_id` configurado. Queda descartada la duda de §3.5 sobre el `pos_id`
duplicado: ahora cada medio tiene el suyo.

**C2 — la orden se cierra sola.** Quedó facturada (`FA-C 00001-00000004`) con los $50 cobrados y el
`transaction_id` guardado. Se pagó por **NFC**, no insertando el chip como decía el caso.

**C12 — el ticket sí lleva los datos.** La matriz anticipaba que `set_receipt_info()` no se llamaba y
el ticket salía vacío. No es así:

```
Tarjeta: AMERICAN EXPRESS ****2385
Tipo: CREDIT
Cupón: FYK207529681
Autorización: 909827
Lote: 1
Emisor: BANCO MARIVA S.A.
```

#### Odoo guarda más de lo que la terminal imprime

| Cupón de la terminal | Línea de pago en Odoo |
|---|---|
| AMERICAN EXPRESS CREDIT 2385 | `card_brand`, `card_no`, `card_type` |
| Código de operación FYK207529681 | en el ticket |
| TRC 909827 | `payment_method_authcode` |
| — | `payment_method_issuer_bank` = BANCO MARIVA S.A. |
| — | `payment_method_payment_mode` = `nfc` |

El emisor y el modo de lectura no figuran en el papel y sí quedan en el sistema, que es justamente lo
que sirve para atender un reclamo.

### 3.26 El bloque A queda cerrado, salvo las devoluciones (2026-10-06)

Cuatro cobros más contra sandbox cierran el bloque de cobros online. Comprobantes de Nave en
`docs/homologacion/evidencias/<caso>/`.

| Caso | Resultado |
|---|---|
| A3 | VISA CREDIT ****0139, 1 cuota, cupón `GDP476968633` → `done` |
| A4 | VISA CREDIT ****0231, **6 cuotas**, cupón `NPA855612747` → `done` |
| A5 | Rechazo `no_amount_available` → `cancel`, sin asientos |
| A16 | Rechazo y luego aprobación sobre la misma intención → `done` |

**A4 muestra para qué sirvió registrar la financiación.** La venta es de $1.150 y el cliente pagó
**$1.364,66** en 6 cuotas de $227,44, con tasa 13%, TNA 63% y CFT 18,67%. Antes del cambio de §3.18
nada de eso quedaba en Odoo.

#### El comprobante de Nave concilia con lo registrado

El cliente descarga un comprobante al terminar de pagar. El de A4 coincide campo por campo con lo que
guardó la transacción:

| Comprobante de Nave | Odoo |
|---|---|
| Total $1.364,66 | `nave_customer_total` = 1364.66 |
| `**** 0231` Visa | VISA CREDIT ****0231 |
| Cuotas: 06 de 227.44 | 6 cuotas |
| Referencia: A4-S00040 | misma referencia |
| Código de operación: NPA855612747 | `nave_payment_code` |
| Medio de cobro: E-Commerce | intención de tipo `ecommerce` |

Es la prueba de conciliación que conviene mostrar: lo que el cliente tiene en la mano y lo que el
comercio tiene en el sistema dicen lo mismo.

#### A16 verifica contra la API el defecto más grave que apareció

Era el que motivó el cambio `recover-transaction-on-later-approval`. Pagando primero con la tarjeta
de rechazo y después, con **"Volver a intentar"**, con la aprobada, la intención terminó con dos
pagos —`REJECTED` y `APPROVED`— y la transacción quedó en `done` con el mensaje *"Tras un intento
rechazado previamente — Pago aprobado…"*. Antes del arreglo esa aprobación se descartaba y quedaba un
cobro real sin registrar.

#### A17: un rechazo que llega tarde no pisa la aprobación

Aprovechando que A16 dejó los dos pagos en la misma intención, se reenvió el webhook del **rechazado**
sobre la transacción ya aprobada. Siguió en `done`, con el pago aprobado registrado. Cumple el
requisito *un desenlace no se pisa con información más vieja*.

#### Lo que queda del bloque A

Sólo **A14 y A15**, las devoluciones, que siguen esperando que Nave habilite el permiso sobre
`DELETE /api/payments/{id}` (§3.21).

### 3.24 El link de pago está bloqueado en sandbox por el `pos_id` (2026-10-05)

Primer intento de generar un link de pago desde un pedido de venta del backend, con el wizard tal
como lo abre la vista. Nave lo rechaza:

```
POST /api/payment_request/payment_link  → 400 {"code": "invalid_pos",
                                               "message": "Given POS is for a different payment type"}
POST /api/payment_request/ecommerce     → 200 OK   (el mismo pos_id)
```

El proveedor de sandbox tiene un solo `pos_id`, el de tienda (`f71ba756-…`), y
`nave_payment_link_pos_id` está vacío, así que el wizard cae al de tienda —el comportamiento previsto
para no romper instalaciones viejas— y Nave lo rechaza porque asigna un identificador distinto a cada
medio de cobro.

**No es un defecto del módulo: falta el dato.** Es lo que se le pidió a Nave en N9 y sigue sin
llegar. El flujo de link de pago no se puede homologar en sandbox hasta tenerlo, y el bloque B de la
matriz queda detenido por eso, no por el código.

Lo que sí quedó verificado es el diagnóstico, con el error real y no con un mock:

```
[payment_nave] Nave rechazó la intención por identidad: medio 'payment_link',
pos_id 'f71ba756-…'. Ese pos_id pertenece a otro medio de cobro: revisá la
configuración del proveedor.
```

Eso cumple el requisito *Error de identidad diagnosticable* de `nave-payment-provider`: quien se
tope con esto sabe qué pasa sin tener que leer el código ni adivinar.

Nota al margen: el wizard devolvió primero un `HTTP 500 "Error getting api status by payment type
payment_link"`, y recién el POST directo mostró el `400 invalid_pos`. Nave contesta de dos formas
distintas para la misma causa, así que conviene no confiar sólo en el código de estado.

### 3.25 La cantidad fraccionaria ya se lee en el checkout (2026-10-05)

Verificado en la pantalla de Nave con `18.0.1.11.2` desplegado, pedido `S00032`:

```
Detalle de la compra
1× 0,15 kg [PRUEBA] ...     $120,00
Total                       $ 120,00
```

Antes decía `1x [PRUEBA] Granel por kilo`, sin rastro de los 0,15 kg. La cantidad se había puesto al
frente de la descripción dando por sentado que Nave la muestra; leyendo el DOM del checkout se vio
que **la descripción no se renderiza en ninguna de sus pantallas**. Pasó entonces al nombre, primero
para que sobreviva tanto al recorte de 100 caracteres como al truncado por CSS, como se ve arriba.

El `1×` lo antepone Nave y no se puede suprimir, así que el cliente lee `1× 0,15 kg`. Es redundante,
pero es preferible a que lea `1x` a secas y crea que compró una unidad.

### 3.23 A2: el circuito del e-commerce, de punta a punta (2026-10-05)

Primera vez que se recorre entero el camino del cliente —carrito, dirección, medio de pago, checkout
de Nave, pago con tarjeta, retorno— y llega hasta la contabilidad.

El retorno, que tampoco se había probado nunca, funciona en dos tiempos: `/payment/status` muestra
*"Espere… Aún no se ha procesado su pago"* con el importe y la referencia, y cuando entra el webhook
redirige sola a `/shop/confirmation` con *"Tu pago se procesó con éxito"*. El cliente no tiene que
hacer nada.

| | |
|---|---|
| Transacción | `S00030-2`, `done`, post-procesada |
| Pedido | `S00030`, confirmado |
| Asiento | `PBNK1/2026/00008` por $1.150,00 |
| Tarjeta | NARANJA CREDIT ****3355 — TARJETA NARANJA S.A. |
| Plan | 1 cuota, sin interés, total al cliente $1.150,00 |
| Comprobantes | cupón `TEE702191588`, autorización `002999`, lote `490` |

Mensaje de estado: *"Pago aprobado. Tarjeta: NARANJA CREDIT ****3355 · Cupón: TEE702191588"*.

Con esto quedan encadenados y verificados en un solo recorrido los tres arreglos del día: la
redirección que conserva la intención (§3.22), el detalle que cuadra con lo cobrado (§3.20) y el
registro del instrumento de pago (§3.18).

### 3.22 🔴 Nadie podía pagar desde la tienda (2026-10-05)

El recorrido que hace un cliente de verdad —entrar al sitio, armar el carrito, cargar la dirección,
elegir el medio de pago y apretar "Pagar ahora"— **se ejecutó por primera vez el 2026-10-05**, con el
navegador. Falló en el primer intento.

Odoo creó la intención y guardó bien su URL. El navegador llegó a otra:

```
nave_checkout_url guardado   → …/nave?payment_request_id=f9d279b1-a6d3-4135-bec6-a570035b9c51
location.href tras el submit → …/nave
```

Sin el identificador, Nave no sabe qué intención mostrar y deja una pantalla en blanco. El pedido
S00030 ($223,45) quedó esperando un pago que el cliente no tenía forma de completar.

**La causa.** La plantilla de redirección era `<form t-att-action="api_url" method="get">` sin
campos. Cuando un formulario con `method="get"` se envía, el algoritmo de submit del HTML **descarta
el query string de la acción** y lo reemplaza por la serialización de los campos. Sin campos, el
parámetro se perdía entre Odoo y Nave. Es comportamiento estándar, no un defecto del navegador.

**Por qué nadie lo vio.** Los 79 tests miran el payload que se le manda a Nave, y el defecto vive en
el salto del navegador. Y todas las pruebas de la matriz ejecutadas hasta ese día —A4, A6, A8, A9,
A13— se hicieron abriendo el `checkout_url` directamente, que es justamente el tramo que funcionaba.
Los dos casos que sí cubrían el recorrido, **A0 y A1, estaban sin ejecutar**.

Es la lección más cara del día: *un camino que no se recorre entero no está probado, por más verde
que esté la suite*.

**Corregido** en `18.0.1.11.1`: los parámetros viajan como campos ocultos, que es la parte que el
envío GET conserva, y se leen de la URL que Nave devuelve en vez de darse por sabidos.

**Verificado con el código desplegado**, rehaciendo el recorrido entero de la tienda. El navegador
llega a `…/nave?payment_request_id=c05e5845-82dd-4b2e-9d6e-acf0b5550fb8` y el checkout carga:

```
1x [PRUEBA] Precio ...      $123,45
2x [PRUEBA] Cobro  ...       $50,00
1x [PRUEBA] Cuotas ...    $1.150,00
1x Envío estándar             $0,00
Total                     $ 1.373,45
```

El primer intento de ese mismo recorrido devolvió `Read timed out` contra `api-sandbox.ranty.io`: el
sandbox corta de a ratos y el timeout de 15 s no siempre alcanza. Vale notar que el cliente **ve el
error** en un diálogo en lugar de quedarse esperando, y que al reintentar salió bien.

#### De paso, A0 y A1 quedan cerrados

El checkout del sitio lista **los dos medios**, "QR Interoperable Nave" y "Tarjeta", ambos con el
sello *"Asegurado por Nave"*. Eso **descarta B7**, que anticipaba que sólo aparecería QR.

El hosted checkout ofrece a su vez las dos formas: "Código QR" para billeteras y el formulario de
tarjeta, con nombre, documento y correo del comprador ya precargados desde el `buyer` que mandamos.
A2–A6 son ejecutables tal como están redactados.

El detalle que ve el cliente, con el pedido armado desde el carrito real:

```
1x [PRUEBA] Precio ...   $123,45
2x [PRUEBA] Cobro  ...    $50,00
1x Envío estándar          $0,00
Total                    $ 223,45
```

La línea de cantidad 2 se informa como `2x` a $50,00, el envío viaja como su propia línea, y la suma
coincide con el importe. El arreglo de §3.20 queda así confirmado también en el flujo real.

#### Lo que el carrito no deja hacer

El carrito web no admite cantidades fraccionarias: con `0,15` —y también con `0.15`— Odoo la
interpreta como cero y elimina la línea. O sea que **la venta a granel no es comprable desde la
tienda**. Es de `website_sale`, no de `payment_nave`, pero conviene tenerlo presente si el negocio
piensa vender por peso online.

### 3.21 A6 cerrado y el endpoint de devolución ubicado (2026-10-05)

**A6 con un importe que admite cuotas.** El primer intento de A6 se rechazó por
`invalid_installment_plan` con $10: no hay plan de cuotas posible para ese monto, así que el checkout
cortaba antes de evaluar el plástico. Repetido con $1.150 (`S00024`) y la misma tarjeta de rechazo,
Nave respondió lo que se buscaba:

```
pantalla  → "La tarjeta con la que intentaste pagar no tiene el dinero necesario"
intención → FAILURE_PROCESSED / REJECTED
Odoo      → cancel | motivo: no_amount_available | 0 asientos | pedido sin confirmar
```

El camino de rechazo queda verificado de punta a punta con un rechazo de tarjeta real: no se
contabiliza nada y el pedido no se confirma.

#### El endpoint de devolución existe; falta el permiso

El sondeo distingue tres respuestas del gateway, lo que permite afirmar algo que antes era
suposición. Las tres con el mismo bearer token válido:

| Petición | Respuesta |
|---|---|
| `GET /api/ruta_que_no_existe_jamas` | `403 {"message": "Invalid key=value pair…"}` |
| `DELETE /api/ruta_que_no_existe_jamas` | `403 {"message": "Invalid key=value pair…"}` |
| `GET /api/payments/{uuid inexistente}` | `404 {"code": "INVALID_PAYMENT"}` |
| **`DELETE /api/payments/{uuid inexistente}`** | **`403 {"Message": "User is not authorized to access this resource because no identity-based policy allows the execute-api:Invoke"}`** |
| `DELETE /api/payment_request/{uuid}` | `403 {"message": "Invalid key=value pair…"}` |

Una ruta que el gateway no mapea devuelve *"Invalid key=value pair"*. El DELETE sobre
`/api/payments/{id}` devuelve otro mensaje distinto, el de IAM: **la ruta está mapeada y el llamador
no tiene permiso**. Si no existiera, devolvería el primero.

O sea que `DELETE /api/payments/{payment_id}` —el que usa `_send_refund_request`— sigue siendo la
ruta correcta, y lo que hay que pedirle a Nave es que habilite ese método para nuestro `client_id`,
no que nos diga cuál es el endpoint. B2, B6 y D5 siguen bloqueadas, pero por un permiso identificado.

Se probaron además `POST /api/payments/{id}/refund` y `POST /ranty-payments/payments/{id}/refunds`
por si la devolución se hubiera mudado: las dos devuelven el mensaje de ruta no mapeada.

Ninguna de estas pruebas devolvió dinero: todas se hicieron contra un `payment_id` inexistente.

### 3.20 A6, A9 y A13 ejecutados: el detalle de productos miente con cantidades fraccionarias (2026-10-05)

Tres cobros de checkout contra sandbox, con ingreso manual de tarjeta. Evidencia del lado del cliente
en `docs/homologacion/evidencias/<caso>/`.

| Caso | Pedido | Intención | Odoo | Resultado |
|---|---|---|---|---|
| A6 | S00018 $10,00 | `FAILURE_PROCESSED` / `REJECTED` | `cancel` | ⚠️ con reparo |
| A9 | S00019 $123,45 | `SUCCESS_PROCESSED` / `APPROVED` | `done` | ✅ |
| A13 | S00020 $120,00 (0,15 kg) | `SUCCESS_PROCESSED` / `APPROVED` | `done` | 🔴 defecto |

**A9 cierra el caso de los decimales.** $123,45 viajó como `"123.45"`, volvió aprobado y quedó en el
asiento `PBNK1/2026/00006` por el mismo importe. Sin redondeos en ningún tramo. Cobrado con NARANJA
CREDIT ****3355, 1 cuota, cupón `HBZ406310060`.

**A6 verifica el camino de rechazo, pero no el que se buscaba.** Odoo lo llevó a `cancel`, sin asiento
contable y con el pedido sin confirmar, que es lo que debe pasar. El reparo es el motivo: Nave informó
`invalid_installment_plan`, no una tarjeta rechazada. Con $10 no hay plan de cuotas posible, así que
el checkout corta antes de evaluar el plástico. Para un rechazo de tarjeta genuino hay que repetirlo
eligiendo **1 cuota**, o con un importe que admita financiación.

#### 🔴 A13: el detalle de productos no cuadra con lo que se cobra

Una línea de 0,15 kg a $800/kg se cobró bien —$120,00— pero Nave recibió esto:

```json
"products": [{"name": "[PRUEBA] Granel por kilo",
              "quantity": 1,
              "unit_price": {"currency": "ARS", "value": "800.00"}}],
"amount": {"currency": "ARS", "value": "120.00"}
```

**1 × $800,00 no da $120,00.** El cobro sale por `amount`, así que el dinero es correcto, pero el
detalle que Nave muestra en el checkout y en el comprobante que el cliente descarga dice otra cosa.

La causa es `int(line.product_uom_qty) or 1` (`payment_transaction.py:161`, y su gemelo
`int(line.quantity) or 1` en `:174` para facturas). Rompe en dos direcciones:

| Cantidad real | Se envía | Detalle que ve el cliente | Se cobra |
|---|---|---|---|
| 0,15 kg × $800 | `1` | $800,00 | $120,00 |
| 2,5 h × $1.000 | `2` | $2.000,00 | $2.500,00 |
| 1 u × $500 | `1` | $500,00 | $500,00 ✅ |

Alcanza a cualquier venta por peso, por tiempo o por medida: granel, servicios por hora, metros de
tela, litros. No es un caso de borde del catálogo de prueba.

**Sondeo contra sandbox para no diseñar a ciegas** (la doc no aclara si `quantity` admite decimales):

| Payload | Respuesta |
|---|---|
| `quantity: 0.15`, unit `800.00`, total `120.00` | **HTTP 502** con una página HTML de error |
| `quantity: 1`, unit `120.00`, total `120.00` | **200 OK** |
| `quantity: 1`, unit `800.00`, total `120.00` | **200 OK** |

Nave **no acepta cantidades fraccionarias** —y ni siquiera devuelve un 400: se cae con un 502— y
acepta el detalle descuadrado sin validarlo. Así que la corrección no puede ser mandar el decimal:
cuando la cantidad no sea entera hay que enviar `quantity: 1` con el **subtotal de la línea** como
`unit_price` y la cantidad real en la descripción. Para cantidades enteras conviene seguir mandando
la cantidad tal cual, que es lo que el cliente espera ver.

El post-proceso de Odoo (confirmar el pedido, generar el asiento) va por el cron
`payment.cron_post_process_payment_tx`, no por el webhook: S00020 quedó unos minutos en `done` con el
pedido en borrador y sin asiento, hasta que corrió el cron y generó `PBNK1/2026/00007` por $120,00.
Conviene saberlo para no confundir esa ventana con un fallo.

#### C1 resuelto: la forma de `status` no es la misma en los dos lugares

La respuesta de `GET /api/payment_requests/{id}` trae el estado de la intención como objeto y el de
cada intento como string plano:

```json
"status": {"name": "FAILURE_PROCESSED"},
"payment_attempts": {"attempts": 1,
                     "payments": [{"payment_id": "07e8d666-…", "status": "REJECTED"}]}
```

La suposición del código (`payment_nave.js:124`: *"suponiendo estructura {status:{name:...}}"*) es
**correcta para la intención** y **equivocada para los intentos**. Hoy no nos afecta porque
`_nave_extract_payment_id` sólo lee `payment_id` de ahí, pero quien escriba
`payments[-1]['status']['name']` se lleva un `AttributeError`. Pasó al escribir el script de
diagnóstico de esta misma corrida.

Claves de la raíz, por si sirven más adelante: `additional_info`, `amount_type`, `application`,
`application_id`, `buyer`, `capture_data`, `creation_date`, `expiration_date`, `external_payment_id`,
`id`, `payment`, `payment_attempts`, `payment_gateway`, `payment_retries_allowed`, `payment_type`,
`platform`, `seller`, `shipping`, `status`, `transactions`.

#### Lo que confirman las capturas

Con el pago aprobado, el checkout ofrece **"Descargar el comprobante"** y **"Volver a la tienda"**.
Ese segundo botón existe porque el checkout manda `additional_info.callback_url`, y es exactamente lo
que le falta al wizard del link de pago (B7c): el cliente que paga una factura no tiene cómo volver.

Con el pago rechazado, la única salida es **"Volver a intentar"**: no hay retorno a la tienda ni
siquiera con `callback_url` presente. Quien abandona ahí se queda en el sitio de Nave.

### 3.19 A8 verificado: la intención expira y el cron la cierra sola (2026-10-05)

Tres intenciones de checkout creadas a las 17:07 UTC quedaron sin pagar. A las 17:57 UTC —exactamente
los 3000 s del `duration_time`— Nave las pasó de `PENDING` a `EXPIRED`, con `payment_attempts.payments`
vacío. Nave **no notifica la expiración**: no llega ningún webhook, así que las tres transacciones
siguieron en `draft` en Odoo.

Corrida manual del cron de conciliación (B9):

```
[payment_nave] Reconsultando 3 transacciones pendientes.
S00011 | estado=cancel | mensaje=Nave informó la intención de pago como EXPIRED.
S00012 | estado=cancel | mensaje=Nave informó la intención de pago como EXPIRED.
S00013 | estado=cancel | mensaje=Nave informó la intención de pago como EXPIRED.
```

Tres cosas que esto deja probadas con datos reales, no con mocks:

1. El catálogo de estados de la intención incluye `EXPIRED` tal como lo documenta Nave, y
   `_nave_poll_payment_request` lo lleva a `_set_canceled` con el motivo a la vista. El pronóstico
   viejo de la matriz (`_set_error` "Estado desconocido") ya no aplica.
2. El cron alcanza transacciones en `draft`, no sólo en `pending`. Importa: una intención que expira
   sin ningún intento de pago nunca pasa por `pending`, así que un dominio restringido a `pending`
   —que es lo que uno escribe por reflejo— las habría dejado colgadas para siempre.
3. La expiración es la única resolución de una intención que **no** genera webhook. Sin el cron no hay
   forma de enterarse.

**Pendiente de diseño**: el `duration_time` del checkout está hardcodeado en 3000 s
(`payment_transaction.py:85`), mientras el wizard del link sí lo expone como `duration_hours` y el
default de Nave es una semana en los cuatro flujos. Cincuenta minutos es razonable para un carrito
web, pero es un número que nadie puede cambiar sin editar el código. Va junto con B7c (el wizard del
link no manda `additional_info.callback_url`, así que el cliente que paga una factura nunca vuelve a
Odoo) como un mismo cambio sobre la construcción de los payloads.

### 3.18 El checkout recibe los datos de tarjeta y cuotas, y los descarta (2026-10-05)

Verificado consultando el pago de `S00007` ($1.150, caso A4) contra la API. La respuesta de
`GET /ranty-payments/payments/{id}` para un cobro **online** trae lo mismo que la de Nave Point:

```json
"card_brand": "VISA", "card_type": "CREDIT", "card_last4": "0231",
"issuer": "BANCO SANTANDER ARGENTINA S.A.", "payment_code": "AYO870166980",
"payment_input": "manual_input",
"installment_plan": {
  "name": "CUOTA SIMPLE 3", "installments": 3, "has_interest": true,
  "interest_rate": "7.40", "annual_nominal_rate": 63, "total_financial_cost": "9.83",
  "total_amount": {"value": "1263.10", "currency": "ARS"}
},
"auth_data": {"auth_id": "002999", "ticket": {"number": "11", "batch": "490"}}
```

**`payment_nave` descarta todo eso.** Sólo guarda `nave_payment_id` y, en el chatter, la billetera
—que en un pago con tarjeta viene `N/A`—. `pos_nave` sí lo extrae para el ticket desde `18.0.1.4.0`.

**El dato que más pesa: el cliente pagó $1.263,10, no $1.150.** Eligió 3 cuotas con interés
(7,40%, CFT 9,83%), así que el total financiado difiere del monto de la venta. Nuestra
`payment.transaction` registra 1.150, que es correcto desde la óptica del comercio, pero **en Odoo
no queda rastro de que el cliente pagó en cuotas ni de cuánto**.

Dos consecuencias:

1. **Para la homologación**: si Nave pide ver marca, últimos cuatro, cupón, lote y plan de cuotas en
   el flujo online —como se presume que los pedirá en el presencial—, hoy no los tenemos.
2. **Para la operación**: ante un reclamo, no se puede responder con qué tarjeta ni en cuántas
   cuotas pagó el cliente sin entrar al panel de Nave.

Nota al margen: el caso A4 se ejecutó con la tarjeta rotulada "6 cuotas" en la documentación, pero
el plan aplicado fue de **3**. El plan lo elige el pagador en el checkout, no la tarjeta.

**Resuelto y verificado el mismo día.** El cobro `S00009` ($1.150 en 3 cuotas) entró ya con el
módulo en `18.0.1.10.1` y quedó registrado completo:

| Campo | Valor |
|---|---|
| Tarjeta | VISA CREDIT ****0231 — BANCO SANTANDER ARGENTINA S.A. |
| Ingreso | `manual_input` |
| Cupón / autorización / lote | `FPK468700137` / `002999` / `490` |
| Plan | 3 cuotas, con interés, tasa 7,40%, TNA 63%, CFT 9,83% |
| Total pagado por el cliente | $1.263,10 (contra $1.150,00 de la venta) |

El contraste entre los dos mensajes de estado es la evidencia más corta de qué cambió:

```
S00007 (antes) → Pago Aprobado con éxito. Billetera utilizada: N/A. Nave ID: efb673c7…
S00009 (ahora) → Pago aprobado. Tarjeta: VISA CREDIT ****0231 · Cuotas: 3 ·
                 total pagado por el cliente: 1263.10 · Cupón: FPK468700137. Nave ID: a19dc285…
```

**`payment_input: "manual_input"` cierra además una duda operativa**: el checkout de sandbox **sí**
habilita el ingreso manual de tarjeta. La doc advertía que eso depende de la configuración del
comercio y que sin él sólo se puede pagar escaneando con billetera, lo que habría dejado A2–A6 sin
poder ejecutarse. Están ejecutables.

### 3.17 🔴 El proveedor de producción tiene credenciales de sandbox (2026-10-05)

Verificado probando las credenciales cargadas contra los dos endpoints de autenticación, desde el
propio servidor:

| Ambiente | Resultado |
|---|---|
| Producción (`services.apinaranja.com`) | **HTTP 401**, sin token |
| Sandbox (`homoservices.apinaranja.com`) | **HTTP 200**, token emitido |

La configuración quedó mezclada: **URLs de producción** (proveedor en `enabled`), **credenciales de
sandbox** y **`pos_id` de producción** (`b4c94f29` para tienda, `925a1b22` para link de pago).

**Con eso no se puede cobrar por ningún flujo**: ni checkout ni link, porque la autenticación falla
antes de llegar a crear la intención.

Es el primer punto del checklist de §3.11 —*"cargar las credenciales de producción antes de cambiar
el estado"*— que quedó sin hacer. El orden importa justamente por esto: con el estado cambiado y las
credenciales viejas, el error que se ve es un 401 que no dice qué falta.

**Para destrabar**: cargar el set de credenciales de producción que Nave entrega aparte del de
sandbox. Si todavía no lo recibimos, pedirlo en el hilo abierto con integraciones.

Nota: el `pos_id` de link de pago (`925a1b22`) quedó cargado y la resolución por medio funciona
—se verificó que `ecommerce` devuelve el de tienda y `payment_link` el suyo—, así que ese frente
queda listo para cuando haya credenciales.

### 3.16 Sandbox restringido, terminal de producción vinculada y `pos_id` por ambiente (2026-09-26)

**El sandbox de Nave sólo opera de 10:00 a 18:00.** Lo informó soporte (Jonathan Castillo) el 2026-09-24. Ese horario no coincide con el de trabajo en este proyecto, así que **el sandbox queda descartado en la práctica**. La homologación restante sigue por la vía de §3.11 (producción acotada).

- **Rechazos (A5, A6, C3):** se provocan con **tarjeta vencida o CVV incorrecto**.
- **QR en sandbox:** no se puede probar desde la terminal de prueba, sólo desde el simulador de `navenegocios.ar/home/developers`.

**Terminal de producción:** serie `L40037644`, llegó antes del 28/09 y ya está **vinculada**. Falta su `pos_id` (P17).

**`pos_id` conocidos, por ambiente.** El ambiente se define por **de dónde sale el id**, no por el nombre del local: el comercio puede renombrar un dispositivo, y "ONLYONE test" hoy se llama "Be Onlyone".

| `pos_id` | Origen | Ambiente |
|---|---|---|
| `f71ba756-1d80-4ab3-9f43-5dc247fd6c4a` | Mail *"Integración Nave \| Sandbox \| Onlyone"* (2026-06-18), rotulado "POS ID de Prueba (Test)". Es también el UUID de ejemplo de toda la doc de Nave | Sandbox |
| `b1c04ade-dec9-4ca0-9fd9-8464c9006764` | Terminal `L40000978` (DEBUG), §3.5 | Sandbox |
| `b4c94f29-0910-448e-9ad7-6dd2f791a957` | *Sistema de gestión*: medio ECOMMERCE. Sirve para cualquier tienda (ver alerta 1). **Cargado en producción el 2026-10-05** | Producción |
| `925a1b22-fc90-47b7-a92a-cf9f621139b5` | *Sistema de gestión*: local LINK DE PAGO, medio LDP | Producción |
| pendiente | Terminal Nave Point `L40037644` | Producción |

**Dos alertas:**

1. ~~**`b4c94f29` figura bajo el local WOOCOMMERCE.**~~ ✅ **RESUELTO (2026-10-05)**: el `pos_id` de
   e-commerce **sirve para cualquier tienda**. Lo que Nave valida es la `notification_url` que le
   informamos, no el nombre del local bajo el que figura el dispositivo. Cargado en producción el
   2026-10-05.

   Ojo con el alcance de esa afirmación: vale **entre tiendas**, no **entre medios de cobro**. El
   error `INVALID_POS` dice textualmente *"Given POS is for a different payment type"*, así que
   ECOMMERCE y LDP siguen siendo identificadores distintos — que es justamente la alerta 2.
2. **Los links de pago tienen su propio `pos_id` (LDP), pero el módulo usa `provider.nave_pos_id` tanto para checkout (`payment_transaction.py:68`) como para links (`nave_link_wizard.py:186`).** Con un solo valor cargado, uno de los dos flujos va a recibir `409 INVALID_POS`. Hace falta un campo aparte para el `pos_id` de links.

Los códigos `J-6A0F-A859-A` y `P-6A2A-F7D3-D` de *Tienda online propia* **no** son `pos_id`: son códigos de vinculación (§3.9.j).

### 3.15 Cronograma: la terminal de producción llega el 2026-09-28

| Hasta el 28/09 | Desde el 28/09 |
|---|---|
| Terminal de **test**, sólo cobra por QR | Terminal de **producción**, cobra con plástico real |
| Ejercitar C1, C2b y B3 pagando con billetera | C2 (chip), C3 (rechazo) y C12 (ticket completo) |
| Proveedor en `test` | Proveedor en `enabled` (§3.11) |

**Tres cosas que hay que tener listas para el lunes:**

1. **El `pos_id` de la terminal nueva** (P17). Es otro dispositivo, así que tiene el suyo. Si llega
   sin ese dato, el lunes se pierde pidiéndolo — y ya sabemos qué pasa cuando el `pos_id` no
   corresponde: la llamada cuelga hasta el timeout (§3.13).
2. **El checklist de cambio de ambiente** de §3.11: credenciales de producción primero, después el
   estado, y verificar que el token cacheado quedó vacío.
3. **Cerrar la sesión del POS antes de cambiar el `nave_terminal_id`.** Odoo no deja modificar un
   método de pago con sesiones abiertas (caso C16). Reemplazar la terminal de test por la de
   producción exige cierre de caja previo: conviene hacerlo antes de empezar, no a mitad de prueba.

**Aprovechar la ventana hasta el lunes** para dejar cerrado todo lo que no depende de la tarjeta:
C1 (vocabulario real de estados), C2b (camino feliz por QR) y B3 (que el `transaction_id` guardado
sea el `payment_id` del pago). Si eso queda verificado antes, el lunes se dedica sólo a lo que
requiere plástico.

### 3.14 Terminal vinculada, pero sólo cobra por QR (2026-09-23)

> **Corrección (2026-09-24):** según soporte de Nave, la terminal de prueba **sí** tiene tarjetas de prueba. Al elegir *Tarjeta* ofrece *Leer tarjeta* o **Simular**, que muestra tarjetas simuladas de distintas marcas (recomiendan NFC Crédito Visa o Chip). Sólo funciona **de 10:00 a 18:00**. Probablemente no apareció porque se probó fuera de ese horario. Ver §3.16.

Nave envió un código de vinculación nuevo y **la terminal `L40000978` quedó operativa**. Confirmaron
además el mismo `pos_id`: `b1c04ade-dec9-4ca0-9fd9-8464c9006764`.

**Limitación nueva**: no tenemos **plásticos de prueba**. El equipo es de test, así que no procesa
tarjetas reales, y sin tarjetas de prueba físicas el cobro con chip/contactless no se puede ejercitar.

Lo que sí se puede, y no es poco: **la terminal cobra por QR**. El flujo `smart_pos` completo
—crear la intención, entregarla al equipo, que el cliente pague, y que Odoo lo detecte por polling—
queda ejercitable de punta a punta, pagando con billetera en vez de tarjeta.

| Caso | Estado |
|---|---|
| C1 — vocabulario real de estados | ✅ **ahora ejecutable**. Es la prueba más valiosa pendiente |
| C2b — camino feliz completo | ✅ ejecutable vía QR desde la terminal |
| C3 — rechazo | ⚠️ difícil de provocar sin tarjeta |
| C2 — cobro con chip | 🚫 **bloqueado por P16** (sin plásticos de prueba) |
| C12 — datos del ticket | ⚠️ parcial: un pago por billetera devuelve `wallet_name`, no marca ni últimos 4 |

**Consecuencia sobre el código**: `_apply_payment_details` llena marca, tipo, últimos 4, titular y
emisor desde `payment_method`. En un cobro por QR esos campos vienen vacíos y el ticket muestra sólo
la billetera. Es el comportamiento correcto, pero significa que **la parte de tarjeta del ticket
queda sin verificar** hasta que haya plásticos.

### 3.13 Verificación en producción tras cargar el `pos_id` correcto (2026-09-23)

Con `b1c04ade-…` cargado en el método de pago y el código nuevo desplegado, se lanzó un cobro de
$ 12,00 desde el POS. Resultado, medido en el log del servidor:

| Hito | Evidencia |
|---|---|
| **El `pos_id` era la causa raíz** | `Enviando solicitud Smart POS a la terminal b1c04ade-…` y la intención se crea en <1 s. Con el `pos_id` de e-commerce la misma llamada colgaba 10 s y moría |
| **`e3-api.ranty.io` es correcto** | La API responde normal. El commit `ffb524b` esquivaba un host sano |
| **B11 — vocabulario de estados** | El polling corre cada ~3,4 s, respuestas 200 en ~0,3 s, sin romperse |
| **B4 — watchdog** | Intención a las 00:44:12, última consulta a las **00:49:11**. 299 s: cortó en el segundo previsto y el POS mostró *"Se agotó el tiempo de espera del cobro"* con la línea en "Volver a intentar" |
| **Sin cobro fantasma** | La orden anterior se cerró en **Efectivo**, sin `transaction_id` de Nave |

**Lo que falta es sólo la vinculación.** Nave acepta y registra la intención, pero no tiene a qué
dispositivo entregársela, así que el ciclo llega al tope sin novedad. Todo el lado Odoo está probado.

**🔴 C4 confirmado con evidencia**: la baja de una intención `smart_pos` devuelve

```
400 Client Error: Bad Request for url: .../api/payment_requests/{id}
```

consistente con el catálogo de errores, que sólo admite baja para `payment_link, dynamic_qr,
static_qr`.

> **Corregido el 2026-10-07 (§3.36 y §3.37):** la explicación era equivocada. El 400 no venía del tipo
> de intención sino de la descripción del motivo, que Nave exige fija. Con `disabled from SAAS`, la
> baja de una intención `smart_pos` funciona.

**Arreglado (`2ccc47d`)**: el cliente ahora lee la respuesta y, si Nave rechazó la baja, avisa que el
cobro puede seguir activo en la terminal y hay que cancelarlo desde el equipo. Se sigue devolviendo
`true` a propósito: con `false` el core deja la línea en `waitingCard` con el polling ya detenido, y
el cajero queda sin salida.

**Pendiente**: preguntarle a Nave cómo se da de baja una intención de terminal (agregado al borrador
de correo). Si no hay forma desde el sistema, el comportamiento actual es el correcto y hay que
documentarlo en el instructivo del cajero.

### 3.11 Modo acordado: producción acotada (2026-09-22)

**Decisión**: se homologa sobre `www.onlyone.ar` con **cobros reales de importe acotado**, en lugar
de esperar el comercio de prueba de Nave (§3.10).

| Límite | Valor |
|---|---|
| Por transacción | **ARS 1.200** |
| Total acumulado | **ARS 90.000** |

**Lo que esto implica, y no es menor:**

1. **El proveedor tiene que pasar a `enabled`.** Con `state = 'test'` las URLs apuntan a sandbox y
   una tarjeta real no puede procesarse. No hay forma de cobrar de verdad quedándose en Prueba.
2. **Los cobros son reales**: acreditan en la cuenta CA $ 4008221-1 158-9 de Banco Galicia, generan
   asientos reales y las devoluciones devuelven plata de verdad.
3. **Hay que usar los `pos_id` de producción** de cada dispositivo (§3.9.k).
4. **Las credenciales son las de producción.** Son un set distinto del de sandbox y ocupan los
   mismos dos campos del proveedor.

**Checklist de cambio de ambiente** — en este orden:

- [ ] Cargar las credenciales de **producción** (`nave_client_id`, `nave_client_secret`).
- [ ] Cargar el `nave_pos_id` del punto de venta **ECOMMERCE** (`www.onlyone.ar`).
- [ ] Pasar el proveedor a **Habilitado**.
- [ ] Verificar que `nave_access_token` quedó vacío. *(Desde 18.0.1.7.1 se limpia solo al cambiar
      estado o credenciales; antes había que hacerlo a mano o el módulo mandaba el token de sandbox
      a producción durante 24 h.)*
- [ ] Primera transacción por el importe mínimo posible, verificada de punta a punta.
- [ ] Revisar que no queden transacciones de sandbox en `pending`: el cron de conciliación las
      reconsultaría contra **producción**, donde su `payment_id` no existe.

**Consecuencias sobre la matriz de casos:**

| Caso | Efecto |
|---|---|
| A2-A4 (aprobados) | ✅ Ejecutables con tarjeta real, importes ≤ 1.200 |
| **A5, A6 (rechazos)** | ⚠️ **Ya no se pueden provocar a voluntad**: las tarjetas de prueba no sirven en producción y un rechazo real por fondos no es reproducible. Alternativa: tarjeta vencida o CVV inválido, o pedirle a Nave un medio de rechazo en producción |
| C9 ("Force done") | 🔴 Pasa de riesgo operativo a **riesgo financiero**: cerrar una venta como cobrada sin cobro real, con plata de por medio |
| A14/A15, C13, H9 (devoluciones) | ⚠️ Devuelven dinero real. Y siguen bloqueadas por N12 |
| Todos | Importes de prueba a fijar **por debajo de 1.200**; llevar la cuenta del acumulado |

**No cambia** el bloqueo de la terminal: el equipo `L40000978` se identifica como dispositivo TEST y
sigue sin poder vincularse (§3.10). Esta decisión destraba los flujos **online**, no los presenciales.

### 3.10 🔴🔴 BLOQUEANTE: no tenemos acceso al ambiente de prueba del comercio

Hallazgo del 2026-09-21, y es el que frena hoy **todo** el testing presencial.

> ⏳ **Actualización 2026-09-22 (2)**: el código de vinculación del 14/08 **ya no es aceptado** por
> la terminal. Se pidió uno nuevo en el mismo hilo. El bloque C sigue en espera, pero por un trámite
> acotado y con el `pos_id` ya en mano, no por falta de acceso a un ambiente.
>
> ✅ **Actualización 2026-09-22**: aparece un camino. En el hilo del 2026-08-14, Nave no pidió un
> local "test": mandó el `pos_id` de la terminal y un **código de vinculación**, con la instrucción
> de *"reiniciar la terminal e ingresar el código de vinculación"*. Probar eso antes de dar el bloque
> presencial por bloqueado. Ojo: el código tiene más de un mes y puede haber caducado; si no entra,
> pedir uno nuevo en el mismo hilo.

**Los hechos (relevados el 2026-09-21):**

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

**l) Dónde NO está el `pos_id`.** La ficha de un punto de venta de e-commerce
(`/business/virtual-branch/385213`) muestra datos de la tienda, cuenta de acreditación y medios
aceptados, **pero no el `pos_id`**. Hay que buscarlo en el menú `⋮` de la ficha (que expone
"Números de identificación del local") o, según indica la documentación, en el archivo de
*Integraciones > Sistema de gestión*.

La ficha de un local presencial (`/business/qr-wrapper-commerce/payment-methods`) sí separa los
dispositivos en pestañas **Código QR** y **Nave Point**. Bajo Código QR figuran **QR 1** y **QR 2**,
con acciones "Crear nuevo QR" y "Asociar QR pre impreso". El `pos_id` de cada QR debería salir del
menú `⋮` de cada uno.

**k) ✅ Los puntos de venta están en *Negocios > Puntos de venta*, uno por tipo de pago.**

La pantalla (`/business/qr-payments?payment_types=static_qr,smart_pos,ecommerce,without_pos`) lista
cuatro, y la propia URL enumera los tipos posibles — confirmación directa del error `INVALID_POS`:

| Punto de venta | Referencia | Tipo(s) |
|---|---|---|
| WOOCOMMERCE | `www.onlyone.aureofy.net` | ecommerce |
| **ECOMMERCE** | **`www.onlyone.ar`** | ecommerce ← **el de nuestro Odoo** |
| Be onlyone Jujuy | Anatuya 15, Jujuy | **Nave Point** + **QR** |
| Be Onlyone Jujuy QR | Anatuya 15, Jujuy | **QR** |

Entrando a cada uno se obtiene su `pos_id`. El mapeo que corresponde:

| Dónde va en Odoo | Punto de venta del que sale |
|---|---|
| `payment.provider.nave_pos_id` (checkout y link) | **ECOMMERCE** (`www.onlyone.ar`) |
| `pos.payment.method.nave_terminal_id` con terminal `nave` | **Be onlyone Jujuy** → Nave Point |
| `pos.payment.method.nave_terminal_id` con terminal `nave_qr` | **Be onlyone Jujuy** → QR, o **Be Onlyone Jujuy QR** |

Ojo: hay **dos puntos de venta de e-commerce** (WooCommerce y el nuestro). Verificar que el
`nave_pos_id` cargado sea el de `www.onlyone.ar` y no el de WooCommerce.

Pendiente de N9: si estos `pos_id` son los productivos, los de sandbox pueden ser otros.

**j) 🔴 Los códigos de *Tienda online propia* NO son los `pos_id`.** En
*Integraciones > Tienda online propia* figuran dos tiendas dadas de alta, cada una con un código con
formato `X-XXXX-XXXX-X`. Ese es el **código de vinculación**: el que se manda por mail a Nave junto
con el CUIT para que emitan las credenciales (`doc_checkout.md` §1). **No sirve como
`seller.pos_id`**, que es un UUID.

Los `pos_id` están en otra subsección: **Integraciones > Sistema de gestión**, donde se descarga el
archivo con los IDs de los puntos de venta. Es la instrucción que repiten las cuatro páginas de la
documentación vigente.

Dato útil de esa pantalla: hay **dos tiendas registradas**, una para `www.tienda.onlyone.ar` y otra
para `www.onlyone.ar`. Nuestro Odoo sirve `https://www.onlyone.ar` (`web.base.url` y el website id 3),
así que la tienda que le corresponde es la segunda. Vale verificar que el `nave_pos_id` cargado en el
proveedor pertenezca a **esa** tienda y no a la otra: sería otra fuente posible del `INVALID_POS`.

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

</details>

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
| A1 | Métodos visibles en checkout | Carrito → Pagar | Se listan los métodos habilitados de Nave | ✅ 2026-10-05: aparecen **"QR Interoperable Nave"** y **"Tarjeta"**, ambos con el sello "Asegurado por Nave". B7 queda descartado. §3.22 |
| A0 | ⚠️ Forma de pago en sandbox | Llegar al hosted checkout y ver qué ofrece | ✅ 2026-10-05: ofrece **las dos cosas**, "Código QR" e "Ingresá los datos" de tarjeta, con los datos del comprador precargados desde nuestro `buyer`. A2–A6 son ejecutables tal como están redactados. §3.22 |
| A2 | Pago aprobado con tarjeta Naranja | Carrito → Nave → `5895 6248 4026 3355` | Redirige a `checkout_url`, vuelve a `/payment/status`, webhook llega, tx `done`, pedido confirmado | ✅ 2026-10-05, S00030-2: el circuito entero, carrito a asiento contable. §3.23 |
| A3 | Pago aprobado con Visa 1 cuota | `4025 2200 0000 0139` | Ídem A2 | ✅ 2026-10-06: `done`, VISA CREDIT ****0139, 1 cuota, cupón `GDP476968633` |
| A4 | Pago aprobado con Visa 6 cuotas | `4761 2299 9900 0231` | Ídem A2 + verificar que el plan de cuotas queda registrado | ✅ 2026-10-06: venta $1.150, el cliente pagó **$1.364,66** en 6 cuotas (tasa 13%, TNA 63%, CFT 18,67%). Todo registrado. §3.26 |
| A5 | Rechazo por fondos | `4025 2200 0000 0127` | tx → `cancel` con el `reason_code` de Nave | ✅ 2026-10-06: `cancel` con motivo `no_amount_available`, pedido sin confirmar, 0 asientos |
| A6 | Rechazo Naranja | `5895 6248 9347 1379` | Ídem A5 | ✅ 2026-10-05, S00024 ($1.150): rechazo de tarjeta genuino (`no_amount_available`) → `cancel`, sin asiento, pedido sin confirmar. §3.21 |
| A7 | Abandono del checkout | Llegar a Nave y cerrar la pestaña | tx queda `draft`, el pedido no se confirma, sin asientos | ✅ 2026-10-06: `draft`, pedido sin confirmar, 0 asientos, y en Nave `PENDING` con 0 intentos. El cron la cierra al expirar (§3.19) |
| A8 | Expiración de la intención | Crear intención y esperar los 3000 s del `duration_time` hardcodeado (`payment_transaction.py:85`) | Nave marca `EXPIRED` y el cron de conciliación deja la transacción en Cancelado con el motivo a la vista | ✅ 2026-10-05, §3.19 |
| A9 | Monto con decimales | Pedido por $123,45 (tope de homologación) | `amount.value == "123.45"` (string, 2 decimales) en el payload | ✅ 2026-10-05, S00019: $123,45 exacto hasta el asiento contable, sin redondeos. §3.20 |
| A10 | Cliente sin CUIT ni email | Partner incompleto | Se envían los defaults `'00000000'` / `'correo@temporal.com'` y dirección `S/D`. Confirmar que Nave los acepta | ✅ 2026-10-06: **Nave los acepta** y el checkout carga normal. Un cliente sin datos puede comprar |
| A11 | CUIT con guiones | Partner con `20-05536168-2` | El módulo no limpia guiones. Verificar si Nave lo rechaza | ✅ 2026-10-06: **Nave acepta el CUIT con guiones** tal cual se envía. No hace falta limpiarlo |
| A12 | Descuadre productos vs total | Pedido con IVA | Los `products[]` iban **sin IVA** y `amount` **con** IVA | ✅ 2026-10-05: resuelto en origen. El detalle pasó a viajar con impuestos incluidos, así que ya no hay descuadre que validar. §3.20 |
| A18 | Datos del cobro registrados | Tras un cobro aprobado, abrir la transacción en Odoo | Figuran marca, tipo, últimos cuatro, emisor, cupón, autorización y lote; con cuotas, también el plan y el total pagado por el cliente | ✅ 2026-10-06: verificado en A4 contra el **comprobante que emite Nave**, que coincide campo por campo. §3.26 |
| A16 | 🔴 Rechazo seguido de aprobación | Pagar con tarjeta de rechazo, y en la misma pantalla usar "Volver a intentar" con una aprobada | La transacción termina en **`done`**, el pedido se confirma, y el chatter muestra el rechazo y la recuperación en orden. **Observado roto el 2026-10-05 (S00005)**: Odoo descartaba la aprobación y dejaba la transacción en `cancel` con un cobro real sin registrar. Corregido por el cambio `recover-transaction-on-later-approval` | ✅ 2026-10-06, A16-S00042: el segundo intento entra y la transacción termina en `done` con el mensaje *"Tras un intento rechazado previamente — Pago aprobado…"*. §3.26 |
| A17 | Rechazo tardío sobre un cobro aprobado | Simular la llegada de un webhook `REJECTED` después de uno `APPROVED` | La transacción sigue en `done` y conserva el `payment_id` del pago aprobado. Queda advertencia en el log |✅ 2026-10-06, A16-S00042: se reenvió el webhook del intento rechazado sobre la transacción ya aprobada y **no la pisó**: siguió en `done` con el pago aprobado. §3.26 |
| A14 | Devolución total desde backend 🔴 | Factura pagada → botón Reembolsar | `DELETE /api/payments/{id}` → `CANCELLING`, tx hija creada. Odoo **no debe ofrecer monto parcial** (`full_only`, N10). 🚫 Hoy el botón no existe (B6) | ⬜ |
| A15 | Cierre del ciclo de devolución 🔴 | Tras A14, esperar el webhook `REFUNDED` | La transacción y la factura reflejan la devolución. 🚫 Hoy el webhook **no cambia nada** (B6.4) | ⬜ |
| A13 | Cantidad fraccionaria | Línea con qty 0,15 kg × $800 | `int(qty) or 1` → se envía 1 (`:161`). Verificar impacto | ✅ 2026-10-05: corregido y verificado contra sandbox. Nave recibe `quantity: 1 × $120,00` con la cantidad real en la descripción, y el detalle suma lo cobrado. §3.20 |

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
| C0 | Ruteo a la terminal correcta 🔴 | Lanzar un cobro con el `pos_id` actual | El cobro **aparece en la terminal `L40000978`**. Si no aparece, el `pos_id` es el de e-commerce (§3.5) y hay que pedirle a Nave el de la terminal |✅ 2026-10-06: el cobro apareció en la terminal **L40037644**, la del `pos_id` configurado. §3.27 |
| C1 | Contrato de estados 🔴 | Cobrar y capturar la respuesta cruda de `GET /api/payment_requests/{id}` | Documentar la forma exacta de `status` y el catálogo completo de valores. **Todo el polling depende de una suposición del código** (`payment_nave.js:124`: *"suponiendo estructura {status:{name:...}}"*) | ✅ 2026-10-05: forma capturada en §3.20. La suposición es correcta en la intención, pero **no** dentro de `payment_attempts` |
| C2 | Cobro aprobado con chip | Orden POS → Tarjeta → insertar chip → aprobar | Línea `done`, orden validada, `transaction_id` guardado |✅ 2026-10-06, POS 1/0001: línea cobrada, orden facturada (`FA-C 00001-00000004`) y `transaction_id` guardado. Se pagó por **NFC**, no por chip. §3.27 |
| C3 | Cobro rechazado | Tarjeta de rechazo en la terminal | Diálogo con el `reason_code`, línea en `retry`, el cajero puede reintentar |🔴 2026-10-07: la línea queda reintentable y no se contabiliza nada, pero Nave devuelve `BLOCKED` y el cajero lee *"Nave bloqueó la operación por motivos de seguridad. Contactá a Nave antes de reintentar"* por una tarjeta sin fondos. §3.30. ⚠️ Reprueba con 18.0.1.8.0: ya no hay alarma de seguridad, pero el aviso muestra el motivo de la intención (*"payment retries limit reached"*) en vez del de la tarjeta. ✅ Reprueba con 18.0.1.9.0: *"La tarjeta no tiene fondos suficientes. Podés reintentar o cobrar con otro medio."*, con el código sólo en el bloque de soporte. §3.31 |
| C4 | Cancelación desde Odoo | Iniciar cobro → botón Cancel | `DELETE` a Nave y la **terminal vuelve a reposo**. Ojo: `send_payment_cancel` retorna `true` siempre, incluso si el DELETE falló (`payment_nave.js:185-190`) | 🔴 2026-10-07: Nave rechaza toda baja desde Odoo con `400 Invalid input reason`: exige una descripción fija por código (`disabled from SAAS`) y Odoo manda una libre. La terminal sigue cobrando. §3.36. ✅ 2026-10-08, `18.0.1.11.1`: la baja funciona con la terminal pidiendo la tarjeta y con el cliente eligiendo cuotas; si el cliente toca *volver*, Nave da de baja la intención y el POS lo informa solo. §3.37 |
| C5 | Cancelación desde la terminal | Iniciar cobro → cancelar en el equipo | Nave notifica `DISABLED` con `manual_disabled_by_user`. **Se espera loop infinito** (B4) |⚠️ 2026-10-07: la terminal vuelve a reposo ("Ingresá el monto a cobrar") y el POS cierra la línea como reintentable. Pero el motivo que se le muestra al cajero es el mismo código que en C6, así que **no se distingue una cancelación de un vencimiento**. §3.29. ✅ Reprueba con 18.0.1.9.0: *"El cobro ya no está disponible. Generá un cobro nuevo."*, sin código en la explicación. Nave no informa el motivo de la baja en el 400. §3.31 |
| C6 | Expiración de la intención | Iniciar cobro y no tocar nada 300 s | Nave marca `EXPIRED`. **Se espera loop infinito** (B4) |⚠️ 2026-10-07: **no hay loop infinito**. Nave no manda `EXPIRED` sino `DISABLED` con `payment_request_is_disabled`: la terminal da de baja la intención. La línea queda reintentable y no se contabiliza nada, pero el cajero lee el código crudo. §3.28. ✅ Reprueba con 18.0.1.9.0: esta vez Nave respondió `EXPIRED` a los 303 s y el cajero leyó *"Cobro expirado"*. Un vencimiento llega a veces como `EXPIRED` y a veces como baja; el aviso es correcto en los dos casos. §3.31 |
| C7 | Salir de la pantalla de pago | Iniciar cobro → botón Back | La intención queda viva: **la terminal sigue cobrable**. No hay `close()` implementado | ✅ 2026-10-08: el core no llama a `close()` y el cobro sigue. Desde productos, una cancelación posterior funciona y un pago real se registra igual. Un segundo cobro con terminal en la misma pestaña lo bloquea el core. §3.38 |
| C8 | Corte de red durante el polling 🔴 | Iniciar cobro y cortar la conexión de Odoo | **Se espera spinner infinito sin diálogo de error** (B4). Verificar que la única salida es "Force done" | 🔴 2026-10-07: con un corte que falla al instante, el POS da el cobro por fallido a los ~9 s mientras la terminal sigue cobrando; Nave aprobó $150 y Odoo quedó en *"Volver a intentar"*, camino directo a un cobro doble. Con un corte que cuelga la consulta, el POS espera sin límite ni aviso. §3.34. ✅ Reprueba con 18.0.1.11.0: el corte ya no termina el cobro, el POS avisa y registra el pago al volver la conexión, y *Volver a intentar* encontró los $150 del pedido 104 sin cobrar de nuevo. §3.35 |
| C9 | "Force done" con pago rechazado | Rechazar en la terminal y presionar Force done | La venta se cierra como cobrada sin cobro real. **Hallazgo a documentar y mitigar** | 🔴 2026-10-07: después de un rechazo el botón no aparece, pero mientras se espera la tarjeta *Forzar terminación* deja la línea en *"Pago exitoso"* con *Validar* habilitado, sin cobro y con la terminal todavía cobrable. Unos 3 min después, la baja devuelve la línea a reintentable. §3.32. ✅ Reprueba con 18.0.1.10.1: el botón consulta a Nave; forzar mientras espera no da nada por cobrado, un rechazo da un solo aviso y sin conexión se pregunta al cajero sin que el polling le gane. Pendiente sólo el forzado sobre un cobro aprobado. §3.33 |
| C10 | Terminal ocupada | Lanzar un cobro con otro en curso | `device_already_on_payment_flow` (`doc_point.md` §6). Verificar el mensaje al cajero. **Caso real a cubrir** (2026-10-07): en una farmacia, 3 o 4 cajas (POS) comparten un solo Nave Point. Hoy el módulo asume una terminal por POS; probar dos cajas cobrando a la vez con la misma terminal, junto con C7 | ⏸️ Postergado el 2026-10-08, fuera del producto mínimo (§5.1) |
| C11 | Terminal con batería < 5% | Descargar la terminal | `low_battery`. Verificar manejo | ⬜ |
| C12 | Datos en el ticket | Cobro aprobado → imprimir | **Hoy no se llama a `set_receipt_info()`**: el ticket no imprime marca, últimos 4 ni cupón, aunque la API los devuelve (`doc_point.md:104-138`). Confirmar si Nave lo exige |✅ 2026-10-06: el ticket sí se completa. Lleva marca, últimos cuatro, tipo, cupón, autorización, lote y emisor. §3.27 |
| C13 | Devolución desde POS | Orden de devolución → Tarjeta | 🚫 Falla por B2/B3 (`REFUND-CIEGO`) | ⬜ |
| C14 | Webhook de baja de intención | Provocar un `DISABLED` | Es un **segundo contrato de webhook** con payload distinto (`payment_request_id`, `disabled_reason`, `doc_point.md` §8) que el módulo **no maneja** | ⬜ |
| C15 | Cierre de caja | Cerrar la sesión POS con cobros Nave | Los pagos quedan en el diario del método. No hay conciliación contra Nave | ✅ 2026-10-09: sesión `POS/00001` cerrada sin diferencias. Los cobros de Nave quedan en el diario Banco, en *Recibos pendientes*, a la espera del extracto. §3.42 |
| C16 | Cambio de `pos_id` con sesión abierta | Intentar editar el método de pago con una sesión POS abierta | Odoo lo rechaza. **Consecuencia operativa**: no se puede reemplazar una terminal a mitad de turno; hay que cerrar caja primero | ✅ verificado 2026-09-22 |

### Bloque H — QR interoperable presencial

> ✅ **B8 implementado el 2026-09-22** (`61d5101`), con tests unitarios. Falta ejercitarlo contra
> sandbox, para lo cual hace falta el `pos_id` de un QR de prueba (P13).
> 🟢 Además del simulador web, la doc publica un **simulador PCT** que paga *nuestra propia*
> intención: `PUT /qrtools/transfer_payment/simulation/payment` con el `payment_request_id` y el
> monto (`gateway`: `nxranty` o `coelsa`). Es el camino para H3 sin hardware ni billetera. Se puede ejecutar **sin billetera real** usando el
> endpoint de simulación de sandbox: `GET /instore/external/resolve?data={QR_FIJO}&access_token={TOKEN}`
> (`doc_qr.md` §10), que dispara el pago y el webhook end-to-end.

| ID | Caso | Pasos | Resultado esperado | Estado |
|---|---|---|---|---|
| H1 | Alta y descarga del QR | *Nave > Negocios > elegí el local > Descargar* (§3.9.d). Ojo: con Nave Point habilitado **no llega el kit POP impreso** | Se obtiene el QR y su `pos_id` (`doc_qr.md` §1) | ✅ 2026-10-08: el cartel del *QR 1* (*"Be onlyone Jujuy – QR 1"*) y su `pos_id` vienen del portal y del archivo `POS_ID-<CUIT>.xlsx`. §3.40 |
| H2 | Crear intención | Orden POS → método "Nave QR" | `POST /static_qr` con `qr_amount: "close"` y `amount.value` string de 2 decimales | ✅ 2026-10-08: Nave registra la intención como `static_qr` con `amount_type: close` y $147,00. §3.40 |
| H3 | Pago simulado aprobado | Llamar al endpoint de simulación | Webhook llega, línea `done`, orden validada | ➖ No hace falta: se probó con un pago real (H5) |
| H4 | Billetera usada | Ídem H3 | `wallet.name` (ej. `"mercado pago"`, `"modo"`) queda registrado para conciliación | ✅ 2026-10-08: la línea guarda el modo `wallet`, la billetera (*"bind pago"*, el procesador de Belo), el cupón y la autorización. §3.40 |
| H5 | Pago con billetera real | Escanear el QR físico desde una app | Mismo resultado que H3 | ✅ 2026-10-08, POS 1/0014: Belo mostró los $147 ya cargados, Nave aprobó y Odoo lo registró en la consulta siguiente. Factura `FA-C 00001-00000017`. §3.40 |
| H6 | Expiración | Crear intención y esperar el `duration_time` | `EXPIRED` manejado sin loop (depende de B11/B4) | ✅ 2026-10-08: `EXPIRED` a los 5 min (19:07:00 → 19:12:03 UTC). *"Cobro expirado"*, línea reintentable, sin loop. §3.40 |
| H7 | Cancelar intención | Cancelar desde el POS | `DELETE /api/payment_requests/{id}`, el QR deja de cobrar | ✅ 2026-10-08, exploratorio: Nave aceptó la baja de una intención `static_qr` desde Odoo (03:56 UTC). Un QR impreso no tiene pantalla que vuelva a reposo |
| H8 | Errores propios de QR | Forzar la condición | `ERROR_ENCODE_DYNAMIC_QR` y `NO_GATEWAYS_AVAILABLE` con mensaje claro al cajero (`doc_qr.md` §9) | ✅ 2026-10-09, `pos_nave 18.0.1.11.3`: aviso en castellano, con qué hacer y el código para soporte. `invalid_pos` verificado en producción; los otros seis, con las respuestas documentadas. §3.43 |
| H9 | Devolución | Devolver un pago QR aprobado | `DELETE /api/payments/{payment_id}` → `CANCELLING` → estado final asincrónico | ⬜ |
| H10 | Path de auth | Capturar el request de token | `doc_qr.md` §2 usa `m2ms`, el código usa `m2msPrivate` (N3) | ✅ 2026-10-08: en producción el token sale de `m2msPrivate` y el QR cobra con él |

### Bloque D — Webhooks y resiliencia

| ID | Caso | Pasos | Resultado esperado | Estado |
|---|---|---|---|---|
| D1c | Preflight OPTIONS | `curl -X OPTIONS .../payment/nave/webhook` | 200 con headers CORS. ✅ **verificado: responde 200** | ✅ |
| D2c | JSON inválido | POST con body roto | 400 "Invalid JSON" | ✅ 2026-10-08, producción: 400. Desde `payment_nave 18.0.1.12.3` se registra como advertencia. §3.39 y §3.40 |
| D3c | Campos faltantes | POST sin `payment_id` | 400 | ✅ 2026-10-08, producción: 400 con la advertencia *"Webhook omitido: faltan campos clave"*. §3.39 |
| D4c | Referencia inexistente | POST con `external_payment_id` inventado | **500 + Nave reintenta en loop**. Evaluar responder 200 ante fallos permanentes | ✅ 2026-10-08, `payment_nave 18.0.1.12.2`: 200 con una línea de información, sin error. Un pago real del POS recibió un solo aviso y Nave no reintentó. §3.39 |
| D5c | Webhook duplicado | Enviar el mismo webhook dos veces | Idempotente: sin doble asiento | ⬜ |
| D6c | Webhook fuera de orden | `APPROVED` y después `PENDING` | La tx no debe retroceder de `done` | ⬜ |
| D7c | Reintentos de Nave | Devolver 500 en el primer intento | Nave reintenta a los 10 s y concilia en el segundo | ⬜ |
| D8c | Pérdida total del webhook | Bajar el sitio > 7h45m y pagar | El cron de conciliación (B9, resuelto) recupera la transacción en la corrida siguiente. Su rama `EXPIRED` ya quedó verificada en A8 | ⬜ |
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
| F2 | Asiento del cobro POS | C2 + cierre de sesión | Asiento correcto en el diario del método de pago | ✅ 2026-10-09: asiento de sesión `POSS/2026/10/0017` cuadrado y un pago por método (`PBNK1/2026/00012` Nave Point $1.623,44, `PBNK1/2026/00013` Nave QR $147). Las 16 facturas quedan pagadas. §3.42 |
| F3 | Trazabilidad | Cualquier cobro | `nave_payment_id` visible en la transacción. Nota: **`provider_reference` queda vacío** — Odoo lo usa para trazabilidad estándar | ⬜ |
| F4 | Total vs monto cobrado | Pedido con lista de precios Nave | Total del pedido == `amount.value` == monto en el panel de Nave | ✅ en lo que pedía: el total del pedido, el `amount.value` y lo que cobró Nave coinciden. ⚠️ Nave acredita el **neto**, y la comisión no queda en ningún asiento. §3.42 |

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

### 5.1 Producto mínimo viable (decidido el 2026-10-08)

Lo primero que se presenta a Nave. Lo que queda afuera no se descarta: se homologa después.

| Entra | Casos | Estado al 2026-10-08 |
|---|---|---|
| Checkout online | A1 a A13, A16 a A18 | ✅ |
| Nave Point con tarjeta | C0 a C9, C12, C16 | ✅ |
| Nave Point con *Código QR* en la terminal | C2 con QR | ✅ 2026-10-08, cobro real con MODO (§3.41) |
| Nave QR fijo | H1 a H8, H10 | ✅ H1, H2, H4 a H8 y H10 (§3.40 y §3.43) |
| Webhook de los pagos del POS | — | ✅ 2026-10-08: responde 200 y Nave no reintenta (§3.39) |
| Seguridad del webhook | E1c a E3c | ⬜ La restricción de host de `payment_check_url` está en el código; falta la prueba |
| Robustez del webhook | D2c a D6c | D2c a D4c ✅; D5c y D6c ⬜ |
| Contabilidad y cierre de caja | F1 a F4, C15 | ✅ C15, F2 y F4 (§3.42). ⚠️ La comisión que Nave descuenta del neto no queda asentada. F1 y F3 ⬜ |
| Calidad | E0.1 a E0.4, E4c | ✅ en cada commit |

| Queda para después | Por qué |
|---|---|
| Links de pago (bloque B) | Fuera del primer alcance |
| Multi-compañía (bloque G) | Fuera del primer alcance. El código ya liga las credenciales a la compañía; falta probarlo |
| Devoluciones por API (A14, A15, B9c, C13, H9, D9c) | Las bloquea el permiso que tiene que dar Nave (consulta 1 de la reunión). Mientras tanto, la devolución se hace desde el panel de Nave |
| Varias cajas con una terminal (C10) | Postergado el 2026-10-08. Una caja sola no puede chocar dos cobros (§3.38) |
| Batería baja (C11) y webhook de baja de intención (C14) | C14 depende de que Nave notifique las intenciones (consulta 3 de la reunión) |

Esto reemplaza, para la primera presentación, los puntos 3 y 5 de los criterios de arriba: el bloque B
y la devolución de punta a punta pasan a la segunda.

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
- **N12** 🟠 **REPLANTEADA (2026-10-07)** — **Probablemente estábamos llamando al endpoint
  equivocado.** La documentación vigente documenta las devoluciones en
  `POST /integrations/payments/{id}/refunds`, un único endpoint que anula o devuelve según el estado
  de liquidación, y no menciona `DELETE /api/payments/{id}`, que es el que usan los módulos. Lo más
  probable es que el 403 de IAM sea el de una ruta vieja que sigue mapeada pero ya no se le habilita
  a integradores nuevos. Detalle del endpoint y sus errores en `docs/nave_codigos_referencia.md` §8.

  **Sondeo en sandbox (2026-10-07), desde la base local con un pago inexistente:**

  | Petición | Respuesta |
  |---|---|
  | `POST /integrations/ruta_que_no_existe_jamas` (control) | 403 *"Invalid key=value pair…"*: ruta no mapeada |
  | `DELETE /api/payments/{id}` | 403 *"…no identity-based policy allows the execute-api:Invoke action"* |
  | `POST /integrations/payments/{id}/refunds`, en `api-sandbox` y en `e3-api` | **el mismo 403 de IAM** |
  | El mismo `POST` con `amount` en el body | el mismo 403 de IAM |

  **El endpoint nuevo existe, y tampoco tenemos permiso.** El token de sandbox trae
  `scope = write.payment_request read.payment read.payment_request`: puede crear y dar de baja
  intenciones y leer pagos, pero **no tiene ningún permiso de escritura sobre pagos**, y una
  devolución lo es. Eso explica el 403 en los dos endpoints.

  **Producción tiene la misma configuración.** Leído en el servidor el mismo día, del token de
  producción (otro `client_id`): `scope = write.payment_request read.payment read.payment_request`.
  El bloqueo es de los dos ambientes.

  **Pedido concreto a Nave:** agregar a nuestro `client_id`, en sandbox y en producción, el permiso
  que habilita `POST /integrations/payments/{id}/refunds`, y confirmar que las devoluciones estén
  habilitadas en el perfil del comercio (si no, la API respondería `REFUND_NOT_ENABLED`). Conviene
  pedir también que confirmen el body de una devolución total, porque el único ejemplo documentado
  lleva sólo `tip_amount`.

  Aunque el permiso llegue, los módulos tienen que migrar al endpoint nuevo: el viejo ya no está
  documentado.

  *Nota original (2026-10-05):* **El endpoint de devolución existe; lo que falta es el
  permiso.** Ya no hay que preguntar si la ruta sigue viva: el sondeo contra sandbox la distingue de
  una inexistente (§3.21). `DELETE /api/payments/{payment_id}` responde *"User is not authorized to
  access this resource"*, el mensaje de IAM que devuelve el gateway cuando la ruta está mapeada pero
  el llamador no tiene permiso, mientras que una ruta inventada devuelve otro mensaje distinto.
  La pregunta a Nave pasa a ser concreta: **habilitar `execute-api:Invoke` del método DELETE sobre
  `/api/payments/{id}` para nuestro `client_id`**. Sigue bloqueando B6 y D5, pero ya no por
  desconocimiento. El endpoint no figura en la documentación vigente (cero ocurrencias de
  `api/payments/` en las cuatro páginas), así que conviene pedir también que lo documenten.
- **N10** ✅ **RESUELTA (2026-09-21)** — **No existe la devolución parcial: es `full_only`.** La
  mención "total o parcial" de `doc_point.md` §7 es un error de la doc. Ver §3.8 para el cambio que
  implica.
- **N11** ✅ **RESUELTA por la doc (2026-09-22)** — El ingreso manual de tarjetas es un **flag del
  comercio**: *"si el ingreso manual de tarjetas se encuentra habilitado, puede completarse el pago
  ingresando datos manuales"*. En desktop se muestra QR; en mobile se redirige a MODO. **A2-A6 son
  ejecutables sólo si lo tenemos habilitado** — falta confirmar si es nuestro caso.
- **N9** ✅ **RESUELTA** — Hay un `pos_id` por dispositivo y por tipo de pago, confirmado por el
  error `INVALID_POS` y por la propia pantalla de puntos de venta. **Nave ya nos había dado el de la
  terminal `L40000978` el 2026-08-14**: `b1c04ade-dec9-4ca0-9fd9-8464c9006764`, distinto del de
  e-commerce que teníamos cargado. Ver §3.5.

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
