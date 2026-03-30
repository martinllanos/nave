<?php
/**
 * Nave for WooCommerce — Uninstall.
 *
 * Limpia datos del plugin al desinstalar desde el admin de WordPress.
 * No se ejecuta al desactivar, solo al eliminar.
 *
 * @package NaveWC
 */

defined( 'WP_UNINSTALL_PLUGIN' ) || exit;

// 1. Eliminar transients de tokens.
global $wpdb;
// phpcs:ignore WordPress.DB.DirectDatabaseQuery.DirectQuery, WordPress.DB.DirectDatabaseQuery.NoCaching -- Cleanup on uninstall, caching not applicable.
$wpdb->query(
    $wpdb->prepare(
        "DELETE FROM {$wpdb->options} WHERE option_name LIKE %s OR option_name LIKE %s",
        '_transient_nave_wc_token_%',
        '_transient_timeout_nave_wc_token_%'
    )
);

// 2. Desregistrar cron.
$nave_wc_cron_timestamp = wp_next_scheduled( 'nave_wc_polling_cron' );
if ( $nave_wc_cron_timestamp ) {
    wp_unschedule_event( $nave_wc_cron_timestamp, 'nave_wc_polling_cron' );
}

// 3. Limpiar locks residuales.
// phpcs:ignore WordPress.DB.DirectDatabaseQuery.DirectQuery, WordPress.DB.DirectDatabaseQuery.NoCaching -- Cleanup on uninstall, caching not applicable.
$wpdb->query(
    $wpdb->prepare(
        "DELETE FROM {$wpdb->options} WHERE option_name LIKE %s",
        'nave_lock_%'
    )
);

// 4. Eliminar settings del gateway.
delete_option( 'woocommerce_nave_settings' );
