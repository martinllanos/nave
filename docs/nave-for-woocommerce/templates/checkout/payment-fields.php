<?php
/**
 * Template: Checkout payment fields (checkout clásico)
 *
 * @var string $logo_url
 * @var string $description
 * @var bool   $is_sandbox
 */
defined( 'ABSPATH' ) || exit;
?>

<div class="nave-checkout-container">

    <?php if ( $is_sandbox ) : ?>
    <div class="nave-sandbox-badge">
        <span class="nave-sandbox-dot"></span>
        <?php esc_html_e( 'Modo Sandbox para pruebas', 'nave-for-woocommerce' ); ?>
    </div>
    <?php endif; ?>

    <?php if ( ! empty( $description ) ) : ?>
    <p class="nave-checkout-description"><?php echo esc_html( $description ); ?></p>
    <?php endif; ?>

    <div class="nave-redirect-notice">
        <img src="<?php echo esc_url( $logo_url ); ?>" alt="Nave" class="nave-redirect-logo" />
        <div class="nave-redirect-text">
            <span class="nave-redirect-title">
                <?php esc_html_e( 'Serás redirigido a Nave', 'nave-for-woocommerce' ); ?>
            </span>
            <span class="nave-redirect-description">
                <?php esc_html_e( 'Completá el pago de forma segura en la plataforma de Nave.', 'nave-for-woocommerce' ); ?>
            </span>
        </div>
        <svg class="nave-redirect-arrow" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M3 8H13M13 8L9 4M13 8L9 12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
    </div>

</div>
