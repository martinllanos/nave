<?php
/**
 * WooCommerce Blocks Support para Nave.
 *
 * @package NaveWC\Blocks
 */

declare( strict_types=1 );

namespace NaveWC\Blocks;

defined( 'ABSPATH' ) || exit;

use Automattic\WooCommerce\Blocks\Payments\Integrations\AbstractPaymentMethodType;

final class NaveBlocksSupport extends AbstractPaymentMethodType {

    protected $name = 'nave';

    public function initialize(): void {
        $this->settings = get_option( 'woocommerce_nave_settings', [] );
    }

    public function is_active(): bool {
        $gateway = $this->get_gateway();
        return $gateway ? $gateway->is_available() : false;
    }

    public function get_payment_method_script_handles(): array {
        wp_register_script(
            'nave-wc-blocks',
            NAVE_WC_URL . 'assets/js/nave-blocks.js',
            [ 'wc-blocks-registry', 'wc-settings', 'wp-element', 'wp-i18n' ],
            NAVE_WC_VERSION,
            true
        );
        return [ 'nave-wc-blocks' ];
    }

    public function get_payment_method_data(): array {
        $gateway = $this->get_gateway();

        return [
            'title'       => $gateway ? $gateway->get_option( 'title', 'Pagá con tarjetas, MODO o QR' ) : 'Pagá con tarjetas, MODO o QR',
            'description' => $gateway ? $gateway->get_option( 'description', '' ) : '',
            'icon_url'    => NAVE_WC_URL . 'assets/images/nave-logo.svg',
            'cards_url'   => NAVE_WC_URL . 'assets/images/cards/',
            'is_sandbox'  => $gateway ? $gateway->get_environment() === 'sandbox' : true,
            'supports'    => [ 'products' ],
        ];
    }

    private function get_gateway(): ?\NaveWC\Gateway\NaveGateway {
        $gateways = WC()->payment_gateways()->payment_gateways();
        return $gateways['nave'] ?? null;
    }
}
