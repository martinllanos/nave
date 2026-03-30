=== Nave for WooCommerce ===
Contributors: jcabreranave
Tags: woocommerce, payment, gateway, nave, argentina
Requires at least: 6.0
Tested up to: 6.9
Stable tag: 1.0.1
Requires PHP: 8.0
Requires Plugins: woocommerce
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Método de pago por redirección para WooCommerce usando la API de Nave.

== Description ==

El plugin oficial de Nave te permite aceptar pagos en tu tienda WooCommerce de forma rápida y segura.
Tus clientes son redirigidos al checkout de Nave para completar el pago y vuelven automáticamente a tu tienda una vez finalizado.

Para instalarlo no necesitás conocimientos técnicos: seguí el paso a paso de esta guía y empezá a vender hoy mismo.

= ¿Qué podés hacer con Nave for WooCommerce? =

* **Aceptá tarjetas, MODO y QR:** ofrecé Visa, Mastercard, Amex, Cabal, pagos con MODO y códigos QR desde un solo plugin.
* **Probá antes de salir a producción:** usá el entorno Sandbox para testear tu integración sin riesgo.
* **Aprovechá las promos bancarias:** tus clientes pueden acceder a las promociones vigentes de sus bancos al pagar con tarjeta.
* **Número de operación visible:** tanto en "Mi cuenta" como en los emails de confirmación, el comprador recibe su número de operación para cualquier consulta o reclamo.
* **Consultá el estado del pago desde el admin:** verificá en tiempo real el estado de un pago directamente desde la pantalla del pedido, con un botón o desde el menú de acciones.

= Preparado para tu negocio =

* **Compatible con Block Checkout (Gutenberg) y Checkout clásico:** funciona en ambos flujos de compra sin configuración extra.
* **Compatible con HPOS:** soporte completo para WooCommerce High-Performance Order Storage.
* **Seguridad integrada:** token criptográfico de un solo uso por orden, almacenamiento cifrado con AES-256-CBC, enmascaramiento de datos sensibles en logs y renovación automática de tokens OAuth.
* **Procesamiento robusto:** reintentos con backoff exponencial, protección contra doble procesamiento de pagos (idempotencia) y reducción de stock garantizada en una sola operación.
* **Logs integrados:** seguí cada paso del proceso de pago desde WooCommerce → Estado → Logs con el modo debug activado.

¡Impulsá tus ventas con Nave for WooCommerce!

== Installation ==

1. Subí la carpeta `nave-for-woocommerce` a `/wp-content/plugins/`.
2. Activá el plugin desde **Plugins → Plugins instalados**.
3. Andá a **WooCommerce → Ajustes → Pagos → Nave**.
4. Completá tu Client ID, Client Secret y POS ID. Si todavía no tenés tus credenciales, solicitálas escribiendo a **integraciones@navenegocios.com**.
5. Seleccioná el entorno (Sandbox o Producción).
6. Guardá los cambios.

¡Listo! Nave ya aparece como método de pago en tu checkout.

== Frequently Asked Questions ==

= ¿Dónde obtengo mis credenciales de API? =

Escribí a **integraciones@navenegocios.com** para solicitar tu Client ID, Client Secret y POS ID para la integración B2B. El equipo de Nave te va a guiar en el proceso de alta.

= ¿El plugin soporta reembolsos? =

No en la versión actual. Los reembolsos deben procesarse manualmente desde el dashboard de Nave.

= ¿Es compatible con HPOS? =

Sí, es totalmente compatible con WooCommerce High-Performance Order Storage.

= ¿Funciona con el Block Checkout (Gutenberg)? =

Sí, el plugin detecta automáticamente si tu tienda usa el Block Checkout o el Checkout clásico y se adapta sin configuración adicional.

= ¿Qué pasa si el pago expira? =

Si el cliente no completa el pago dentro del tiempo configurado (por defecto 15 minutos), la intención de pago expira y la orden permanece en estado pendiente. Podés ajustar la duración del link de pago desde los ajustes del plugin.

= ¿Puedo verificar el estado de un pago manualmente? =

Sí. Desde la pantalla del pedido en el admin tenés dos formas: un botón en el meta box lateral "Nave - Estado del Pago" o la acción "Consultar estado en Nave" en el menú desplegable de acciones del pedido.

= ¿Es seguro? =

Sí. El plugin utiliza tokens criptográficos de un solo uso para los callbacks, almacenamiento cifrado con AES-256-CBC para los tokens de acceso, y enmascara datos sensibles en los logs de depuración. Ningún dato de tarjeta se almacena en tu servidor.

== Screenshots ==

1. Tus clientes te pagan como quieran.
2. Vendé más con promos.
3. Llevá la información de tus ventas en un solo lugar. 

== Changelog ==

= 1.0.1 =
* Agregada la declaración de servicios externos en el readme (Guideline 6).
* Reemplazados estilos y scripts inline por wp_add_inline_style() y wp_add_inline_script().
* Agregado el header Requires Plugins para la dependencia de WooCommerce.
* Corregido Plugin URI a una URL pública válida.
* Agregados comentarios para traductores en placeholders de i18n.
* Prefijadas variables globales en uninstall.php.
* Uso de $wpdb->prepare() para las consultas de limpieza en base de datos.

= 1.0.0 =
* Lanzamiento inicial.

== Upgrade Notice ==

= 1.0.1 =
Correcciones de cumplimiento para las directrices del directorio de plugins de WordPress.org.

= 1.0.0 =
Lanzamiento inicial.

== External Services ==

Este plugin se conecta a la **plataforma de pagos Nave** para procesar pagos. Nave es un adquirente de pagos que permite a los comercios aceptar pagos con tarjeta (Visa, Mastercard, Amex, Cabal), MODO y QR en Argentina.

= API de Pagos de Nave =

* **Qué es:** la API de procesamiento de pagos de Nave, utilizada para crear intenciones de pago, consultar el estado de un pago y recibir notificaciones de pago.
* **Cuándo se envían datos:**
  * Cuando un cliente inicia un pago en el checkout, el plugin envía los datos del pedido (monto, moneda, nombres de productos, cantidades, precios unitarios) e información del comprador (nombre, email, teléfono, dirección de facturación) para crear una intención de pago.
  * Cuando el administrador de la tienda o un cron automático consulta el estado de un pago existente.
  * Cuando Nave envía una notificación webhook a la tienda para confirmar el estado del pago.
* **URLs del servicio:**
  * Sandbox: `https://api-sandbox.ranty.io/api`
  * Producción: `https://api.ranty.io/api`
  * Pagos Sandbox: `https://punku-sandbox.ranty.io/payments-ms/payments`
  * Pagos Producción: `https://punku.ranty.io/payments-ms/payments`
* **Proveedor del servicio:** Nave (por Galicia) — [https://navenegocios.com](https://navenegocios.com)
* **Términos de servicio:** [https://ecommerce.ranty.io/nave/terms](https://ecommerce.ranty.io/nave/terms)
* **Política de privacidad:** [https://ecommerce.ranty.io/nave/terms](https://ecommerce.ranty.io/nave/terms)

= Servicio de Autenticación de Nave =

* **Qué es:** servicio de autenticación OAuth 2.0 machine-to-machine utilizado para obtener tokens de acceso a la API de Nave.
* **Cuándo se envían datos:** cuando el plugin necesita un nuevo token de acceso (en el primer uso y cuando el token almacenado expira). El plugin envía el Client ID y Client Secret del comercio.
* **URLs del servicio:**
  * Sandbox: `https://homoservices.apinaranja.com/security-ms/api/security/auth0/b2b/m2ms`
  * Producción: `https://services.apinaranja.com/security-ms/api/security/auth0/b2b/m2msPrivate`
* **Proveedor del servicio:** Naranja X — [https://naranjax.com](https://naranjax.com)
* **Términos de servicio:** [https://ecommerce.ranty.io/nave/terms](https://ecommerce.ranty.io/nave/terms)
* **Política de privacidad:** [https://ecommerce.ranty.io/nave/terms](https://ecommerce.ranty.io/nave/terms)

Este plugin no recopila ni envía datos de seguimiento o analítica. Todos los datos transmitidos son estrictamente necesarios para el procesamiento de pagos.