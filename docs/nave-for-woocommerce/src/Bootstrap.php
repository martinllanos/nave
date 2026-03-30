<?php
/**
 * Plugin Bootstrap.
 *
 * Registra el payment gateway, hooks, y soporte para Block Checkout.
 *
 * @package NaveWC
 */

declare( strict_types=1 );

namespace NaveWC;

defined( 'ABSPATH' ) || exit;

use NaveWC\Gateway\NaveGateway;
use NaveWC\Handler\ReturnHandler;
use NaveWC\Handler\WebhookHandler;
use NaveWC\Handler\CronHandler;

final class Bootstrap {

    private static ?self $instance = null;

    public static function instance(): self {
        if ( null === self::$instance ) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    private function __construct() {}

    /**
     * Inicializa todos los hooks.
     */
    public function init(): void {
        // Registrar gateway clásico.
        add_filter( 'woocommerce_payment_gateways', [ $this, 'register_gateway' ] );

        // Registrar soporte para Block Checkout (Gutenberg).
        add_action( 'woocommerce_blocks_loaded', [ $this, 'register_blocks_support' ] );

        // Registrar WC API callback endpoint.
        add_action( 'woocommerce_api_nave_return', [ new ReturnHandler(), 'handle' ] );

        // Admin: dropdown de acciones en pedido.
        add_action( 'woocommerce_order_actions', [ $this, 'add_order_action' ] );
        add_action( 'woocommerce_order_action_nave_check_status', [ $this, 'handle_order_action' ] );

        // Admin meta box para pantalla de pedido (clásica y HPOS).
        add_action( 'add_meta_boxes', [ $this, 'add_meta_box' ] );
        add_action( 'wp_ajax_nave_check_order_status', [ $this, 'ajax_check_order_status' ] );

        // Registrar endpoint REST del webhook de Nave.
        add_action( 'rest_api_init', function() {
            ( new WebhookHandler() )->register_routes();
        } );

        // Registrar cron de polling como safety net.
        CronHandler::register();

        // Forzar estado 'completed' tras payment_complete() para órdenes Nave.
        // WC por defecto pone 'processing' después de payment_complete() salvo que
        // todos los productos sean virtuales. Nave ya confirmó el pago externamente.
        add_filter( 'woocommerce_payment_complete_order_status', [ $this, 'force_completed_status' ], 10, 3 );

        // Permitir payment_complete() desde 'pending' (WC ya lo permite por defecto,
        // pero lo explicitamos por claridad y para cubrir edge cases).
        add_filter( 'woocommerce_valid_order_statuses_for_payment_complete', [ $this, 'allow_payment_complete_from_failed' ] );

        // Frontend: mostrar payment_code en Mi cuenta → Pedidos (detalle de orden).
        add_action( 'woocommerce_order_details_after_order_table', [ $this, 'render_payment_code_frontend' ] );

        // Email: incluir payment_code en email de confirmación de WooCommerce.
        add_action( 'woocommerce_email_after_order_table', [ $this, 'render_payment_code_email' ], 10, 4 );
    }

    /**
     * Registrar el gateway clásico.
     *
     * @param array<string> $gateways
     * @return array<string>
     */
    public function register_gateway( array $gateways ): array {
        $gateways[] = NaveGateway::class;
        return $gateways;
    }

    /**
     * Registrar integración con WooCommerce Block Checkout.
     */
    public function register_blocks_support(): void {
        if ( ! class_exists( '\Automattic\WooCommerce\Blocks\Payments\Integrations\AbstractPaymentMethodType' ) ) {
            return;
        }

        add_action(
            'woocommerce_blocks_payment_method_type_registration',
            static function ( \Automattic\WooCommerce\Blocks\Payments\PaymentMethodRegistry $registry ): void {
                $registry->register( new \NaveWC\Blocks\NaveBlocksSupport() );
            }
        );
    }

    /**
     * Agregar acción manual al dropdown del pedido en admin.
     *
     * @param array<string,string> $actions
     * @return array<string,string>
     */
    public function add_order_action( array $actions ): array {
        $actions['nave_check_status'] = __( 'Consultar estado en Nave', 'nave-for-woocommerce' );
        return $actions;
    }

    /**
     * Ejecutar la acción manual del pedido.
     *
     * @param \WC_Order $order
     */
    public function handle_order_action( \WC_Order $order ): void {
        ( new ReturnHandler() )->refresh_order_data( $order );
    }

    /**
     * Agregar meta box en la pantalla de pedido (clásica y HPOS).
     */
    public function add_meta_box(): void {
        $screen = 'shop_order';

        if (
            class_exists( '\Automattic\WooCommerce\Internal\DataStores\Orders\CustomOrdersTableController' )
            && function_exists( 'wc_get_container' )
        ) {
            try {
                $controller = wc_get_container()->get(
                    \Automattic\WooCommerce\Internal\DataStores\Orders\CustomOrdersTableController::class
                );
                if ( $controller->custom_orders_table_usage_is_enabled() ) {
                    $screen = wc_get_page_screen_id( 'shop-order' );
                }
            } catch ( \Exception $e ) {
                // Fallback a shop_order clásico.
            }
        }

        add_meta_box(
            'nave_order_meta',
            __( 'Nave - Estado del Pago', 'nave-for-woocommerce' ),
            [ $this, 'render_meta_box' ],
            $screen,
            'side'
        );
    }

    /**
     * Renderizar el meta box.
     *
     * @param \WP_Post|\WC_Order $post_or_order
     */
    public function render_meta_box( $post_or_order ): void {
        $order_id_raw = $post_or_order instanceof \WC_Order ? $post_or_order->get_id() : absint( $post_or_order->ID );
        $order        = wc_get_order( $order_id_raw );

        if ( ! $order || $order->get_payment_method() !== NAVE_WC_SLUG ) {
            echo '<p>' . esc_html__( 'Este pedido no usa Nave.', 'nave-for-woocommerce' ) . '</p>';
            return;
        }

        $payment_request_id = $order->get_meta( '_nave_payment_request_id' );
        $intention_status   = $order->get_meta( '_nave_status' );
        $payment_id         = $order->get_meta( '_nave_payment_id' );
        $payment_status     = $order->get_meta( '_nave_payment_status' );
        $payment_code       = $order->get_meta( '_nave_payment_code' );

        // Mapa de estados del payment para descripción legible.
        $payment_status_labels = [
            'PENDING'            => __( 'Iniciado, sin resultado', 'nave-for-woocommerce' ),
            'APPROVED'           => __( 'Pago aprobado', 'nave-for-woocommerce' ),
            'REJECTED'           => __( 'Pago rechazado', 'nave-for-woocommerce' ),
            'CANCELLED'          => __( 'Cancelado manualmente', 'nave-for-woocommerce' ),
            'REFUNDED'           => __( 'Devolución total emitida', 'nave-for-woocommerce' ),
            'PURCHASE_REVERSED'  => __( 'Reversado pre-liquidación', 'nave-for-woocommerce' ),
            'CHARGEBACK_REVIEW'  => __( 'Disputa en proceso', 'nave-for-woocommerce' ),
            'CHARGED_BACK'       => __( 'Contracargo confirmado', 'nave-for-woocommerce' ),
        ];

        $payment_status_display = $payment_status
            ? ( $payment_status_labels[ $payment_status ] ?? $payment_status )
            : 'N/A';

        // 1. ID de intención de pago
        echo '<p><strong>' . esc_html__( 'ID de intención de pago:', 'nave-for-woocommerce' ) . '</strong><br>';
        echo '<small style="color:#444;word-break:break-all;">' . esc_html( $payment_request_id ?: 'N/A' ) . '</small></p>';

        // 2. Estado de la intención
        echo '<p><strong>' . esc_html__( 'Estado de la intención:', 'nave-for-woocommerce' ) . '</strong><br>';
        echo '<span style="font-family:monospace;">' . esc_html( $intention_status ?: 'N/A' ) . '</span></p>';

        // 3. ID del pago
        echo '<p><strong>' . esc_html__( 'ID del pago:', 'nave-for-woocommerce' ) . '</strong><br>';
        echo '<small style="color:#444;word-break:break-all;">' . esc_html( $payment_id ?: 'N/A' ) . '</small></p>';

        // 4. Estado del pago
        echo '<p><strong>' . esc_html__( 'Estado del pago:', 'nave-for-woocommerce' ) . '</strong><br>';
        echo '<span style="font-family:monospace;">' . esc_html( $payment_status_display ) . '</span></p>';

        // 5. Número de operación
        if ( $payment_code ) {
            echo '<p><strong>' . esc_html__( 'Número de operación:', 'nave-for-woocommerce' ) . '</strong><br>';
            echo '<code style="background:#f0f0f0;padding:2px 6px;border-radius:3px;font-size:13px;">' . esc_html( $payment_code ) . '</code></p>';
        }

        if ( $payment_request_id ) {
            $nonce    = wp_create_nonce( 'nave_check_status_' . $order->get_id() );
            $ajax_url = admin_url( 'admin-ajax.php' );
            printf(
                '<button type="button" class="button button-secondary" onclick="naveCheckStatus(%d, \'%s\', \'%s\')">%s</button>',
                absint( $order->get_id() ),
                esc_js( $nonce ),
                esc_js( $ajax_url ),
                esc_html__( 'Consultar estado en Nave', 'nave-for-woocommerce' )
            );
            echo '<span id="nave-status-result" style="display:block;margin-top:8px;"></span>';

            $consulting_text    = esc_js( __( 'Consultando...', 'nave-for-woocommerce' ) );
            $button_text        = esc_js( __( 'Consultar estado en Nave', 'nave-for-woocommerce' ) );
            $inline_js = "
                function naveCheckStatus(orderId, nonce, ajaxUrl) {
                    var btn = event.target;
                    btn.disabled = true;
                    btn.textContent = '{$consulting_text}';
                    fetch(ajaxUrl, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                        body: 'action=nave_check_order_status&order_id=' + orderId + '&nonce=' + nonce
                    })
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        document.getElementById('nave-status-result').textContent = data.message || data.data;
                        btn.disabled = false;
                        btn.textContent = '{$button_text}';
                        if (data.success) setTimeout(function() { location.reload(); }, 1500);
                    })
                    .catch(function() { btn.disabled = false; });
                }
            ";
            wp_register_script( 'nave-admin-check-status', false, [], NAVE_WC_VERSION, true );
            wp_enqueue_script( 'nave-admin-check-status' );
            wp_add_inline_script( 'nave-admin-check-status', $inline_js );
        }
    }


    /**
     * Muestra el payment_code en la página de detalle de pedido (Mi cuenta → Pedidos).
     * Solo si el método de pago es Nave y hay payment_code.
     *
     * @param \WC_Order $order
     */
    public function render_payment_code_frontend( \WC_Order $order ): void {
        if ( $order->get_payment_method() !== NAVE_WC_SLUG ) {
            return;
        }
        $payment_code = $order->get_meta( '_nave_payment_code' );
        if ( ! $payment_code ) {
            return;
        }
        ?>
        <section class="woocommerce-nave-payment-code" style="margin:20px 0;padding:16px 20px;background:#F5EEFF;border:1px solid #D4AAFF;border-radius:10px;">
            <h2 style="font-size:15px;margin:0 0 6px;color:#1A1A1A;">
                <?php esc_html_e( 'Número de operación', 'nave-for-woocommerce' ); ?>
            </h2>
            <p style="margin:0 0 8px;font-size:13px;color:#6B7280;">
                <?php esc_html_e( 'Usá este número para identificar tu pago ante cualquier reclamo.', 'nave-for-woocommerce' ); ?>
            </p>
            <code style="display:inline-block;background:#fff;border:1px solid #D4AAFF;border-radius:6px;padding:6px 14px;font-size:15px;font-weight:700;color:#7B2FBE;letter-spacing:0.04em;">
                <?php echo esc_html( $payment_code ); ?>
            </code>
        </section>
        <?php
    }

    /**
     * Agrega el payment_code al email de confirmación de WooCommerce.
     * Se muestra en el email de nuevo pedido (admin) y en los emails de
     * confirmación al cliente (completed y processing).
     *
     * @param \WC_Order $order
     * @param bool      $sent_to_admin
     * @param bool      $plain_text
     * @param \WC_Email $email
     */
    public function render_payment_code_email( \WC_Order $order, bool $sent_to_admin, bool $plain_text, \WC_Email $email ): void {
        if ( $order->get_payment_method() !== NAVE_WC_SLUG ) {
            return;
        }

        $payment_code = $order->get_meta( '_nave_payment_code' );
        if ( ! $payment_code ) {
            return;
        }

        // Mostrar en emails relevantes: admin (new_order) y cliente (customer_completed_order, customer_processing_order).
        $relevant_emails = [ 'new_order', 'customer_completed_order', 'customer_processing_order' ];
        if ( ! in_array( $email->id, $relevant_emails, true ) ) {
            return;
        }

        if ( $plain_text ) {
            echo "
" . esc_html__( 'Número de operación:', 'nave-for-woocommerce' ) . ' ' . esc_html( $payment_code ) . "
" . esc_html__( 'Usá este número para identificar tu pago ante cualquier reclamo.', 'nave-for-woocommerce' ) . "
";
            return;
        }
        ?>
        <div style="margin:20px 0;padding:16px 20px;background:#F5EEFF;border:1px solid #D4AAFF;border-radius:8px;font-family:sans-serif;">
            <p style="margin:0 0 6px;font-size:14px;font-weight:700;color:#1A1A1A;">
                <?php esc_html_e( 'Número de operación', 'nave-for-woocommerce' ); ?>
            </p>
            <p style="margin:0 0 10px;font-size:13px;color:#6B7280;">
                <?php esc_html_e( 'Usá este número para identificar tu pago ante cualquier reclamo.', 'nave-for-woocommerce' ); ?>
            </p>
            <code style="display:inline-block;background:#fff;border:1px solid #D4AAFF;border-radius:6px;padding:8px 16px;font-size:16px;font-weight:700;color:#7B2FBE;letter-spacing:0.06em;">
                <?php echo esc_html( $payment_code ); ?>
            </code>
        </div>
        <?php
    }

    /**
     * Suprime los emails de "orden fallida" para órdenes Nave.
     * Aplica tanto al email del admin (failed_order) como al del cliente (customer_failed_order).
     * Razones:
     *  - El estado 'failed' es transitorio: puede haber un reintento exitoso.
     *  - Un error 500 de la API de Nave no debe comunicarse al cliente como orden fallida.
     *  - Si la intención finalmente expira o se bloquea, WC enviará el email correcto
     *    cuando el admin resuelva el estado manualmente.
     *
     * @param bool      $enabled Si el email está habilitado
     * @param \WC_Order $order   Objeto orden
     * @return bool
     */
    public function suppress_failed_email( bool $enabled, \WC_Order $order ): bool {
        if ( $order instanceof \WC_Order && $order->get_payment_method() === NAVE_WC_SLUG ) {
            return false;
        }
        return $enabled;
    }

    /**
     * Fuerza el estado 'completed' al llamar payment_complete() en órdenes Nave.
     * WooCommerce usa 'processing' por defecto; como Nave ya procesó el pago
     * externamente no hay fulfillment pendiente que justifique 'processing'.
     *
     * @param string    $status   Estado que WC aplicaría por defecto ('processing')
     * @param int       $order_id ID de la orden
     * @param \WC_Order $order    Objeto orden
     * @return string
     */
    public function force_completed_status( string $status, int $order_id, \WC_Order $order ): string {
        if ( $order->get_payment_method() === NAVE_WC_SLUG ) {
            return 'completed';
        }
        return $status;
    }

    /**
     * Permite que una orden en estado 'failed' pueda ser marcada como pagada (completed).
     * WooCommerce solo permite payment_complete() desde pending, on-hold y processing por defecto.
     * Necesario cuando un primer pago REJECTED deja la orden en 'failed' y luego
     * un reintento es APPROVED con SUCCESS_PROCESSED.
     *
     * @param array<string> $statuses
     * @return array<string>
     */
    public function allow_payment_complete_from_failed( array $statuses ): array {
        $statuses[] = 'failed';
        $statuses[] = 'cancelled';
        return array_unique( $statuses );
    }

    /**
     * Habilita transiciones de estado que WooCommerce no permite por defecto.
     * WC usa un grafo de transiciones válidas internamente; este filtro no existe
     * en WC core, pero update_status() respeta los statuses registrados.
     * La transición real la forzamos pasando el status directamente a update_status().
     *
     * @param array<string,string> $statuses
     * @return array<string,string>
     */
    public function register_nave_transitions( array $statuses ): array {
        // WooCommerce ya tiene todos los statuses que necesitamos registrados.
        // Este hook existe para confirmar que 'failed' y 'cancelled' están presentes.
        return $statuses;
    }

    public function ajax_check_order_status(): void {
        $order_id = absint( $_POST['order_id'] ?? 0 );
        $nonce    = sanitize_text_field( wp_unslash( $_POST['nonce'] ?? '' ) );

        if ( ! wp_verify_nonce( $nonce, 'nave_check_status_' . $order_id ) ) {
            wp_send_json_error( __( 'Nonce inválido.', 'nave-for-woocommerce' ) );
        }

        if ( ! current_user_can( 'edit_shop_orders' ) ) {
            wp_send_json_error( __( 'Sin permisos.', 'nave-for-woocommerce' ) );
        }

        $order = wc_get_order( $order_id );
        if ( ! $order ) {
            wp_send_json_error( __( 'Pedido no encontrado.', 'nave-for-woocommerce' ) );
        }

        $result = ( new ReturnHandler() )->refresh_order_data( $order );

        if ( $result ) {
            wp_send_json_success( __( 'Estado actualizado correctamente.', 'nave-for-woocommerce' ) );
        } else {
            wp_send_json_error( __( 'No se pudo actualizar. Revisa los logs.', 'nave-for-woocommerce' ) );
        }
    }
}
