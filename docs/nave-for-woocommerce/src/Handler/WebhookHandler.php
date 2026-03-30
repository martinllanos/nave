<?php
/**
 * Webhook Handler.
 *
 * Registra y procesa el endpoint REST que Nave invoca server-to-server
 * cuando el estado de un pago cambia, independientemente de la navegación
 * del cliente (solución al problema de redirect perdido).
 *
 * SEGURIDAD:
 * - Secret criptográfico de 256 bits por orden, incluido en la notification_url.
 * - Validado con hash_equals() (timing-safe) antes de procesar nada.
 * - El secret se rota en cada nueva intención de pago.
 *
 * FLUJO:
 * 1. NaveApiClient incluye notification_url al crear la intención.
 * 2. Nave hace POST a /wp-json/nave/v1/webhook?order_id=X&secret=Y
 * 3. Este handler valida el secret, hace GET al payment_check_url,
 *    y corre la misma máquina de estados de ReturnHandler.
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

final class WebhookHandler {

    private NaveGateway        $gateway;
    private NaveApiClient      $api_client;
    private OrderStateResolver $resolver;

    public function __construct() {
        $gateways         = WC()->payment_gateways() ? WC()->payment_gateways()->payment_gateways() : [];
        $this->gateway    = $gateways[ NAVE_WC_SLUG ] ?? new NaveGateway();
        $token_manager    = new TokenManager( $this->gateway );
        $this->api_client = new NaveApiClient( $this->gateway, $token_manager );
        $this->resolver   = new OrderStateResolver();
    }

    // ── Secret management ────────────────────────────────────────────────────

    /**
     * Genera y persiste un secret criptográfico de 256 bits para la notification_url.
     * Se llama al crear la intención de pago en NaveApiClient.
     * El secret se rota en cada nueva intención (si el cliente reintenta el checkout).
     */
    public static function generate_webhook_secret( \WC_Order $order ): string {
        $secret = bin2hex( random_bytes( 32 ) );
        $order->update_meta_data( '_nave_webhook_secret', $secret );
        $order->save();
        return $secret;
    }

    // ── REST endpoint ────────────────────────────────────────────────────────

    /**
     * Registra el endpoint REST: POST /wp-json/nave/v1/webhook
     */
    public function register_routes(): void {
        register_rest_route(
            'nave/v1',
            '/webhook',
            [
                'methods'             => \WP_REST_Server::CREATABLE, // POST
                'callback'            => [ $this, 'handle' ],
                'permission_callback' => '__return_true', // Auth manual via secret
            ]
        );
    }

    /**
     * Procesa el POST de Nave.
     *
     * Payload esperado:
     * {
     *   "payment_id": "uuid",
     *   "payment_check_url": "api.ranty.io/ranty-payments/payments/:id",
     *   "external_payment_id": "wc_order_id"
     * }
     */
    public function handle( \WP_REST_Request $request ): \WP_REST_Response {
        // 1. Extraer parámetros de la URL.
        $order_id = absint( $request->get_param( 'order_id' ) );
        $secret   = sanitize_text_field( $request->get_param( 'secret' ) ?? '' );

        if ( ! $order_id || ! $secret ) {
            $this->log( 'Webhook recibido sin order_id o secret.', 'warning' );
            return new \WP_REST_Response( [ 'error' => 'missing_params' ], 400 );
        }

        // 2. Buscar la orden.
        $order = wc_get_order( $order_id );
        if ( ! $order ) {
            $this->log( 'Webhook: orden #' . $order_id . ' no encontrada.', 'error' );
            // Respondemos 200 para evitar reintentos de Nave sobre órdenes inexistentes.
            return new \WP_REST_Response( [ 'error' => 'order_not_found' ], 200 );
        }

        // 3. Validar secret (timing-safe).
        $stored_secret = (string) $order->get_meta( '_nave_webhook_secret' );
        if ( ! $stored_secret || ! hash_equals( $stored_secret, $secret ) ) {
            $this->log( 'Webhook: secret invalido para orden #' . $order_id . '.', 'error' );
            return new \WP_REST_Response( [ 'error' => 'invalid_secret' ], 401 );
        }

        // 4. Validar método de pago.
        if ( $order->get_payment_method() !== NAVE_WC_SLUG ) {
            $this->log( 'Webhook: orden #' . $order_id . ' no es de Nave.', 'warning' );
            return new \WP_REST_Response( [ 'ok' => true ], 200 );
        }

        // 5. Extraer payload del body.
        $body             = $request->get_json_params() ?? [];
        $payment_id       = sanitize_text_field( $body['payment_id'] ?? '' );
        $payment_check_url = sanitize_text_field( $body['payment_check_url'] ?? '' );

        if ( ! $payment_id || ! $payment_check_url ) {
            $this->log( 'Webhook: payload incompleto para orden #' . $order_id . '. Body: ' . wp_json_encode( $body ), 'warning' );
            return new \WP_REST_Response( [ 'error' => 'invalid_payload' ], 400 );
        }

        $this->log( 'Webhook recibido para orden #' . $order_id . ' — payment_id: ' . $payment_id );

        // 6. Marcar que el webhook fue recibido (para que el cron lo salte).
        $order->update_meta_data( '_nave_webhook_received', current_time( 'mysql' ) );
        $order->save();

        // 7. Procesar en background para responder a Nave rápido.
        // Usamos shutdown action para no bloquear la respuesta HTTP.
        add_action( 'shutdown', function() use ( $order, $payment_id, $payment_check_url ) {
            $this->process_webhook( $order, $payment_id, $payment_check_url );
        } );

        return new \WP_REST_Response( [ 'ok' => true ], 200 );
    }

    /**
     * Consulta el estado del payment y corre la máquina de estados.
     * Se ejecuta en shutdown para responder a Nave inmediatamente.
     *
     * El estado del PAYMENT es la fuente de verdad para la orden WC.
     * La intención solo se consulta como metadata informativa.
     */
    private function process_webhook( \WC_Order $order, string $payment_id, string $payment_check_url ): void {
        try {
            // GET al endpoint interno del payment para obtener status y payment_code.
            $payment_data   = $this->api_client->get_payment_internal( $payment_id );
            $payment_status = $payment_data['status']['name'] ?? '';
            $payment_code   = $payment_data['payment_code'] ?? '';

            $this->log( 'Webhook — estado del payment para orden #' . $order->get_id() . ': ' . $payment_status );

            // Guardar datos del payment.
            $order->update_meta_data( '_nave_payment_id', sanitize_text_field( $payment_id ) );
            if ( $payment_status ) {
                $order->update_meta_data( '_nave_payment_status', sanitize_text_field( $payment_status ) );
            }
            if ( $payment_code ) {
                $order->update_meta_data( '_nave_payment_code', sanitize_text_field( $payment_code ) );
            }
            $order->save();

            // Actualizar estado de la intención como metadata informativa (no determina el estado WC).
            $payment_request_id = $order->get_meta( '_nave_payment_request_id' );
            if ( $payment_request_id ) {
                try {
                    $pr_response = $this->api_client->get_payment_request( $payment_request_id );
                    $nave_status = $pr_response['status']['name'] ?? 'PENDING';
                    $order->update_meta_data( '_nave_status', sanitize_text_field( $nave_status ) );
                    $order->save();
                    $this->log( 'Webhook — estado de la intención para orden #' . $order->get_id() . ': ' . $nave_status );
                } catch ( \RuntimeException $e ) {
                    $this->log( 'Webhook — no se pudo consultar payment_request para orden #' . $order->get_id() . ': ' . $e->getMessage(), 'warning' );
                }
            }

            // El estado del PAYMENT determina el estado de la orden WC.
            // Una intención puede tener muchos pagos; lo que importa es el estado
            // del payment concreto que Nave notifica en este webhook.
            $this->resolver->resolve_by_payment_status( $order, $payment_status );

        } catch ( \RuntimeException $e ) {
            $this->log( 'Webhook — error al procesar orden #' . $order->get_id() . ': ' . $e->getMessage(), 'error' );
            $order->add_order_note(
                sprintf(
                    /* translators: %s: Technical error message from the Nave API */
                    __( '⚠️ [Nave] Error al procesar webhook. Detalle técnico: %s', 'nave-for-woocommerce' ),
                    $e->getMessage()
                ),
                false,
                true // Privada
            );
            $order->save();
        }
    }

    private function log( string $message, string $level = 'debug' ): void {
        if ( 'yes' !== $this->gateway->get_option( 'debug' ) ) {
            return;
        }
        wc_get_logger()->log( $level, '[WebhookHandler] ' . $message, [ 'source' => 'nave-for-woocommerce' ] );
    }
}
