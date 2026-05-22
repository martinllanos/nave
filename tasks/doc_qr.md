# QR Interoperable - Cobros Presenciales con QR Físico vía API

Integrá nuestra solución de cobros vía API y permití pagos con QR desde tu negocio de forma simple y segura. Los clientes podrán escanear y pagar usando cualquier billetera virtual o aplicación bancaria.

---

## 1. Requisitos para comenzar
* Solicitar credenciales de sandbox y producción.
* Configurar la `notification_url` (Webhook) en la plataforma Nave para recibir eventos en tiempo real.
* Registrar/crear QRs físicos en la plataforma para obtener los correspondientes `pos_id`.

---

## 2. Autenticación (Obtención de Token)

La autenticación se realiza mediante el cliente Auth0 de Galicia/Naranja X para obtener un token B2B M2M.

### Endpoint de Autenticación
* **Sandbox (Galicia/Naranja X MS):** `POST https://homoservices.apinaranja.com/security-ms/api/security/auth0/b2b/m2ms`
* **Producción:** `POST https://api.ranty.io/security-ms/api/security/auth0/b2b/m2ms` *(o según credenciales de prod)*

### Request Body (JSON)
* `client_id` (String, Obligatorio): Client ID provisto por Nave.
* `client_secret` (String, Obligatorio): Client Secret provisto por Nave.
* `audience` (String, Obligatorio): Siempre `"https://naranja.com/ranty/merchants/api"`

### Response Schema (JSON)
```json
{
  "access_token": "eyJhbGciOiJS...1A",
  "scope": "read:payments write:payments",
  "expires_in": 86400,
  "token_type": "Bearer"
}
```
*Recomendación de integración:* Almacenar en caché el `access_token` y reutilizarlo hasta que falte poco para expirar (basado en `expires_in` segundos).

---

## 3. Crear Intención de Pago (QR Estático / Dinámico)

Para que el QR físico muestre un monto específico a cobrar, se debe registrar una intención de pago asociada al `pos_id` (ID de terminal/caja).

### Endpoint para Crear Intención
* **Sandbox:** `POST https://api-sandbox.ranty.io/api/payment_request/static_qr`
* **Producción:** `POST https://api.ranty.io/api/payment_request/static_qr`

### Headers
* `Authorization: Bearer <access_token>`
* `Content-Type`: application/json

### Atributos del Body (JSON)
* `external_payment_id` (String, Requerido): Identificador del pago en el sistema externo (máximo 36 caracteres).
* `seller.pos_id` (String, Requerido): ID único de la terminal o punto de venta física en Nave.
* `transactions` (Array de Objetos, Requerido): Detalles de la transacción.
  * `qr_amount` (String, Requerido): Tipo de QR. Valor obligatorio: `"close"` (indica monto cerrado).
  * `amount.currency` (String, Requerido): Moneda de pago. Valor obligatorio: `"ARS"`.
  * `amount.value` (String, Requerido): Monto total del cobro. **Debe enviarse siempre como String con exactamente dos decimales** (Ej: `"999.00"`).
  * `products` (Array de Objetos, Requerido): Lista de productos vendidos.
    * `name` (String, Requerido): Nombre del producto o concepto del cobro.
    * `description` (String, Opcional): Descripción detallada.
    * `quantity` (Entero, Requerido): Cantidad del producto.
    * `unit_price.currency` (String, Requerido): `"ARS"`.
    * `unit_price.value` (String, Requerido): Precio unitario con dos decimales.
* `duration_time` (Entero/String, Opcional): Tiempo de expiración de la intención en segundos. Por defecto es 1 semana (604800 segundos).

### Ejemplo de Request Body
```json
{
  "external_payment_id": "OD-2026-05-21-001",
  "seller": {
    "pos_id": "43e0e11c-8d63-457f-b3f9-ff3ba3bfdc4a"
  },
  "transactions": [
    {
      "qr_amount": "close",
      "amount": {
        "currency": "ARS",
        "value": "999.00"
      },
      "products": [
        {
          "name": "Producto de prueba",
          "quantity": 1,
          "description": "Detalle del producto",
          "unit_price": {
            "currency": "ARS",
            "value": "999.00"
          }
        }
      ]
    }
  ],
  "duration_time": 300
}
```

### Ejemplo de Respuesta Exitosa
La respuesta contiene la información de la intención creada y los datos del QR a renderizar en caso necesario, aunque típicamente el cliente escanea el QR físico de la terminal.

---

## 4. Flujo y Notificación de Pagos (Webhook / IPN)

Una vez que el cliente escanea el QR físico desde su billetera preferida y aprueba el pago, Nave envía de manera inmediata una notificación al endpoint registrado como `notification_url`.

### Payload del Webhook (POST JSON)
```json
{
  "payment_id": "3a6b8c9d-1234-5678-abcd-ef0123456789",
  "payment_check_url": "api.ranty.io/ranty-payments/payments/3a6b8c9d-1234-5678-abcd-ef0123456789",
  "external_payment_id": "OD-2026-05-21-001"
}
```

### Respuesta esperada por Nave
El servidor del comercio debe responder inmediatamente con HTTP Status `200 OK`.

### Reintentos en caso de falla
Si el servidor no responde con `200 OK`, Nave reintenta el envío de la notificación hasta 5 veces con intervalos crecientes:
1. Reintento: a los 10 segundos
2. Reintento: a los 70 segundos (1m 10s)
3. Reintento: a los 490 segundos (8m 10s)
4. Reintento: a los 3340 segundos (55m 40s)
5. Reintento: a los 24010 segundos (6h 40m 10s)

---

## 5. Recuperar / Consultar un Pago

Permite obtener los detalles completos de una transacción de pago procesada a partir del `payment_id` recibido en el Webhook.

### Endpoint de Consulta
* **Sandbox:** `GET https://api-sandbox.ranty.io/ranty-payments/payments/{payment_id}`
* **Producción:** `GET https://api.ranty.io/ranty-payments/payments/{payment_id}`

### Ejemplo de Response JSON (Aprobado)
```json
{
  "id": "3a6b8c9d-1234-5678-abcd-ef0123456789",
  "external_payment_id": "OD-2026-05-21-001",
  "creation_date": "2026-05-21T03:53:07Z",
  "updated_date": "2026-05-21T03:53:15Z",
  "status": {
    "name": "APPROVED",
    "reason_code": "transaction_successful",
    "reason_name": "Transaction successful"
  },
  "amount": {
    "currency": "ARS",
    "value": "999.00"
  },
  "transactions": [
    {
      "id": "tx-12345",
      "creation_date": "2026-05-21T03:53:07Z",
      "soft_descriptor": "Nave Galicia",
      "products": [
        {
          "name": "Producto de prueba",
          "quantity": 1,
          "description": "Detalle del producto",
          "unit_price": {
            "currency": "ARS",
            "value": "999.00"
          }
        }
      ]
    }
  ],
  "buyer": {
    "doc_number": "27229641242",
    "doc_type": "CUIT"
  },
  "wallet": {
    "name": "mercado pago"
  }
}
```
*El campo `wallet.name` nos indica exactamente qué billetera virtual usó el cliente final (por ejemplo, `"mercado pago"`, `"modo"`, etc.).*

---

## 6. Consultar Estado de una Intención de Pago (Payment Request)

Permite verificar el estado de la solicitud/intención de pago creada antes de que el pago esté consolidado.

### Endpoint de Consulta
* **Sandbox:** `GET https://api-sandbox.ranty.io/api/payment_requests/{payment_request_id}`
* **Producción:** `GET https://api.ranty.io/api/payment_requests/{payment_request_id}`

### Estados posibles de una Intención (`status.name`):
* `PENDING`: Solicitud creada, sin cobros asociados iniciados todavía.
* `PROCESSED`: Solicitud con un pago en proceso de iniciación.
* `DISABLED`: Solicitud desactivada manualmente antes de recibir pago.
* `SUCCESS_PROCESSED`: Cobro exitoso y consolidado (`APPROVED`).
* `FAILURE_PROCESSED`: El cobro fue rechazado (`REJECTED`).
* `EXPIRED`: La intención de pago superó su `duration_time` y expiró.
* `BLOCKED`: Solicitud bloqueada por motivos de seguridad o fraude.

---

## 7. Cancelar / Desactivar Intención de Pago

Si la intención de pago está activa pero aún no ha sido escaneada ni procesada, puede ser dada de baja inmediatamente.

### Endpoint de Cancelación de Intención
* **Sandbox:** `DELETE https://api-sandbox.ranty.io/api/payment_requests/{payment_request_id}`
* **Producción:** `DELETE https://api.ranty.io/api/payment_requests/{payment_request_id}`

---

## 8. Cancelar / Reembolsar un Pago Completado (Refund)

Permite reversar o realizar la devolución total de un cobro que se encuentre en estado `APPROVED`.

### Endpoint de Reembolso
* **Sandbox:** `DELETE https://api-sandbox.ranty.io/api/payments/{payment_id}`
* **Producción:** `DELETE https://api.ranty.io/api/payments/{payment_id}`

### Response Schema (JSON)
```json
{
  "status": "CANCELLING",
  "message": "Payment 3a6b8c9d-1234-5678-abcd-ef0123456789 pending to cancel"
}
```
*Nota: El estado final del pago transicionará a `CANCELLED` o `REFUNDED` tras completarse asincrónicamente el reverso en el gateway.*

---

## 9. Errores Comunes de la API
* `ERROR_ENCODE_DYNAMIC_QR`: Fallo interno del sistema al intentar codificar la información del QR dinámico.
* `NO_GATEWAYS_AVAILABLE`: No hay gateways disponibles o configurados activos para procesar pagos en este momento.

---

## 10. Escenario de Pruebas y Simulación (Sandbox)

Nave ofrece un endpoint muy potente para simular el escaneo y pago de un QR físico en el entorno Sandbox sin necesidad de apps reales.

### Flujo de Simulación en Sandbox:
1. Obtener un token de acceso B2B.
2. Crear la intención de pago enviando el request de cobro a `POST /api/payment_request/static_qr`. Tomar nota de los datos devueltos del QR físico.
3. Consumir el endpoint de simulación vía GET para procesar el pago:
   ```bash
   curl --location 'https://api-sandbox.ranty.io/instore/external/resolve?data={QR_FIJO}&access_token={ACCESS_TOKEN_FIJO}'
   ```
   * `{QR_FIJO}`: Es el string identificador o datos del código QR asociado al pos_id.
   * `{ACCESS_TOKEN_FIJO}`: El token de acceso M2M obtenido en el paso 1.
4. El sistema procesará el pago automáticamente y disparará el Webhook hacia tu servidor de pruebas, permitiendo una automatización y QA 100% integrales.
