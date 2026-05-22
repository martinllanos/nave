# Integración de Cobros Presenciales con Nave Point (Smart POS)

Integrá Nave Point en tu comercio y habilitá pagos presenciales con nuestra terminal. Aceptá tarjetas con chip, contactless, NFC y QR. Gestioná múltiples terminales desde un solo lugar.

## ¿Qué necesitás para empezar?
1. **Credenciales de sandbox y producción**: te permiten generar un token de acceso para comunicarse con nuestras APIs.
2. **APIs de Nave**: para generar intenciones de pago, recibir notificaciones y gestionar cancelaciones.
3. **Terminal de prueba**: te enviaremos una terminal física para que pruebes la solución en condiciones reales.

---

## 1. Autenticación
El proceso de autenticación es idéntico al de Checkout.

### Endpoints
* **Sandbox**: `POST https://homoservices.apinaranja.com/security-ms/api/security/auth0/b2b/m2msPrivate`
* **Producción**: `POST https://services.apinaranja.com/security-ms/api/security/auth0/b2b/m2msPrivate`

---

## 2. Crear intención de pago (Nave Point)

### Endpoints
* **Sandbox**: `POST https://e3-api.ranty.io/api/payment_request/smart_pos`
* **Producción**: `POST https://api.ranty.io/api/payment_request/smart_pos`

### Headers
* `Authorization`: `Bearer <token>`
* `Content-Type`: `application/json`

### Parámetros del Body (JSON)
* `external_payment_id` (String, Requerido): Identificador del pago en tu plataforma. Máximo 36 caracteres.
* `seller.pos_id` (String, Requerido): ID de la terminal POS física asignada.
* `transactions` (Array, Requerido): Listado de transacciones asociadas.
  * `amount.currency` (String, Requerido): Moneda del pago (ej. `"ARS"`).
  * `amount.value` (String, Requerido): Monto del pago (ej. `"177.00"`). Indicar con dos decimales.
  * `products` (Array, Requerido): Listado de productos.
    * `name` (String, Requerido): Nombre del producto.
    * `description` (String, Requerido): Descripción del producto.
    * `quantity` (Integer, Requerido): Cantidad.
    * `unit_price.currency` (String, Requerido): Moneda del precio unitario.
    * `unit_price.value` (String, Requerido): Precio unitario.
* `duration_time` (Integer, No): Tiempo de expiración de la intención en segundos en la terminal.

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
  "duration_time": 300
}
```

### Respuesta esperada (JSON)
* `id` (String): ID único de la intención en Nave.
* `external_payment_id` (String): ID de tu plataforma.
* `status`: `"PENDING"`

---

## 3. Notificación de un pago (Webhook)
Una vez que el cliente realiza el pago en la terminal, Nave enviará un webhook POST a tu URL registrada con el siguiente formato:

### Body (JSON)
```json
{
  "payment_id": "9db1b695-8051-4442-90d5-9c9329a97486",
  "payment_check_url": "https://e3-api.ranty.io/ranty-payments/payments/9db1b695-8051-4442-90d5-9c9329a97486",
  "external_payment_id": "1ea685c2-a89a-406e-a366-27abd4c14876"
}
```
*Deberás responder con HTTP `200 OK`*.

---

## 4. Recuperar un pago (smart_pos)
Realizá una petición GET para validar los datos del pago y su estado final.

### Endpoints
* **Sandbox**: `GET https://e3-api.ranty.io/ranty-payments/payments/{payment_id}`
* **Producción**: `GET https://api.ranty.io/ranty-payments/payments/{payment_id}`

### Respuesta de pago aprobado (Ejemplo)
```json
{
  "id": "9db1b695-8051-4442-90d5-9c9329a97486",
  "payment_code": "K88530374",
  "creation_date": "2025-09-30T20:55:17.277Z",
  "updated_date": "2025-09-30T20:55:26.501Z",
  "external_payment_id": "1ea685c2-a89a-406e-a366-27abd4c14876",
  "external_payment_datetime": "2025-09-30T19:55:07.597Z",
  "payment_input": "chip",
  "payment_type": "smart_pos",
  "status": {
    "name": "APPROVED",
    "reason_code": "transaction_successful",
    "reason_name": "Transaction successful"
  },
  "lifecycle_stages": [
    "AUTHORIZATION"
  ],
  "payment_method": {
    "type": "card_payment",
    "data_privacy_type": "emv",
    "pan": "476173******0011",
    "bin": "476173",
    "card_brand": "VISA",
    "installment_plan": {
      "annual_nominal_rate": 0,
      "total_financial_cost": "0.00",
      "installments": 1
    },
    "card_type": "DEBIT",
    "card_last4": "0011",
    "issuer": "BANCO DE GALICIA Y BUENOS AIRES S.A.U."
  }
}
```

---

## 5. Consultar una intención de pago
Permite verificar el estado actual de la intención de pago generada.

### Endpoints
* **Sandbox**: `GET https://e3-api.ranty.io/api/payment_requests/{payment_request_id}`
* **Producción**: `GET https://api.ranty.io/api/payment_requests/{payment_request_id}`

---

## 6. Cancelar una intención de pago (Baja)
Para dar de baja una intención de pago activa en la terminal antes de que sea cobrada.

### Endpoints
* **Sandbox**: `DELETE https://e3-api.ranty.io/api/payment_requests/{payment_request_id}`
* **Producción**: `DELETE https://api.ranty.io/api/payment_requests/{payment_request_id}`

### Body opcional para especificar la razón de cancelación:
```json
{
  "reason": {
    "code": "manual_disabled_by_user",
    "description": "El pago fue cancelado por el usuario dentro de la terminal"
  }
}
```

#### Catálogo de códigos válidos de baja:
* `low_battery`: La terminal objetivo posee batería insuficiente para iniciar el pago (menos de 5%).
* `manual_disabled_by_user`: Cancelado por el usuario dentro de la terminal.
* `disabled_by_user_timeout`: La terminal no pudo ser notificada o venció el tiempo.
* `device_already_on_payment_flow`: La terminal ya está procesando otro pago.
* `disabled_from_saas`: Cancelación desde el SAAS por motivo externo.
* `not_specified`: Sin especificar.

---

## 7. Cancelación de un pago (Devolución)
Para realizar una devolución total o parcial de un pago ya cobrado exitosamente.

### Endpoints
* **Sandbox**: `DELETE https://e3-api.ranty.io/api/payments/{payment_id}`
* **Producción**: `DELETE https://api.ranty.io/api/payments/{payment_id}`

### Respuesta esperada (CANCELLING)
```json
{
  "status": "CANCELLING",
  "message": "Payment {payment_id} pending to cancel"
}
```

---

## 8. Notificación de baja de intención de pago
Una vez ejecutada la baja de la intención se notificará a tu URL registrada:
```json
{
  "payment_request_id": "d91301ef-4c70-4a08-bf7f-0337e4093824",
  "status": "DISABLED",
  "disabled_reason": "low battery",
  "payment_request_check_url": "https://api-sandbox.ranty.io/api/payment_requests/d91301ef-4c70-4a08-bf7f-0337e4093824",
  "external_payment_id": "7a20779f-5d3e-4dc4-9c3f-fb778d12134b"
}
```
