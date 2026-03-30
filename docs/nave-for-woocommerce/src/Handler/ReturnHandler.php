<?php
/**
 * Return Handler.
 *
 * Procesa el callback cuando el usuario vuelve de Nave después del pago.
 *
 * SEGURIDAD implementada:
 * - Token criptográfico de un solo uso (256 bits) en la callback_url
 *   → previene enumeración de órdenes (OWASP API8)
 * - Validación de order_key de WooCommerce
 *   → previene IDOR (un usuario no puede procesar órdenes de terceros)
 * - hash_equals() para comparación timing-safe de tokens
 * - Invalidación del token tras primer uso (one-time use)
 *
 * @package NaveWC\Handler
 */

declare( strict_types=1 );

namespace NaveWC\Handler;

defined( 'ABSPATH' ) || exit;

use NaveWC\Api\NaveApiClient;
use NaveWC\Api\TokenManager;
use NaveWC\Gateway\NaveGateway;
use NaveWC\Resolver\OrderStateResolver;

final class ReturnHandler {

    private NaveGateway        $gateway;
    private NaveApiClient      $api_client;
    private OrderStateResolver $resolver;

    public function __construct() {
        $gateways      = WC()->payment_gateways() ? WC()->payment_gateways()->payment_gateways() : [];
        $this->gateway = $gateways[ NAVE_WC_SLUG ] ?? new NaveGateway();

        $token_manager    = new TokenManager( $this->gateway );
        $this->api_client = new NaveApiClient( $this->gateway, $token_manager );
        $this->resolver   = new OrderStateResolver();
    }

    // ── Generación del token de callback ─────────────────────────────────────

    /**
     * Genera y persiste un token criptográfico de un solo uso para la callback_url.
     * Llamar al momento de crear el payment_request en NaveApiClient.
     *
     * @param \WC_Order $order
     * @return string Token (hex, 64 chars) a incluir en la URL
     */
    public static function generate_callback_token( \WC_Order $order ): string {
        $token = bin2hex( random_bytes( 32 ) ); // 256 bits de entropía
        $order->update_meta_data( '_nave_callback_token', $token );
        $order->save();
        return $token;
    }

    // ── Hook principal ────────────────────────────────────────────────────────

    /**
     * Hook: woocommerce_api_nave_return
     *
     * Parámetros esperados en la URL:
     *   - order_id    (int)    ID de la orden WooCommerce
     *   - order_key   (string) Clave única de WooCommerce (previene IDOR)
     *   - nave_token  (string) Token criptográfico de un solo uso (previene enumeración)
     *
     * phpcs:disable WordPress.Security.NonceVerification.Recommended
     * Nota: Este endpoint es una callback URL pública invocada por Nave (no por un form HTML).
     * No es posible usar nonces de WordPress porque Nave no puede obtener ni enviar un nonce WP.
     * La autenticación se realiza mediante token criptográfico de 256 bits de un solo uso.
     */
    public function handle(): void {
        // phpcs:disable WordPress.Security.NonceVerification.Recommended
        $order_id  = absint( wp_unslash( $_GET['order_id'] ?? 0 ) );
        $order_key = sanitize_text_field( wp_unslash( $_GET['order_key'] ?? '' ) );
        $nav_token = sanitize_text_field( wp_unslash( $_GET['nave_token'] ?? '' ) );
        // phpcs:enable WordPress.Security.NonceVerification.Recommended

        // 1. Parámetros mínimos — sin orden no hay thank you page posible.
        if ( ! $order_id || ! $order_key ) {
            $this->log( 'Callback sin order_id u order_key.', 'warning' );
            wp_safe_redirect( wc_get_page_permalink( 'shop' ) );
            exit;
        }

        // 2. La orden existe.
        $order = wc_get_order( $order_id );
        if ( ! $order ) {
            $this->log( 'Orden #' . $order_id . ' no encontrada.', 'error' );
            wp_safe_redirect( wc_get_page_permalink( 'shop' ) );
            exit;
        }

        // Helper: URL de destino final. A partir de aquí siempre redirigimos aquí.
        $thank_you_url = $order->get_checkout_order_received_url();

        // 3. ANTI-IDOR: validar order_key.
        if ( ! hash_equals( $order->get_order_key(), $order_key ) ) {
            $this->log( 'Order key invalida para orden #' . $order_id . '. Posible IDOR attempt.', 'error' );
            wp_safe_redirect( wc_get_page_permalink( 'shop' ) );
            exit;
        }

        // 4. La orden usa Nave como método de pago.
        if ( $order->get_payment_method() !== NAVE_WC_SLUG ) {
            $this->log( 'Orden #' . $order_id . ' no usa Nave. Ignorando.', 'warning' );
            wp_safe_redirect( $thank_you_url );
            exit;
        }

        // 5. Si la orden ya está en estado final, no reprocesar — ir directo al thank you.
        $current_status = $order->get_meta( '_nave_status' );
        if ( $current_status && $this->resolver->is_final_status( $current_status ) ) {
            $this->log( 'Orden #' . $order_id . ' ya en estado final (' . $current_status . '). Redirigiendo sin reprocesar.' );
            wp_safe_redirect( $thank_you_url );
            exit;
        }

        // 6. PREVENCIÓN DE RACE CONDITION: Mutex atómico con add_option.
        // add_option falla silenciosamente (false) si la clave ya existe gracias al
        // constraint UNIQUE de wp_options — operación atómica a nivel base de datos.
        // A diferencia de get_transient + set_transient (dos queries no atómicas),
        // esto garantiza que solo un proceso puede adquirir el lock simultáneamente.
        $lock_key = 'nave_lock_' . $order_id;
        if ( false === add_option( $lock_key, '1', '', 'no' ) ) {
            // Otro proceso ya tiene el lock — redirigir al thank you sin procesar.
            $this->log( 'Orden #' . $order_id . ' ya esta siendo procesada (Lock atomico activo). Redirigiendo al thank you.', 'warning' );
            wp_safe_redirect( $thank_you_url );
            exit;
        }
        // Lock adquirido. Programar limpieza automática al finalizar el request.
        // También se limpia manualmente al final del proceso exitoso.
        register_shutdown_function( function() use ( $lock_key ) {
            delete_option( $lock_key );
        } );

        // 7. ANTI-ENUMERACIÓN: validar token criptográfico de un solo uso.
        //    Si el token ya fue consumido (second request / back button) → redirigir al thank you.
        $stored_token = (string) $order->get_meta( '_nave_callback_token' );
        if ( ! $stored_token || ! $nav_token || ! hash_equals( $stored_token, $nav_token ) ) {
            delete_option( $lock_key ); // Liberar lock si falla la validación del token.
            if ( ! $stored_token ) {
                // Token ya consumido = segundo intento legítimo (back button, refresh).
                $this->log( 'Token ya consumido para orden #' . $order_id . '. Redirigiendo al thank you.', 'warning' );
                wp_safe_redirect( $thank_you_url );
            } else {
                // Token presente pero no coincide = intento sospechoso.
                $this->log( 'Token invalido para orden #' . $order_id . '. Posible ataque de enumeracion.', 'error' );
                wp_safe_redirect( wc_get_page_permalink( 'shop' ) );
            }
            exit;
        }

        // 8. Invalidar token (one-time use).
        $order->delete_meta_data( '_nave_callback_token' );
        $order->save();

        // Redirect asíncrono: mostrar la thank you page inmediatamente
        // sin bloquear al usuario esperando la respuesta de la API de Nave.
        // El procesamiento real ocurre en shutdown, después de enviar la respuesta HTTP.
        // Esto evita que un timeout de Nave (ej. 5s) degrade la UX del cliente.
        wp_safe_redirect( $thank_you_url );

        // Cerrar el output buffer y enviar la respuesta HTTP al navegador ya.
        if ( function_exists( 'fastcgi_finish_request' ) ) {
            fastcgi_finish_request(); // PHP-FPM: libera la conexión con el cliente.
        } elseif ( ob_get_level() > 0 ) {
            ob_end_flush();
            flush();
        }

        // Procesar el estado de la orden en background, después del redirect.
        $this->process_order( $order );

        delete_option( $lock_key ); // Liberar lock al finalizar el procesamiento.
    }

    /**
     * Consulta el estado real de la orden en Nave y actualiza WooCommerce.
     */
    /**
     * Procesa el callback automático de Nave.
     * Aplica idempotencia: no reprocesa órdenes ya en estado final.
     * Llamado desde handle() (callback URL) y handle_order_action() (dropdown admin).
     */
    public function process_order( \WC_Order $order ): bool {
        $payment_request_id = $order->get_meta( '_nave_payment_request_id' );

        if ( ! $payment_request_id ) {
            $this->log( 'Orden #' . $order->get_id() . ' sin _nave_payment_request_id.', 'error' );
            $order->add_order_note( __( '[Nave] Error: no se encontró payment_request_id.', 'nave-for-woocommerce' ) );
            return false;
        }

        // Idempotencia: no reprocesar estado de WC para órdenes ya en estado final.
        // Para actualización forzada desde admin usar refresh_order_data().
        $current_status = $order->get_meta( '_nave_status' );
        if ( $current_status && $this->resolver->is_final_status( $current_status ) ) {
            $this->log( 'Orden #' . $order->get_id() . ' ya en estado final: ' . $current_status );
            return true;
        }

        return $this->fetch_and_update( $order, $payment_request_id, true );
    }

    /**
     * Refresca todos los datos de Nave para la orden desde el admin.
     * Sin idempotencia — siempre consulta ambas APIs (payment_request + payment).
     * Llamado desde el botón AJAX del meta box y el dropdown de acciones.
     */
    public function refresh_order_data( \WC_Order $order ): bool {
        $payment_request_id = $order->get_meta( '_nave_payment_request_id' );

        if ( ! $payment_request_id ) {
            $this->log( 'Orden #' . $order->get_id() . ' sin _nave_payment_request_id.', 'error' );
            return false;
        }

        $this->log( 'Refresco manual de orden #' . $order->get_id() . ' desde admin.' );
        return $this->fetch_and_update( $order, $payment_request_id, false );
    }

    /**
     * Lógica compartida: consulta payment_request + payment y actualiza metas.
     *
     * El estado del PAYMENT es la fuente de verdad para la orden WC.
     * La intención se consulta para obtener el array de payments y guardar
     * su estado como metadata informativa, pero no determina el estado WC.
     *
     * Fallback: si no hay payments en la intención (ej. expiró antes de que
     * el cliente pagara), se usa el estado de la intención como fallback
     * (EXPIRED → cancelled, DISABLED → cancelled, BLOCKED → cancelled).
     *
     * @param bool $update_wc_status Si true, aplica la transición de estado en WooCommerce.
     *                               En el refresco manual (false) solo se actualizan los metas.
     */
    private function fetch_and_update( \WC_Order $order, string $payment_request_id, bool $update_wc_status ): bool {
        try {
            $response    = $this->api_client->get_payment_request( $payment_request_id );
            $nave_status = $response['status']['name'] ?? 'PENDING';

            $this->log( 'Estado intención para orden #' . $order->get_id() . ': ' . $nave_status );

            // Guardar estado de la intención como metadata informativa.
            $order->update_meta_data( '_nave_status', sanitize_text_field( $nave_status ) );

            // Consultar el ÚLTIMO payment del array — es el más reciente.
            // Un REJECTED puede ser seguido de un APPROVED en un reintento,
            // por lo que siempre procesamos el último estado disponible.
            $payments = array_values( array_filter(
                $response['payment_attempts']['payments'] ?? [],
                fn( $p ) => ! empty( $p['payment_id'] )
            ) );

            $has_payment = false;

            if ( ! empty( $payments ) ) {
                $last_payment = end( $payments );
                $payment_id   = $last_payment['payment_id'];

                try {
                    $payment_data   = $this->api_client->get_payment( $payment_id );
                    $payment_code   = $payment_data['payment_code'] ?? '';
                    $payment_status = $payment_data['status']['name'] ?? '';

                    $order->update_meta_data( '_nave_payment_id', sanitize_text_field( $payment_id ) );
                    if ( $payment_code ) {
                        $order->update_meta_data( '_nave_payment_code', sanitize_text_field( $payment_code ) );
                        $this->log( 'Número de operación para orden #' . $order->get_id() . ': ' . $payment_code );
                    }
                    if ( $payment_status ) {
                        $order->update_meta_data( '_nave_payment_status', sanitize_text_field( $payment_status ) );
                        $this->log( 'Estado pago para orden #' . $order->get_id() . ' (último de ' . count( $payments ) . '): ' . $payment_status );
                        $has_payment = true;
                    }
                } catch ( \RuntimeException $pe ) {
                    $this->log( 'No se pudo obtener datos del payment: ' . $pe->getMessage(), 'warning' );
                    $order->add_order_note(
                        sprintf(
                            /* translators: %s: Mensaje de error */
                            __( '⚠️ [Nave] No se pudo obtener el detalle del pago. Detalle técnico: %s', 'nave-for-woocommerce' ),
                            $pe->getMessage()
                        ),
                        false,
                        true
                    );
                }
            }

            if ( $update_wc_status ) {
                if ( $has_payment ) {
                    // Flujo principal: el estado del PAYMENT determina el estado WC.
                    $this->resolver->resolve_by_payment_status( $order, $payment_status );
                } else {
                    // Fallback: no hay payment (intención expiró, fue bloqueada o deshabilitada
                    // antes de que el cliente generara un pago). Usar estado de la intención.
                    $this->resolver->resolve( $order, $nave_status );
                }
            } else {
                // Refresco manual: no transicionar estado WC, solo agregar notas informativas.
                $this->resolver->add_payment_status_note( $order );
                $this->resolver->add_payment_code_note_if_missing( $order );
                $order->save();
            }

            return true;

        } catch ( \RuntimeException $e ) {
            $this->log( 'Error al consultar orden #' . $order->get_id() . ': ' . $e->getMessage(), 'error' );
            $order->update_status( 'pending' );
            // Nota privada con el error técnico — visible solo para el comercio en Order Notes.
            $order->add_order_note(
                sprintf(
                    /* translators: %s: Mensaje de error de la API de Nave */
                    __( '⚠️ [Nave] Error al consultar el estado del pago en Nave. La orden queda en Pending Payment hasta que se resuelva. Detalle técnico: %s', 'nave-for-woocommerce' ),
                    $e->getMessage()
                ),
                false, // No notificar al cliente
                true   // Nota privada
            );
            $order->save();
            return false;
        }
    }

    private function log( string $message, string $level = 'debug' ): void {
        if ( 'yes' !== $this->gateway->get_option( 'debug' ) ) {
            return;
        }
        wc_get_logger()->log( $level, '[ReturnHandler] ' . $message, [ 'source' => 'nave-for-woocommerce' ] );
    }
}
