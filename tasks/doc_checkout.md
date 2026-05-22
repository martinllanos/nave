# Integración de Checkout con Nave

Integrá nuestra solución de cobros vía API y permití pagos con QR o tarjetas directamente desde tu sitio o app. Vas a tener una experiencia simple y segura para tus clientes.

## ¿Qué necesitás para empezar?
1. **Credenciales de sandbox y producción**: te permiten generar un token de acceso para comunicarte con nuestras APIs.
2. **Utilizar nuestras APIs**: para generar intenciones de pago en tiempo real.
3. **Elegir cómo mostrar el proceso de pago**: podés renderizar un QR, embeber el SDK o redirigir al usuario a nuestro checkout.

## Ciclo de vida de un pago
1. Obtener un `access_token` con nuestro servicio de autenticación.
2. Generar una intención de pago.
3. Redireccionar al usuario al `checkout_url` o renderizar el QR.
4. Recibir notificaciones de estado de pago en tiempo real.

---

## 1. Autenticación

Para generar tus credenciales, necesitamos que nos compartas la siguiente información a través de tu ejecutivo Galicia o escribiendo a `integraciones@navenegocios.com` junto con el código de vinculación obtenido al realizar el flujo de alta en la plataforma Nave (Nave > Integraciones > Tienda Online Propia):
- CUIT del comercio
- Dos URLs de notificación (notification_url): una para sandbox y otra para producción.

### Endpoints
* **Sandbox**: `POST https://homoservices.apinaranja.com/security-ms/api/security/auth0/b2b/m2msPrivate`
* **Producción**: `POST https://services.apinaranja.com/security-ms/api/security/auth0/b2b/m2msPrivate`

### Parámetros del Body (JSON)
* `client_id` (String, Requerido): Identificación del cliente.
* `client_secret` (String, Requerido): Clave privada del cliente.
* `audience` (String, Requerido): `https://naranja.com/ranty/merchants/api`

#### Body de ejemplo:
```json
{
  "client_id": "eGXu7VV...LsXWylDmrE",
  "client_secret": "BAdRFax_McS...JLBTH-n",
  "audience": "https://naranja.com/ranty/merchants/api"
}
```

### Respuesta esperada (JSON)
* `access_token` (String): Token de acceso (Bearer).
* `scope` (String): Permisos habilitados.
* `expires_in` (Number): Tiempo de expiración en segundos.
* `token_type` (String): Tipo de token (ej. "Bearer").

---

## 2. Crear intención de pago

### Endpoints
* **Sandbox**: `POST https://api-sandbox.ranty.io/api/payment_request/ecommerce`
* **Producción**: `POST https://api.ranty.io/api/payment_request/ecommerce`

### Headers
* `Authorization`: `Bearer <token>`
* `Content-Type`: `application/json`

### Parámetros del Body (JSON)
* `external_payment_id` (String, Requerido): Identificador del pago en tu plataforma (máx. 36 caracteres).
* `seller.pos_id` (String, Requerido): ID de la tienda (obtenido desde Nave > Integraciones > Sistema de gestión).
* `transactions` (Array, Requerido): Lista de transacciones.
  * `amount.currency` (String, Requerido): Moneda (ARS).
  * `amount.value` (String, Requerido): Monto total.
  * `products` (Array, Requerido): Lista de productos.
    * `name` (String, Requerido): Nombre.
    * `description` (String, No): Descripción.
    * `quantity` (Number, Requerido): Cantidad.
    * `unit_price.currency` (String, Requerido): Moneda.
    * `unit_price.value` (String, Requerido): Precio unitario.
* `buyer` (Object, No): Datos del cliente.
  * `doc_type` (String, No): Tipo de documento (DNI, etc.).
  * `doc_number` (String, No): Número de documento.
  * `name` (String, No): Nombre del cliente.
  * `user_email` (String, No): Email del cliente.
  * `user_id` (String, No): ID de usuario en tu plataforma.
  * `billing_address` (Object, No): Datos de facturación.
    * `street_1` (String, No): Dirección línea 1.
    * `street_2` (String, No): Dirección línea 2.
    * `city` (String, No): Ciudad.
    * `region` (String, No): Provincia/Región.
    * `country` (String, No): País ("AR").
    * `zipcode` (String, No): Código postal.
* `additional_info.callback_url` (String, No): URL para redirigir al usuario una vez aprobado.
* `duration_time` (String, No): Tiempo de expiración de la intención en segundos (por defecto 1 semana).

#### Body de ejemplo:
```json
{
  "external_payment_id": "order-111",
  "seller": {
    "pos_id": "f71ba756-1d80-4ab3-9f43-5dc247fd6c4a"
  },
  "transactions": [
    {
      "amount": {
        "currency": "ARS",
        "value": "177.00"
      },
      "products": [
        {
          "name": "Nave product",
          "description": "Nave description",
          "quantity": 1,
          "unit_price": {
            "currency": "ARS",
            "value": "177.00"
          }
        }
      ]
    }
  ],
  "buyer": {
    "doc_type": "DNI",
    "doc_number": "XXXXXXXX",
    "name": "User Platform",
    "user_email": "user.platform@platform.com",
    "user_id": "userplatform_id",
    "billing_address": {
      "street_1": "Platform 110",
      "street_2": "N/A",
      "city": "Santa Fe",
      "region": "Santa Fe",
      "country": "AR",
      "zipcode": "3000"
    }
  },
  "additional_info": {
    "callback_url": "https://tuplatform.com/order_status/order-111"
  },
  "duration_time": 3000
}
```

### Respuesta esperada (JSON)
* `id` (String): ID de la intención en Nave.
* `external_payment_id` (String): ID en tu sistema.
* `checkout_url` (String): Link de pago para redirigir.
* `qr_data` (String): Cadena para renderizar el código QR.

---

## 3. Redirección al Checkout y SDK
* **Redirección**: Podés crear un botón de pago y redirigir a la URL recibida en `checkout_url`.
  * *Experiencia*: En desktop muestra QR para escanear y opción de ingreso de tarjetas. En mobile redirige directamente a la APP de MODO o bancarias.
* **SDK Embebido (Client-Side)**: Permite embeber el checkout como un formulario personalizable.
  * **NPM**: `@ranty/ranty-sdk`
  * **CDN**: jsDelivr

---

## 4. Webhooks (Notificación de un pago)
Nave envía un POST a tu `notification_url` cada vez que el pago cambia de estado (ej: PENDING -> APPROVED).

### Body (JSON)
```json
{
  "payment_id": "ID DEL PAGO",
  "payment_check_url": "api.ranty.io/ranty-payments/payments/:id",
  "external_payment_id": "ID SISTEMA EXTERNO"
}
```

### Respuesta esperada
Debes responder con HTTP 200 OK inmediatamente.

### Reintentos si no se recibe 200 OK:
* Intento 1: 10 segundos
* Intento 2: 70 segundos
* Intento 3: 490 segundos
* Intento 4: 3340 segundos
* Intento 5: 24010 segundos

---

## 5. Recuperar un pago (Consultar estado del pago)
Utilizá este endpoint para consultar el estado del pago tras recibir la notificación o vía fallback.

### Endpoints
* **Sandbox**: `GET https://api-sandbox.ranty.io/ranty-payments/payments/{payment_id}`
* **Producción**: `GET https://api.ranty.io/ranty-payments/payments/{payment_id}`

### Headers
* `Authorization`: `Bearer <token>`
* `Content-Type`: `application/json`

### Respuesta de ejemplo (JSON - Aprobado)
```json
{
  "id": "ebac56ab-89f2-4419-941e-670f801d9c7b",
  "status": {
    "name": "APPROVED",
    "reason_code": "transaction_successful"
  },
  "amount": {
    "value": "50.00",
    "currency": "ARS"
  },
  "card_info": {
    "pan": "XXXXXXXXXXXX1234",
    "bin": "XXXXXX",
    "card_brand": "Visa",
    "card_type": "credit",
    "card_last4": "1234",
    "card_holder_name": "Jhon Doe"
  }
}
```

### Estados posibles de un pago:
* `PENDING`: Transacción iniciada, sin resultado final.
* `APPROVED`: Pago aprobado.
* `REJECTED`: Pago rechazado.
* `CANCELLED`: Cancelación manual antes del cierre de lote.
* `REFUNDED`: Devolución total emitida.
* `PURCHASE_REVERSED`: Reversado antes de liquidarse.
* `CHARGEBACK_REVIEW`: Disputa en proceso por contracargo.
* `CHARGED_BACK`: Contracargo confirmado.

---

## 6. Consultar una intención de pago
Permite consultar el estado global de una intención creada mediante su `payment_request_id`.

### Endpoints
* **Sandbox**: `GET https://api-sandbox.ranty.io/api/payment_requests/{payment_request_id}`
* **Producción**: `GET https://api.ranty.io/api/payment_requests/{payment_request_id}`

### Headers
* `Authorization`: `Bearer <token>`
* `Content-Type`: `application/json`

### Estados posibles de la intención:
* `PENDING`: Creada, sin pagos asociados aún.
* `PROCESSED`: Con un pago iniciado.
* `DISABLED`: Desactivada antes de usarse.
* `SUCCESS_PROCESSED`: Pago aprobado de forma exitosa.
* `FAILURE_PROCESSED`: Pago rechazado.
* `EXPIRED`: Vencida.
* `BLOCKED`: Bloqueada por fraude o intentos excedidos.

---

## 7. Cancelar intención de pago
Permite dar de baja una intención activa que aún no fue pagada.

### Endpoints
* **Sandbox**: `DELETE https://api-sandbox.ranty.io/api/payment_requests/{payment_request_id}`
* **Producción**: `DELETE https://api.ranty.io/api/payment_requests/{payment_request_id}`

### Respuesta esperada
```json
{
  "message": "Payment request deleted"
}
```

---

## 8. Cancelación de un pago (Devolución)
Permite cancelar un pago ya aprobado (en estado APPROVED).

### Endpoints
* **Sandbox**: `DELETE https://api-sandbox.ranty.io/api/payments/{payment_id}`
* **Producción**: `DELETE https://api.ranty.io/api/payments/{payment_id}`

### Respuesta esperada
```json
{
  "status": "CANCELLING",
  "message": "Payment {payment_id} pending to cancel"
}
```

---

## 9. Renderizar QR en el frontend
Si decidís renderizar el QR en tu web en vez de redirigir, usá la cadena recibida en `qr_data`. Podés capturar los eventos del modal mediante:
* **Cerrar modal**: `{"type": "PAYMENT_MODAL_RESPONSE", "data": { "success": true, "closeModal": true }}`
* **Aprobado**: `{"type": "PAYMENT_MODAL_RESPONSE", "data": { "success": true }}`
* **Vencido**: `{"type": "PAYMENT_MODAL_RESPONSE", "data": { "success": false, "expiration": true }}`
* **Rechazado**: `{"type": "PAYMENT_MODAL_RESPONSE", "data": { "success": false, "rejected": true }}`

---

## 10. Motivos de rechazo más frecuentes
* `denied`: Error con el proveedor de la tarjeta. Inténtalo de nuevo.
* `no_amount_available`: La tarjeta no tiene fondos suficientes.
* `account_identity_validation_error`: La información de la tarjeta no es válida.
* `expired_card_invalid_expiry_date`: La fecha de vencimiento no es válida.
* `denied_hold_card`: Tu banco rechazó la operación.
* `invalid_merchant`, `system_error`, `gateway_timeout`: Error interno o con el proveedor.
* `gateway_not_available`: Error interno o con el proveedor.

---

## 11. Tarjetas de prueba (Naranja / Visa)
* **Naranja crédito** (APPROVED): `5895 6248 4026 3355` | Venc: `04/40` | CVV: `928`
* **Naranja crédito** (REJECTED): `5895 6248 9347 1379` | Venc: `07/40` | CVV: `374`
* **Naranja crédito** (REJECTED): `5895 6134 3478 9277` | Venc: `04/40` | CVV: `990`
* **Visa crédito (1 cuota)** (APPROVED): `4025 2200 0000 0139` | Venc: Cualquiera | CVV: Cualquiera
* **Visa crédito (6 cuotas)** (APPROVED): `4761 2299 9900 0231` | Venc: `12/31` | CVV: `078`
* **Visa crédito (1 cuota)** (REJECTED): `4025 2200 0000 0127` | Venc: Cualquiera | CVV: Cualquiera
