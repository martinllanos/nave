# Integración de Link de Pago con Nave

Permití a tus clientes pagar a través de links de pago generados dinámicamente mediante nuestra API. Los clientes podrán realizar pagos con QR o tarjetas de crédito y débito.

## ¿Qué necesitás para empezar?
1. **Credenciales de sandbox y producción**: te permiten generar un token de acceso para comunicarte con nuestras APIs.
2. **Utilizar nuestras APIs**: para generar links de pago en tiempo real.

---

## 1. Autenticación
El proceso de autenticación es idéntico al de Checkout.

### Endpoints
* **Sandbox**: `POST https://homoservices.apinaranja.com/security-ms/api/security/auth0/b2b/m2msPrivate`
* **Producción**: `POST https://services.apinaranja.com/security-ms/api/security/auth0/b2b/m2msPrivate`

---

## 2. Crear intención de pago (Link de pago)

### Endpoints
* **Sandbox**: `POST https://api-sandbox.ranty.io/api/payment_request/payment_link`
* **Producción**: `POST https://api.ranty.io/api/payment_request/payment_link`

### Headers
* `Authorization`: `Bearer <token>`
* `Content-Type`: `application/json`

### Parámetros del Body (JSON)
*(Idénticos a Checkout. Ver doc_checkout.md para la descripción completa de cada parámetro)*
* `external_payment_id` (String, Requerido)
* `seller.pos_id` (String, Requerido)
* `transactions` (Array, Requerido)
  * `amount.currency` (String, Requerido)
  * `amount.value` (String, Requerido)
  * `products` (Array, Requerido)
* `buyer` (Object, No)
* `additional_info.callback_url` (String, No)
* `duration_time` (String, No)

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
* `checkout_url` (String): Link de pago para compartir con el cliente.
* `qr_data` (String): Cadena para renderizar el código QR.

---

## 3. Notificación, Recuperación, Estados y Cancelación
Todos los flujos subsiguientes son idénticos a los de Checkout (ver `doc_checkout.md`):
* **Webhooks / Notificaciones**: POST enviado a tu URL con reintentos.
* **Recuperar un pago**: GET `/ranty-payments/payments/{payment_id}`.
* **Estados del pago**: PENDING, APPROVED, REJECTED, CANCELLED, REFUNDED, etc.
* **Consultar intención**: GET `/api/payment_requests/{payment_request_id}`.
* **Cancelar intención**: DELETE `/api/payment_requests/{payment_request_id}`.
* **Devolución**: DELETE `/api/payments/{payment_id}`.
* **Tarjetas de prueba**: las mismas tarjetas de prueba de Naranja y Visa aplican para el flujo del Link de Pago.
