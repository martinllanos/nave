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

Redirect payment gateway for WooCommerce using the Nave acquirer API.

== Description ==

Nave for WooCommerce integrates the Nave payment platform into your WooCommerce store.
Customers are redirected to Nave to complete payment securely, then returned to your store automatically.

Features:

* Supports cards (Visa, Mastercard, Amex, Cabal), MODO and QR payments
* OAuth token caching with auto-renewal
* Retry with exponential backoff (up to 3 attempts)
* Automatic token refresh on 401 responses
* Idempotent order processing (no double-processing of final states)
* Single stock reduction guarantee
* WooCommerce logger integration
* HPOS compatible
* Block Checkout (Gutenberg) compatible
* Manual status check from order admin (dropdown + meta box)
* Cryptographic one-time callback token (prevents order enumeration attacks)
* AES-256-CBC encrypted token storage in transients
* Sensitive data masking in debug logs

== Installation ==

1. Upload the `nave-for-woocommerce` folder to `/wp-content/plugins/`
2. Activate the plugin from **Plugins -> Installed Plugins**
3. Go to **WooCommerce -> Settings -> Payments -> Nave**
4. Enter your Client ID, Client Secret, and POS ID
5. Select the environment (Sandbox or Production)
6. Save changes

== Frequently Asked Questions ==

= Where do I get my API credentials? =

Contact Nave to receive your Client ID, Client Secret and POS ID for B2B integration.

= Does this plugin support refunds? =

Not in the current version. Refunds must be processed manually from the Nave dashboard.

= Is this plugin compatible with HPOS? =

Yes, it is fully compatible with WooCommerce High-Performance Order Storage.

== Changelog ==

= 1.0.1 =
* Added external services disclosure in readme (Guideline 6)
* Replaced inline styles and scripts with wp_add_inline_style() and wp_add_inline_script()
* Added Requires Plugins header for WooCommerce dependency
* Fixed Plugin URI to valid public URL
* Added translators comments for i18n placeholders
* Prefixed global variables in uninstall.php
* Used $wpdb->prepare() for database cleanup queries

= 1.0.0 =
* Initial release

== Upgrade Notice ==

= 1.0.1 =
Compliance fixes for WordPress.org Plugin Directory guidelines.

= 1.0.0 =
Initial release.

== External services ==

This plugin connects to the **Nave payment platform** to process payments. Nave is a payment acquirer that allows merchants to accept card payments (Visa, Mastercard, Amex, Cabal), MODO and QR payments in Argentina.

= Nave Payment API =

* **What it is:** Nave's payment processing API, used to create payment intents, query payment status, and receive payment notifications.
* **When data is sent:**
  * When a customer initiates a payment at checkout, the plugin sends order details (amount, currency, product names, quantities, unit prices) and buyer information (name, email, phone, billing address) to create a payment intent.
  * When the store admin or an automated cron job queries the status of an existing payment.
  * When Nave sends a webhook notification back to the store to confirm payment status.
* **Service URLs:**
  * Sandbox: `https://api-sandbox.ranty.io/api`
  * Production: `https://api.ranty.io/api`
  * Sandbox payments: `https://punku-sandbox.ranty.io/payments-ms/payments`
  * Production payments: `https://punku.ranty.io/payments-ms/payments`
* **Service provider:** Nave (by Naranja X) — [https://navenegocios.com](https://navenegocios.com)
* **Terms of service:** [https://ecommerce.ranty.io/nave/terms](https://ecommerce.ranty.io/nave/terms)
* **Privacy policy:** [https://ecommerce.ranty.io/nave/terms](https://ecommerce.ranty.io/nave/terms)

= Nave Authentication Service =

* **What it is:** OAuth 2.0 machine-to-machine authentication service used to obtain access tokens for the Nave API.
* **When data is sent:** When the plugin needs a new access token (on first use and when the cached token expires). The plugin sends the merchant's Client ID and Client Secret.
* **Service URLs:**
  * Sandbox: `https://homoservices.apinaranja.com/security-ms/api/security/auth0/b2b/m2ms`
  * Production: `https://services.apinaranja.com/security-ms/api/security/auth0/b2b/m2msPrivate`
* **Service provider:** Naranja X — [https://naranjax.com](https://naranjax.com)
* **Terms of service:** [https://ecommerce.ranty.io/nave/terms](https://ecommerce.ranty.io/nave/terms)
* **Privacy policy:** [https://ecommerce.ranty.io/nave/terms](https://ecommerce.ranty.io/nave/terms)

No user tracking or analytics data is collected or sent by this plugin. All data transmitted is strictly necessary for payment processing.
