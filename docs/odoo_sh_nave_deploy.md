# Despliegue Odoo.sh — `payment_nave` (rama `18.0-dev-mat`)

Guía para el primer test en Odoo.sh del módulo **payment_nave** únicamente.

## Rama de trabajo

| Rama | Uso |
|------|-----|
| `18.0-dev` | Desarrollo compartido del equipo |
| **`18.0-dev-mat`** | Aportes de Matías — fixes y homologación online Nave |

Conectar el entorno staging de Odoo.sh a **`18.0-dev-mat`**.

## Módulos a instalar

- **Instalar:** `payment_nave` (y dependencias automáticas: `payment`, `account`, `sale`, `mail`, `account_payment` vía `sale`).
- **No instalar en esta fase:** `point_of_sale` (evita auto-install de `pos_nave`), `sale_nave_simulator`.

## Configuración en Nave / Galicia

Registrar en la plataforma Nave (sandbox) la URL de notificación:

```text
https://<tu-proyecto>.odoo.com/payment/nave/webhook
```

Requisitos (ver `tasks/doc_checkout.md`):

- CUIT del comercio
- Credenciales sandbox: Client ID, Client Secret, POS ID
- Código de vinculación desde **Nave > Integraciones > Tienda Online Propia**

## Configuración en Odoo

1. **Contabilidad > Configuración > Proveedores de Pago > Nave**
2. Estado: **Entorno de prueba (Test)**
3. Credenciales: Client ID, Client Secret, POS ID
4. Publicar el proveedor
5. Moneda compañía: **ARS**
6. Cliente de prueba con **CUIT** válido y email

## URLs del módulo

| Ruta | Uso |
|------|-----|
| `/payment/nave/webhook` | Notificaciones S2S de Nave (POST JSON) |
| `/payment/nave/return` | Retorno del cliente tras checkout (GET/POST) |

## Prueba 1 — Portal Pay Now (hito 1)

1. Crear factura de cliente en ARS y publicarla.
2. Vista previa del portal → **Pagar ahora** → seleccionar **Nave**.
3. Completar pago en sandbox Nave.
4. Verificar en Odoo: **Contabilidad > Transacciones de pago** → estado **Autorizado** (`done`).
5. Revisar logs del servidor si falla: buscar `payment_nave` y `Notification received from Nave`.

## Prueba 2 — Wizard link (opcional tras hito 1)

1. Factura confirmada → **Generar Link de Pago**.
2. El wizard crea una `payment.transaction` con la misma referencia que Nave.
3. Al pagar el link, el webhook debe conciliar la transacción en Odoo.

## Hitos siguientes (fuera de `18.0-dev-mat` actual)

- **Hito 2:** `pos_nave` alineado a `tasks/doc_point.md`
- **Hito 3:** `sale_nave_simulator` — motor de precios
