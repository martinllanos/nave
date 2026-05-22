# Manual de Configuración y Pruebas - Nave Checkout (Fase 2)

Este manual te guiará paso a paso para configurar el proveedor de pagos **Nave** en tu base de datos de Odoo 18 y realizar tu primera prueba de cobro con una factura real.

---

## 1. Levantar el Servidor de Odoo
Primero, necesitamos arrancar Odoo normalmente (sin los flags de tests para poder usar la interfaz gráfica).
Ejecutá el siguiente comando en tu terminal:

```bash
/home/martin/server/18/odoo/odoo-bin -c /home/martin/server/18/nave/odoo.conf -d nave -p 8069
```
*Asegurate de que no tengas otro servidor corriendo en el puerto 8069.*

---

## 2. Configurar el Proveedor de Pagos en Odoo

1. Ingresá a Odoo desde tu navegador: `http://localhost:8069`
2. Iniciá sesión con tu usuario administrador.
3. Navegá a **Contabilidad > Configuración > Proveedores de Pago** (o *Website > Configuración > Proveedores de Pago* si estás desde el módulo de Sitio Web).
4. Buscá el proveedor llamado **Nave** y hacé clic en él.
5. **Configuración del Entorno:**
   - En la parte superior derecha, cambiá el "Estado" de **Deshabilitado** a **Entorno de Prueba (Test)**. Esto asegurará que todas las llamadas vayan a la API Sandbox (`api-sandbox.ranty.io`).
6. **Pestaña Credenciales:**
   - Completá los campos con tus credenciales de Sandbox proporcionadas por Nave:
     - `Client ID`
     - `Client Secret`
     - `POS ID`
7. **Pestaña Configuración (Opcional pero recomendado):**
   - Acá podés definir el diario contable donde se registrarán los pagos (Ej: *Bank* o *Nave*).
8. **Métodos de Pago:**
   - Odoo 18 requiere que los métodos de pago estén vinculados. Hacé clic en la pestaña **Métodos de Pago**. Deberías ver los métodos disponibles. Asegurate de que estén habilitados.
9. **Publicación:**
   - Arriba de todo (en la barra de botones inteligentes), asegurate de hacer clic en el botón de **Publicado** (tiene que estar en verde) para que los clientes puedan verlo.

---

## 3. Preparar la Base de Datos (Moneda y Cliente)

Nave en su entorno de Sandbox espera procesar operaciones en **Pesos Argentinos (ARS)**.

1. Asegurate de que la compañía principal tenga a **ARS** como moneda principal (*Ajustes > Compañías*).
2. O bien, al crear la factura, asegurate de seleccionar la moneda ARS.
3. Creá o modificá un cliente (*Contactos*). Es importante que el cliente tenga configurado un **CUIT válido** para Argentina (Ejemplo de prueba: `20055361682`), y de ser posible un correo electrónico válido, ya que Nave suele requerir estos datos para procesar la intención de pago.

---

## 4. Prueba 1: Pago desde el Portal del Cliente

1. Navegá a **Ventas** o **Contabilidad** y creá una nueva **Factura (Invoice)** a nombre de tu cliente de prueba.
2. Agregá un producto (Ej: Servicio por $1500) y confirmá la factura.
3. Hacé clic en el botón **Vista Previa (Preview)** o envíale el link al cliente.
4. Odoo te mostrará el portal del cliente con la factura.
5. Hacé clic en el botón **Pagar Ahora (Pay Now)**.
6. En la lista de opciones de pago, debería aparecer **Nave**. Seleccionalo.
7. Al hacer clic en **Pagar**, Odoo generará la intención de pago (Payment Intent) en segundo plano y te **redirigirá al entorno de Sandbox de Nave Checkout**.
8. En la pantalla de Nave, ingresá datos de tarjeta de prueba (Nave te debería haber provisto tarjetas de crédito/débito ficticias para Sandbox) y completá el flujo.
9. Al finalizar, Nave te va a redirigir automáticamente de nuevo a Odoo, donde la factura debería figurar como **En Proceso** o **Pagada** (dependiendo de si el Webhook de Nave ya llegó y se procesó).

---

## 5. Prueba 2: Generar un Link de Pago Manual (Wizard)

Esta es la funcionalidad personalizada que armamos en `payment_nave`.

1. Con la factura anterior (o una nueva ya confirmada), andá a la vista de formulario en el backend (Contabilidad o Ventas).
2. Hacé clic en el botón **Generar Link de Pago (Generate Payment Link)**.
3. Odoo te abrirá el Wizard estándar modificado. Asegurate de seleccionar a **Nave** como proveedor.
4. Hacé clic en generar.
5. Te va a entregar un link (Ej: `https://checkout.ranty.io/link/...`). 
6. Abrí ese link en una pestaña de incógnito para simular ser el cliente. Vas a ver el checkout directo de Nave.

---

## 6. Monitoreo y Troubleshooting (Para Vos como Dev)

Si algo falla o querés ver cómo ocurre la "magia" por detrás:

- **Logs de Terminal**: Mantené a la vista la terminal donde corre Odoo. Vas a ver en tiempo real los mensajes de `[payment_nave]` cuando solicitamos el token, cuando mandamos el payload, y cuando recibimos el Webhook.
- **Transacciones de Pago**: Podés ir a **Contabilidad > Configuración > Transacciones de Pago** (modo desarrollador activado). Ahí se lista cada intento. Si hacés clic, vas a ver si quedó en estado *Borrador*, *Pendiente*, o *Aprobado*, y el campo con el ID real de pago en Nave.

¡Éxitos con la prueba! Avisame si te trabás en la interfaz de Odoo o si Nave devuelve algún error de autenticación con tus credenciales.
