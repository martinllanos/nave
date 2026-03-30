<?php
/**
 * Nave Payment Gateway.
 *
 * @package NaveWC\Gateway
 */

declare( strict_types=1 );

namespace NaveWC\Gateway;

defined( 'ABSPATH' ) || exit;

use NaveWC\Api\NaveApiClient;
use NaveWC\Api\TokenManager;

if ( ! class_exists( 'WC_Payment_Gateway' ) ) {
    return;
}

final class NaveGateway extends \WC_Payment_Gateway {

    public function __construct() {
        $this->id                 = NAVE_WC_SLUG;
        $this->method_title       = __( 'Nave', 'nave-for-woocommerce' );
        $this->method_description = __( 'Pago por redirección usando Nave.', 'nave-for-woocommerce' );
        $this->has_fields         = true;
        $this->supports           = [ 'products' ];
        $this->icon               = NAVE_WC_URL . 'assets/images/nave-logo.svg';

        $this->init_form_fields();
        $this->init_settings();

        $this->title       = $this->get_option( 'title', __( 'Pagar con Nave', 'nave-for-woocommerce' ) );
        $this->description = $this->get_option( 'description', '' );
        $this->enabled     = $this->get_option( 'enabled', 'no' );

        if ( ! in_array( $this->enabled, [ 'yes', 'no' ], true ) ) {
            $this->enabled = filter_var( $this->enabled, FILTER_VALIDATE_BOOLEAN ) ? 'yes' : 'no';
        }

        add_action( 'woocommerce_update_options_payment_gateways_' . $this->id, [ $this, 'process_admin_options' ] );
        add_action( 'wp_enqueue_scripts', [ $this, 'enqueue_frontend_assets' ] );
        add_filter( 'woocommerce_gateway_icon', [ $this, 'filter_icon_html' ], 10, 2 );
    }

    // ── Assets ───────────────────────────────────────────────────────────────

    public function enqueue_frontend_assets(): void {
        if ( ! is_checkout() ) {
            return;
        }
        wp_enqueue_style(
            'nave-checkout',
            NAVE_WC_URL . 'assets/css/nave-checkout.css',
            [],
            NAVE_WC_VERSION
        );
    }

    // ── Icon ─────────────────────────────────────────────────────────────────

    public function filter_icon_html( string $icon_html, string $gateway_id ): string {
        if ( $gateway_id !== $this->id ) {
            return $icon_html;
        }
        $base  = NAVE_WC_URL . 'assets/images/cards/';
        $cards = [ 'visa', 'mastercard', 'amex', 'cabal', 'modo', 'qr' ];
        $icons = '';
        foreach ( $cards as $card ) {
            $icons .= sprintf(
                '<img src="%s" alt="%s" style="height:20px;width:auto;vertical-align:middle;margin-left:4px;border-radius:3px;" />',
                esc_url( $base . $card . '.svg' ),
                esc_attr( strtoupper( $card ) )
            );
        }
        return $icons;
    }

    public function get_icon(): string {
        // Iconos generados por filter_icon_html() via el filtro woocommerce_gateway_icon.
        // No duplicar aquí: parent::get_icon() ya aplica ese filtro.
        return parent::get_icon();
    }

    // ── Payment fields ───────────────────────────────────────────────────────

    /**
     * Renderiza el bloque que aparece debajo de "Pagar con Nave" en el checkout.
     */
    public function payment_fields(): void {
        wc_get_template(
            'checkout/payment-fields.php',
            [
                'logo_url'    => NAVE_WC_URL . 'assets/images/nave-logo.svg',
                'description' => $this->description,
                'is_sandbox'  => $this->get_environment() === 'sandbox',
            ],
            '',
            NAVE_WC_PATH . 'templates/'
        );
    }

    // ── Admin ────────────────────────────────────────────────────────────────

    public function init_form_fields(): void {
        $this->form_fields = [
            'enabled' => [
                'title'   => __( 'Habilitar / Deshabilitar', 'nave-for-woocommerce' ),
                'type'    => 'checkbox',
                'label'   => __( 'Habilitar Nave como método de pago', 'nave-for-woocommerce' ),
                'default' => 'no',
            ],
            'title' => [
                'title'       => __( 'Título', 'nave-for-woocommerce' ),
                'type'        => 'text',
                'default'     => __( 'Pagá con tarjetas, MODO o QR', 'nave-for-woocommerce' ),
                'desc_tip'    => true,
                'description' => __( 'Nombre visible en el checkout del cliente.', 'nave-for-woocommerce' ),
            ],
            'description' => [
                'title'   => __( 'Descripción', 'nave-for-woocommerce' ),
                'type'    => 'textarea',
                'default' => __( '¡Aprovechá las promos de tu banco! Pagá con MODO, QR o tus Tarjetas de forma rápida y segura a través de Nave.', 'nave-for-woocommerce' ),
            ],
            'environment' => [
                'title'   => __( 'Entorno', 'nave-for-woocommerce' ),
                'type'    => 'select',
                'options' => [
                    'sandbox'    => __( 'Sandbox (pruebas)', 'nave-for-woocommerce' ),
                    'production' => __( 'Producción', 'nave-for-woocommerce' ),
                ],
                'default' => 'sandbox',
            ],
            'client_id' => [
                'title'       => __( 'Client ID', 'nave-for-woocommerce' ),
                'type'        => 'text',
                'default'     => '',
                'desc_tip'    => true,
                'description' => __( 'Tu Client ID de Nave B2B.', 'nave-for-woocommerce' ),
            ],
            'client_secret' => [
                'title'       => __( 'Client Secret', 'nave-for-woocommerce' ),
                'type'        => 'password',
                'default'     => '',
                'desc_tip'    => true,
                'description' => __( 'Tu Client Secret de Nave B2B.', 'nave-for-woocommerce' ),
            ],
            'pos_id' => [
                'title'       => __( 'POS ID', 'nave-for-woocommerce' ),
                'type'        => 'text',
                'default'     => '',
                'desc_tip'    => true,
                'description' => __( 'Identificador del punto de venta asignado por Nave.', 'nave-for-woocommerce' ),
            ],
            'duration_time' => [
                'title'             => __( 'Duración del pago (segundos)', 'nave-for-woocommerce' ),
                'type'              => 'number',
                'default'           => '900',
                'desc_tip'          => true,
                'description'       => __( 'Tiempo en segundos que el link de pago estará vigente. Default: 900 (15 min).', 'nave-for-woocommerce' ),
                'custom_attributes' => [ 'min' => '60', 'step' => '60' ],
            ],
            'debug' => [
                'title'   => __( 'Modo Debug', 'nave-for-woocommerce' ),
                'type'    => 'checkbox',
                'label'   => __( 'Activar logs en WooCommerce -> Estado -> Logs', 'nave-for-woocommerce' ),
                'default' => 'no',
            ],
        ];
    }

    public function is_available(): bool {
        if ( 'yes' !== $this->enabled ) {
            return false;
        }
        if ( empty( $this->get_client_id() ) || empty( $this->get_client_secret() ) || empty( $this->get_pos_id() ) ) {
            return false;
        }
        return true;
    }

    public function is_valid_for_use(): bool {
        return true;
    }

    public function admin_options(): void {
        wp_enqueue_style( 'nave-admin-header', false );
        wp_add_inline_style( 'nave-admin-header',
            '.nave-admin-header{display:flex;align-items:center;gap:14px;padding:16px 20px;background:#faf9ff;border:1px solid #D4AAFF;border-radius:10px;margin-bottom:20px;}'
            . '.nave-admin-logo{height:32px;width:auto;}'
            . '.nave-admin-header-text strong{display:block;font-size:15px;color:#1A1A1A;}'
            . '.nave-admin-header-text span{font-size:13px;color:#6B7280;}'
        );

        echo '<div class="nave-admin-header">
            <img src="' . esc_url( NAVE_WC_URL . 'assets/images/nave-logo.svg' ) . '" alt="Nave" class="nave-admin-logo" />
            <div class="nave-admin-header-text">
                <strong>Nave for WooCommerce</strong>
                <span>' . esc_html__( 'Método de pago por redirección via Nave', 'nave-for-woocommerce' ) . '</span>
            </div>
        </div>';

        if ( empty( $this->get_client_id() ) || empty( $this->get_client_secret() ) || empty( $this->get_pos_id() ) ) {
            echo '<div class="notice notice-warning inline"><p><strong>Nave:</strong> '
                . esc_html__( 'Completa Client ID, Client Secret y POS ID para que el método aparezca en el checkout.', 'nave-for-woocommerce' )
                . '</p></div>';
        }

        parent::admin_options();
    }

    // ── Process payment ──────────────────────────────────────────────────────

    public function process_payment( $order_id ): array {
        $order = wc_get_order( $order_id );

        if ( ! $order ) {
            wc_add_notice( __( 'Pedido no encontrado. Intentá de nuevo.', 'nave-for-woocommerce' ), 'error' );
            return [ 'result' => 'failure' ];
        }

        $order->update_status( 'pending', __( '[Nave] Iniciando proceso de pago.', 'nave-for-woocommerce' ) );

        try {
            $token_manager   = new TokenManager( $this );
            $api_client      = new NaveApiClient( $this, $token_manager );
            $payment_request = $api_client->create_payment_request( $order );

            $order->update_meta_data( '_nave_payment_request_id', sanitize_text_field( $payment_request['id'] ) );
            $order->update_meta_data( '_nave_checkout_url',        esc_url_raw( $payment_request['checkout_url'] ) );
            $order->update_meta_data( '_nave_external_payment_id', sanitize_text_field( $payment_request['external_payment_id'] ?? (string) $order_id ) );
            $order->update_meta_data( '_nave_qr_data',             sanitize_text_field( $payment_request['qr_data'] ?? '' ) );
            $order->update_meta_data( '_nave_status',              'created' );
            $order->save();

            WC()->cart->empty_cart();
            $this->log( 'Payment request creado para orden #' . $order_id . '. ID: ' . $payment_request['id'] );

            return [ 'result' => 'success', 'redirect' => $payment_request['checkout_url'] ];

        } catch ( \RuntimeException $e ) {
            $this->log( 'Error en process_payment para orden #' . $order_id . ': ' . $e->getMessage(), 'error' );
            // Usar 'pending' en lugar de 'failed' para evitar el email automático de WC.
            $order->update_status( 'pending' );
            // Nota privada con el error técnico — visible solo para el comercio en Order Notes.
            $order->add_order_note(
                sprintf(
                    /* translators: %s: Mensaje de error de la API de Nave */
                    __( '⚠️ [Nave] Error al crear la intención de pago. El cliente ve el checkout con un mensaje de error genérico. Detalle técnico: %s', 'nave-for-woocommerce' ),
                    $e->getMessage()
                ),
                false, // No notificar al cliente
                true   // Nota privada
            );
            $order->save();
            wc_add_notice( __( 'Ocurrió un error al iniciar el pago con Nave. Por favor, intentá de nuevo.', 'nave-for-woocommerce' ), 'error' );
            return [ 'result' => 'failure' ];
        }
    }

    // ── Getters ──────────────────────────────────────────────────────────────

    public function get_client_id(): string     { return (string) $this->get_option( 'client_id', '' ); }
    public function get_client_secret(): string { return (string) $this->get_option( 'client_secret', '' ); }
    public function get_pos_id(): string        { return (string) $this->get_option( 'pos_id', '' ); }
    public function get_environment(): string   { return (string) $this->get_option( 'environment', 'sandbox' ); }

    private function log( string $message, string $level = 'debug' ): void {
        if ( 'yes' !== $this->get_option( 'debug' ) ) {
            return;
        }
        wc_get_logger()->log( $level, '[NaveGateway] ' . $message, [ 'source' => 'nave-for-woocommerce' ] );
    }
}
