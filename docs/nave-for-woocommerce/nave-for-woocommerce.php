<?php
/**
 * Plugin Name:       Nave for WooCommerce
 * Plugin URI:        https://github.com/jcabreranave/nave-for-woocommerce
 * Description:       Método de pago por redirección usando la API de Nave.
 * Version:           1.0.1
 * Author:            Nave Integrations
 * Author URI:        https://navenegocios.com/
 * License:           GPL-2.0+
 * License URI:       https://www.gnu.org/licenses/gpl-2.0.html
 * Text Domain:       nave-for-woocommerce
 * Domain Path:       /languages
 * Requires at least: 6.0
 * Requires PHP:      8.0
 * Requires Plugins:  woocommerce
 * WC requires at least: 8.0
 * WC tested up to:   9.6
 */

declare( strict_types=1 );

namespace NaveWC;

defined( 'ABSPATH' ) || exit;

// ─── Constants ───────────────────────────────────────────────────────────────
define( 'NAVE_WC_VERSION',   '1.0.1' );
define( 'NAVE_WC_FILE',      __FILE__ );
define( 'NAVE_WC_PATH',      plugin_dir_path( __FILE__ ) );
define( 'NAVE_WC_URL',       plugin_dir_url( __FILE__ ) );
define( 'NAVE_WC_SLUG',      'nave' );

// ─── Autoloader PSR-4 ────────────────────────────────────────────────────────
spl_autoload_register( static function ( string $class ): void {
    $prefix   = 'NaveWC\\';
    $base_dir = NAVE_WC_PATH . 'src/';

    if ( ! str_starts_with( $class, $prefix ) ) {
        return;
    }

    $relative = str_replace( $prefix, '', $class );
    $file     = $base_dir . str_replace( '\\', '/', $relative ) . '.php';

    if ( is_readable( $file ) ) {
        require $file;
    }
} );

// ─── HPOS Compatibility ──────────────────────────────────────────────────────
add_action( 'before_woocommerce_init', static function (): void {
    if ( class_exists( \Automattic\WooCommerce\Utilities\FeaturesUtil::class ) ) {
        \Automattic\WooCommerce\Utilities\FeaturesUtil::declare_compatibility(
            'custom_order_tables',
            NAVE_WC_FILE,
            true
        );
    }
} );

// ─── Deactivation: limpiar cron ──────────────────────────────────────────────
register_deactivation_hook( __FILE__, static function (): void {
    $timestamp = wp_next_scheduled( 'nave_wc_polling_cron' );
    if ( $timestamp ) {
        wp_unschedule_event( $timestamp, 'nave_wc_polling_cron' );
    }
} );

// ─── Bootstrap ───────────────────────────────────────────────────────────────
add_action( 'plugins_loaded', static function (): void {
    if ( ! class_exists( 'WC_Payment_Gateway' ) ) {
        add_action( 'admin_notices', static function (): void {
            echo '<div class="notice notice-error"><p>'
                . esc_html__( 'Nave for WooCommerce requiere que WooCommerce esté activo.', 'nave-for-woocommerce' )
                . '</p></div>';
        } );
        return;
    }

    Bootstrap::instance()->init();
} );
