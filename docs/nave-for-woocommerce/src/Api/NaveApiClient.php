<?php
/**
 * Nave API Client.
 *
 * @package NaveWC\Api
 */

declare( strict_types=1 );

namespace NaveWC\Api;

defined( 'ABSPATH' ) || exit;

use NaveWC\Gateway\NaveGateway;
use NaveWC\Handler\ReturnHandler;

final class NaveApiClient {

    private const BASE_URL_SANDBOX = 'https://api-sandbox.ranty.io/api';
    private const BASE_URL_PROD    = 'https://api.ranty.io/api';
    private const PAYMENTS_URL_SANDBOX = 'https://punku-sandbox.ranty.io/payments-ms/payments';
    private const PAYMENTS_URL_PROD    = 'https://punku.ranty.io/payments-ms/payments';

    // Campos PII/sensibles a enmascarar en logs.
    private const SENSITIVE_FIELDS = [
        'access_token', 'token', 'Authorization',
        'user_email', 'email',
        'phone', 'doc_number',
        'client_secret',
        'checkout_url',   // contiene tokens de sesión de Nave
    ];

    private NaveGateway  $gateway;
    private TokenManager $token_manager;

    public function __construct( NaveGateway $gateway, TokenManager $token_manager ) {
        $this->gateway       = $gateway;
        $this->token_manager = $token_manager;
    }

    // ── Métodos públicos ──────────────────────────────────────────────────────

    /**
     * Crea una intención de pago en Nave.
     *
     * @throws \RuntimeException
     */
    public function create_payment_request( \WC_Order $order ): array {
        $url  = $this->base_url() . '/payment_request/ecommerce';
        $body = $this->build_payment_request_body( $order );

        $this->log( 'Creando payment request para orden #' . $order->get_id() );
        $this->log( 'Payload: ' . $this->mask_sensitive( wp_json_encode( $body ) ) );

        $response = $this->post( $url, $body );

        if ( empty( $response['id'] ) || empty( $response['checkout_url'] ) ) {
            throw new \RuntimeException(
                'Respuesta de Nave incompleta (faltan id o checkout_url).'
            );
        }

        return $response;
    }

    /**
     * Consulta el estado actual de un payment_request.
     *
     * @throws \RuntimeException
     */
    public function get_payment_request( string $payment_request_id ): array {
        $url = $this->base_url() . '/payment_requests/' . rawurlencode( $payment_request_id );

        $this->log( 'Consultando estado de payment_request: ' . $payment_request_id );

        $response = $this->get( $url );

        if ( ! isset( $response['status']['name'] ) ) {
            throw new \RuntimeException(
                'Respuesta inesperada al consultar estado (falta status.name).'
            );
        }

        return $response;
    }

    // ── Body builder ──────────────────────────────────────────────────────────

    /**
     * Obtiene los detalles de un pago específico por payment_id.
     * Retorna el payment_code entre otros datos para conciliación.
     *
     * @param string $payment_id UUID del pago (obtenido de payment_attempts.payments[].payment_id)
     * @return array<string,mixed>
     * @throws \RuntimeException
     */
    public function get_payment( string $payment_id ): array {
        $base = 'production' === $this->gateway->get_environment()
            ? self::PAYMENTS_URL_PROD
            : self::PAYMENTS_URL_SANDBOX;

        $url = $base . '/' . rawurlencode( $payment_id );

        $this->log( 'Consultando payment_id: ' . $payment_id );

        $response = $this->get( $url );

        if ( empty( $response ) ) {
            throw new \RuntimeException( 'Respuesta vacía al consultar payment.' );
        }

        return $response;
    }

    /**
     * Obtiene los detalles internos de un pago por payment_id.
     * Usa el endpoint /internal que devuelve payment_code, status completo
     * y datos adicionales de la transacción.
     *
     * @param string $payment_id UUID del pago (recibido en el payload del webhook)
     * @return array<string,mixed>
     * @throws \RuntimeException
     */
    public function get_payment_internal( string $payment_id ): array {
        $base = 'production' === $this->gateway->get_environment()
            ? self::PAYMENTS_URL_PROD
            : self::PAYMENTS_URL_SANDBOX;

        $url = $base . '/' . rawurlencode( $payment_id ) . '/internal';

        $this->log( 'Consultando payment interno: ' . $payment_id );

        $response = $this->get( $url );

        if ( empty( $response ) ) {
            throw new \RuntimeException( 'Respuesta vacía al consultar payment interno.' );
        }

        return $response;
    }

    /**
     * Consulta un payment por URL completa (payment_check_url del webhook).
     * La URL ya viene formada desde Nave, solo agregamos el Authorization header.
     *
     * @param string $url URL completa del payment (ej: api.ranty.io/ranty-payments/payments/:id)
     * @return array<string,mixed>
     * @throws \RuntimeException
     */
    public function get_payment_by_url( string $url ): array {
        // Asegurar que la URL tenga esquema HTTPS.
        if ( ! str_starts_with( $url, 'https://' ) ) {
            $url = 'https://' . ltrim( $url, '/' );
        }

        $this->log( 'Consultando payment por URL: ' . $url );

        $response = $this->get( $url );

        if ( empty( $response ) ) {
            throw new \RuntimeException( 'Respuesta vacía al consultar payment por URL.' );
        }

        return $response;
    }

    private function build_payment_request_body( \WC_Order $order ): array {
        $currency = get_woocommerce_currency();

        // Generar token de un solo uso e incluirlo en la callback_url.
        $callback_token = ReturnHandler::generate_callback_token( $order );
        $callback_url   = add_query_arg(
            [
                'wc-api'     => 'nave_return',
                'order_id'   => $order->get_id(),
                'order_key'  => $order->get_order_key(), // Anti-IDOR: valida propiedad de la orden
                'nave_token' => $callback_token,
            ],
            home_url( '/' )
        );

        // ── Productos ─────────────────────────────────────────────────────────
        $products = [];
        foreach ( $order->get_items() as $item ) {
            /** @var \WC_Order_Item_Product $item */
            $product    = $item->get_product();
            $unit_price = $product
                ? (float) wc_get_price_excluding_tax( $product )
                : round( (float) $item->get_total() / max( 1, (int) $item->get_quantity() ), 2 );

            $products[] = [
                'name'        => sanitize_text_field( $item->get_name() ),
                'description' => $product
                    ? sanitize_text_field( wp_strip_all_tags( $product->get_short_description() ) ?: $item->get_name() )
                    : sanitize_text_field( $item->get_name() ),
                'quantity'    => (int) $item->get_quantity(),
                'unit_price'  => [
                    'currency' => $currency,
                    'value'    => number_format( $unit_price, 2, '.', '' ),
                ],
            ];
        }

        $shipping_total = (float) $order->get_shipping_total();
        if ( $shipping_total > 0 ) {
            $products[] = [
                'name'        => (string) __( 'Envío', 'nave-for-woocommerce' ),
                'description' => (string) __( 'Costo de envío', 'nave-for-woocommerce' ),
                'quantity'    => 1,
                'unit_price'  => [
                    'currency' => $currency,
                    'value'    => number_format( $shipping_total, 2, '.', '' ),
                ],
            ];
        }

        // ── Transaction ───────────────────────────────────────────────────────
        $transactions = [
            [
                'amount'   => [
                    'currency' => $currency,
                    'value'    => number_format( (float) $order->get_total(), 2, '.', '' ),
                ],
                'products' => $products,
            ],
        ];

        // ── Buyer ─────────────────────────────────────────────────────────────
        $phone = sanitize_text_field( $order->get_billing_phone() );
        if ( $phone && ! str_starts_with( $phone, '+' ) ) {
            $phone = '+54' . ltrim( $phone, '0' );
        }

        $buyer = [
            'user_id'         => (string) $order->get_customer_id() ?: 'guest_' . $order->get_id(),
            'session_id'      => (string) ( WC()->session ? WC()->session->get_customer_id() : $order->get_id() ),
            'name'            => sanitize_text_field( trim( $order->get_billing_first_name() . ' ' . $order->get_billing_last_name() ) ),
            'user_email'      => sanitize_email( $order->get_billing_email() ),
            'doc_type'        => 'DNI',
            'doc_number'      => '',
            'phone'           => $phone,
            'billing_address' => [
                'street_1' => sanitize_text_field( $order->get_billing_address_1() ),
                'street_2' => sanitize_text_field( $order->get_billing_address_2() ?: 'N/A' ),
                'city'     => sanitize_text_field( $order->get_billing_city() ),
                'region'   => sanitize_text_field( $order->get_billing_state() ),
                'country'  => sanitize_text_field( $order->get_billing_country() ),
                'zipcode'  => sanitize_text_field( $order->get_billing_postcode() ),
            ],
        ];

        // Generar webhook secret de un solo uso para validar la notification_url.
        $webhook_secret  = \NaveWC\Handler\WebhookHandler::generate_webhook_secret( $order );
        $notification_url = add_query_arg(
            [
                'order_id' => $order->get_id(),
                'secret'   => $webhook_secret,
            ],
            rest_url( 'nave/v1/webhook' )
        );

        return [
            'external_payment_id' => (string) $order->get_id(),
            'seller'              => [ 'pos_id' => sanitize_text_field( $this->gateway->get_pos_id() ) ],
            'transactions'        => $transactions,
            'buyer'               => $buyer,
            'additional_info'     => [
                'callback_url'     => $callback_url,
                'notification_url' => $notification_url,
            ],
            'platform'            => [
                'id'   => 'woocommerce',
                'type' => 'mktplace',
                'data' => [
                    'callback_url'     => $callback_url,
                    'notification_url' => $notification_url,
                ],
            ],
            'duration_time'       => (int) $this->gateway->get_option( 'duration_time', 900 ),
        ];
    }

    // ── HTTP helpers ──────────────────────────────────────────────────────────

    private function post( string $url, array $body ): array {
        return $this->request( 'POST', $url, $body );
    }

    private function get( string $url ): array {
        return $this->request( 'GET', $url );
    }

    private function request( string $method, string $url, array $body = [] ): array {
        $max_retries = 3;
        $attempt     = 0;

        while ( $attempt < $max_retries ) {
            $attempt++;
            $token = $this->token_manager->get_token();

        $args = [
                'method'      => $method,
                'headers'     => [
                    'Authorization' => 'Bearer ' . $token,
                    'Content-Type'  => 'application/json',
                    'Accept'        => 'application/json',
                ],
                'timeout'     => 30,
                'redirection' => 5,
                'sslverify'   => true, // Seguridad: Mitiga ataques MitM
            ];

            if ( ! empty( $body ) ) {
                $args['body'] = wp_json_encode( $body );
            }

            $response    = wp_remote_request( $url, $args );
            $status_code = wp_remote_retrieve_response_code( $response );
            $raw_body    = wp_remote_retrieve_body( $response );

            if ( is_wp_error( $response ) ) {
                $this->log( 'Error de red [intento ' . $attempt . ']: ' . $response->get_error_message(), 'error' );
                if ( $attempt < $max_retries ) {
                    sleep( (int) pow( 2, $attempt ) );
                    continue;
                }
                throw new \RuntimeException( 'Error de red: ' . esc_html( $response->get_error_message() ) );
            }

            if ( $status_code === 401 && $attempt === 1 ) {
                $this->log( 'Token expirado (401), refrescando...', 'warning' );
                $this->token_manager->refresh_token();
                continue;
            }

            // Loggear respuesta con datos sensibles enmascarados.
            $this->log( sprintf( 'Respuesta HTTP %d [intento %d]: %s', $status_code, $attempt, $this->mask_sensitive( $raw_body ) ) );

            $data = json_decode( $raw_body, true );

            if ( $status_code < 200 || $status_code >= 300 ) {
                // En el log de error no incluir raw_body (puede tener tokens).
                $this->log( sprintf( 'Error API [%d] intento %d.', $status_code, $attempt ), 'error' );
                if ( $attempt < $max_retries && $status_code >= 500 ) {
                    sleep( (int) pow( 2, $attempt ) );
                    continue;
                }
                throw new \RuntimeException(
                    sprintf( 'API Nave respondió con HTTP %d.', absint( $status_code ) )
                );
            }

            return is_array( $data ) ? $data : [];
        }

        throw new \RuntimeException( 'Máximo de reintentos alcanzado para ' . esc_url( $url ) );
    }

    // ── Masking de datos sensibles ────────────────────────────────────────────

    /**
     * Enmascara valores de campos sensibles en un string antes de loggearlo.
     *
     * Primera pasada: si es JSON válido, recorre el árbol recursivamente.
     * Segunda pasada (fallback): si el body no es JSON (ej. HTML de error 500,
     * texto plano, volcado de stack de Auth0), aplica regex sobre el string crudo
     * para que credenciales embebidas en mensajes de error no se logueen en claro.
     */
    private function mask_sensitive( string $json ): string {
        $data = json_decode( $json, true );

        if ( is_array( $data ) ) {
            // JSON válido — enmascarar recursivamente por clave.
            return wp_json_encode( $this->mask_array_recursive( $data ) ) ?: $json;
        }

        // Fallback para respuestas no-JSON (HTML, texto plano, errores de proxy).
        // Cubre patrones: "field":"value", field=value, field: value.
        $masked = $json;
        foreach ( self::SENSITIVE_FIELDS as $field ) {
            // Regex sobre string crudo: cubre field=value, field: value, "field":"value".
            $pattern = '/(' . preg_quote( $field, '/' ) . ')([\s:=\"]+)([^\"\s&<>{}\[\],]+)/i';
            $masked  = preg_replace( $pattern, '$1$2***REDACTED***', $masked ) ?? $masked;
        }

        return $masked;
    }

    private function mask_array_recursive( array $data ): array {
        foreach ( $data as $key => $value ) {
            if ( is_array( $value ) ) {
                $data[ $key ] = $this->mask_array_recursive( $value );
            } elseif ( in_array( (string) $key, self::SENSITIVE_FIELDS, true ) ) {
                $data[ $key ] = '***REDACTED***';
            }
        }
        return $data;
    }

    private function base_url(): string {
        return 'production' === $this->gateway->get_environment()
            ? self::BASE_URL_PROD
            : self::BASE_URL_SANDBOX;
    }

    private function log( string $message, string $level = 'debug' ): void {
        if ( 'yes' !== $this->gateway->get_option( 'debug' ) ) {
            return;
        }
        wc_get_logger()->log( $level, '[NaveApiClient] ' . $message, [ 'source' => 'nave-for-woocommerce' ] );
    }
}
