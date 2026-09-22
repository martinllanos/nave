# Documentación oficial actualizada de Nave — relevamiento del 2026-09-22

Fuente (DevPortal de Nave, SPA — no se puede traer con `curl`, hay que abrirla en un navegador):

- https://developer-portal-doc-mfe-website-mfe.ranty.io/nave/online-payments/checkout
- https://developer-portal-doc-mfe-website-mfe.ranty.io/nave/online-payments/payment-link
- https://developer-portal-doc-mfe-website-mfe.ranty.io/nave/in-person-payments/nave-point
- https://developer-portal-doc-mfe-website-mfe.ranty.io/nave/in-person-payments/qr-interoperable

> ⚠️ Los archivos `tasks/doc_checkout.md`, `doc_link.md`, `doc_point.md` y `doc_qr.md` son copias
> **anteriores** a esta versión. Ante cualquier diferencia, mandan las URLs de arriba y este archivo.

---

## 1. 🔴 Confirmado: dos vocabularios de estados (B11)

La documentación ahora publica **ambas tablas por separado y son distintas**. Esto confirma B11 sin
necesidad de probar contra sandbox.

**Estados de una INTENCIÓN** — `GET /api/payment_requests/{payment_request_id}`

| Estado | Descripción |
|---|---|
| `PENDING` | Solicitud creada, sin pagos asociados aún |
| `PROCESSED` | Solicitud con un pago iniciado |
| `DISABLED` | Intención desactivada antes de usarse |
| `SUCCESS_PROCESSED` | **Pago aprobado** |
| `FAILURE_PROCESSED` | **Pago rechazado** |
| `EXPIRED` | Intención vencida |
| `BLOCKED` | Intención bloqueada por fraude o intentos excedidos |

**Estados de un PAGO** — `GET /ranty-payments/payments/{payment_id}`

| Estado | Descripción |
|---|---|
| `PENDING` | Transacción iniciada, sin resultado final |
| `APPROVED` | Pago aprobado |
| `REJECTED` | Pago rechazado |
| `CANCELLED` | Cancelación manual antes del cierre de lote |
| `REFUNDED` | Devolución total emitida |
| `PURCHARSE_REVERSED` | Reversado antes de liquidarse *(sic: así está escrito en la doc)* |
| `CHARGEBACK_REVIEW` | Disputa en proceso por contracargo |
| `CHARGED_BACK` | Contracargo confirmado por la entidad emisora |

`APPROVED` **no existe** en el endpoint de intención. El fix aplicado en `81c02c7` mapea las dos
tablas, así que queda validado contra la fuente.

⚠️ **Errata en la doc de Nave**: en la página de QR, la tabla titulada *"Estados posibles de un pago"*
lista en realidad los estados de la **intención**. La tabla correcta de pagos está en la página de
Nave Point.

## 2. 🟢 B3 resuelto: la intención trae el `payment_id`

La respuesta de `GET /api/payment_requests/{id}` incluye:

```json
"payment_attempts": {
    "attempts": 1,
    "payments": [ { "payment_id": "de759155-0904-4ada-afc2-05dc429d3d90", "status": "APPROVED" } ]
}
```

Ese `payment_id` es el que hace falta para consultar el pago y para devolver. Era el dato que
faltaba: ya no hay que adivinar la forma de la respuesta.

La respuesta también trae `expiration_date`, `amount_type`, `payment_retries_allowed`,
`capture_data.checkout_url` y `capture_data.qr_data`.

## 3. 🔴 N2 resuelto: Nave Point usa OTRO host de sandbox

| Flujo | Sandbox | Producción |
|---|---|---|
| Checkout | `https://api-sandbox.ranty.io` | `https://api.ranty.io` |
| Link de pago | `https://api-sandbox.ranty.io` | `https://api.ranty.io` |
| QR interoperable | `https://api-sandbox.ranty.io` | `https://api.ranty.io` |
| **Nave Point** | **`https://e3-api.ranty.io`** | `https://api.ranty.io` |

**Nuestro código usa `api-sandbox.ranty.io` para todo** (`_nave_get_api_url()`), lo que es incorrecto
para Nave Point. El test `pos_nave/tests/test_pos_nave_payment.py:67`, que espera `e3-api`, **tenía
razón**; el commit `ffb524b` que lo cambió "para arreglar un 404" fue en la dirección equivocada.

Hipótesis del 404 original: ver §4 — con un `pos_id` de otro tipo de pago, la API responde error.

Auth: las cuatro páginas usan `m2msPrivate` en sus cuadros de endpoint (sandbox
`homoservices.apinaranja.com`, producción `services.apinaranja.com`). **N3 resuelto: nuestro código
está bien.** El `m2ms` que aparece en un curl de ejemplo de la página de QR es una inconsistencia de
la propia doc.

## 4. 🔴 N9 resuelto: hay un `pos_id` por punto de venta, y se descarga del panel

Las cuatro páginas repiten la misma instrucción:

> *"Accedé desde la plataforma de Nave a **Integraciones > Sistema de gestión** y descargá el archivo
> con los IDs de los puntos de venta que vas a usar para generar las intenciones de pago"*

Para dar de alta QR físicos: **Nave > Negocios > Agregar medios de cobro > QR**.

Y existe un error específico que lo confirma:

```json
{ "code": "409", "message": "INVALID_POS", "detail": "Given POS is for a different payment type" }
```

> *"Cuando el payment type definido en el onboarding del POS difiere del PR que se está intentando
> generar. Se debe chequear el POS."*

Es decir: **cada `pos_id` está registrado para un tipo de pago concreto**. Usar el `pos_id` de la
tienda online para `smart_pos` da error. Esto valida el hallazgo de §3.5 del plan.

**Acción inmediata**: descargar ese archivo desde el panel. Puede destrabar el `pos_id` sin esperar
la respuesta al correo.

## 5. 🔴 N12 (NUEVO): el endpoint de devolución desapareció de la documentación

Buscando `api/payments/` en las cuatro páginas: **cero ocurrencias**. El único `DELETE` documentado
es `/api/payment_requests/{id}`, que cancela una **intención**, no devuelve un **pago**.

La documentación anterior sí lo tenía (`doc_checkout.md` §8, `doc_point.md` §7, `doc_qr.md` §8) como
`DELETE {api-base}/api/payments/{payment_id}` → `CANCELLING`. **Nuestro código lo usa**
(`payment_transaction.py:322`, `pos_payment_method.py:239`).

Los estados `REFUNDED` y `CANCELLED` siguen existiendo en la tabla de pagos, así que la devolución
existe como concepto. Lo que no está documentado es cómo dispararla por API.

**Impacto en D5**: el criterio acordado fue *"si está en la documentación, tiene que entrar"*. En la
documentación **actualizada**, no está. Hay que preguntarle a Nave (N12) antes de invertir en B6.

## 6. 🟢 N11 resuelto: el ingreso manual de tarjetas es un flag del comercio

> *"En **desktop** se muestra un QR para escanear con billetera virtual o banco. **Si el ingreso
> manual de tarjetas se encuentra habilitado**, puede completarse el pago ingresando datos manuales.
> En **mobile** se redirige automáticamente a MODO."*

O sea que los casos A2-A6 son ejecutables **sólo si el comercio tiene habilitado el ingreso manual**.
Hay que confirmar si lo tenemos. Si no, se paga escaneando con billetera, que es exactamente lo que
pasó en la transacción aprobada del 2026-08-11.

**Tarjetas de prueba (7, una más que en nuestra copia)**

| Marca | Número | Venc | CVV | Estado |
|---|---|---|---|---|
| Naranja crédito | 5895 6248 4026 3355 | 04/40 | 928 | APPROVED |
| Naranja crédito | 5895 6248 9347 1379 | 07/40 | 374 | REJECTED |
| Naranja crédito | 5895 6134 3478 9277 | 04/40 | 990 | REJECTED |
| Visa crédito (1 cuota) | 4025 2200 0000 0139 | Cualquiera | Cualquiera | APPROVED |
| Visa crédito (6 cuotas) | 4761 2299 9900 0231 | 12/31 | 078 | APPROVED |
| Visa crédito (1 cuota) | 4025 2200 0000 0127 | Cualquiera | Cualquiera | REJECTED |
| **Visa crédito (1 cuota)** | **4025 2200 0000 1040** | Cualquiera | Cualquiera | **REJECTED** |

## 7. 🟢 NUEVO: simulador PCT de pago para QR

Además del simulador web, la doc de QR publica un simulador que paga **nuestra propia intención**:

```bash
curl --location --request PUT 'https://api-sandbox.ranty.io/qrtools/transfer_payment/simulation/payment' \
  --header 'Content-Type: application/json' \
  --data '{ "payment_request": "<nuestro payment_request_id>",
            "config": { "paymentAmount": "165.00", "gateway": "nxranty" } }'
```

`gateway` acepta `nxranty` o `coelsa`; si uno falla, probar el otro.

Esto es **mejor que el simulador web** para el bloque H: valida el payload que arma Odoo, no sólo la
mitad entrante. Homologación de QR end-to-end sin hardware y sin billetera.

## 8. 🟠 NUEVO: cancelar una intención puede no aplicar a Nave Point

El error de la cancelación dice:

> `payment_request_delete_failed`: *"The payment request could not be deleted. It does not belong to
> a **payment_link, dynamic_qr, static_qr**. Or, it does not have status: PENDING, FAILURE_PROCESSED,
> PROCESSING"*

**`smart_pos` no figura en esa lista.** Si es literal, `nave_cancel_payment_intent` no puede cancelar
un cobro de terminal — justo el caso C4. Contradice que la página de Nave Point documente el endpoint
de cancelación con su catálogo de códigos de baja. A verificar contra sandbox.

Otros errores documentados: `payment_request_is_disabled`, `not_found`, `CLIENT_VALIDATION_FAILED`
(404), `INVALID_POS` (409), `NO_GATEWAYS_AVAILABLE` (409), `PAYMENT_TYPE_IS_NOT_OPERATIVE` (503),
`APPLICATION_ERROR_SERVICE` (404), `INTERNAL_SERVER_ERROR` (500), `ERROR_ENCODE_DYNAMIC_QR` (500).

## 9. 🟠 NUEVO: `buyer` es opcional

En link de pago, **todos** los campos de `buyer` figuran como no requeridos. Nuestro código siempre
arma un comprador y rellena con `'00000000'`, `'correo@temporal.com'`, `'S/D'`, `'0000'`
(`payment_transaction.py:196-215`). Se puede omitir el bloque cuando el partner está incompleto, en
vez de mandar datos falsos a Nave.

`additional_info.callback_url`: *"URL a la que el cliente es redirigido una vez aprobado el pago, ya
sea automáticamente a los 20 segundos o al presionar el botón 'Volver a la tienda'"*. El wizard del
link **no lo manda** (B7c) — ahora sabemos exactamente qué se pierde.

## 10. Otras confirmaciones

- `products.description` es **requerido** en Nave Point y en QR.
- `duration_time` por defecto: **1 semana** en los cuatro flujos.
- `external_payment_id`: máximo 36 caracteres, en los cuatro flujos.
- Reintentos de webhook: 10 s, 70 s, 490 s, 3340 s, 24010 s. Sin cambios.
- Payload del webhook: `payment_id`, `payment_check_url`, `external_payment_id`. **Sin firma.**
- El pago devuelve `payment_request_id`, que permite volver de pago → intención.
- `seller.pos_id` es **requerido también en link de pago y checkout**.
