<?php
/**
 * Cron Handler.
 *
 * Safety net para órdenes que quedaron en `pending` porque:
 * - El usuario cerró el navegador antes del redirect.
 * - El webhook no llegó o falló.
 *
 * Corre cada 15 minutos y procesa órdenes Nave en `pending`
 * con más de 30 minutos de antigüedad que no hayan sido
 * resueltas por el webhook.
 *
 * @package NaveWC\Handler
 */

declare( strict_types=1 );

namespace NaveWC\Handler;

defined( 'ABSPATH' ) || exit;

use NaveWC\Gateway\NaveGateway;

final class CronHandler {

    private const CRON_HOOK     = 'nave_wc_polling_cron';
    private const CRON_INTERVAL = 'nave_every_15_minutes';
    private const MIN_AGE       = 30; // Minutos mínimos antes de hacer polling

    // ── Registro ─────────────────────────────────────────────────────────────

    public static function register(): void {
        // Registrar intervalo personalizado de 15 minutos.
        add_filter( 'cron_schedules', [ self::class, 'add_cron_interval' ] );

        // Programar cron si no está programado.
        if ( ! wp_next_scheduled( self::CRON_HOOK ) ) {
            wp_schedule_event( time(), self::CRON_INTERVAL, self::CRON_HOOK );
        }

        // Vincular el hook al handler.
        add_action( self::CRON_HOOK, [ self::class, 'run' ] );
    }

    public static function unregister(): void {
        $timestamp = wp_next_scheduled( self::CRON_HOOK );
        if ( $timestamp ) {
            wp_unschedule_event( $timestamp, self::CRON_HOOK );
        }
    }

    /**
     * @param array<string,mixed> $schedules
     * @return array<string,mixed>
     */
    public static function add_cron_interval( array $schedules ): array {
        $schedules[ self::CRON_INTERVAL ] = [
            'interval' => 15 * MINUTE_IN_SECONDS,
            'display'  => __( 'Cada 15 minutos (Nave polling)', 'nave-for-woocommerce' ),
        ];
        return $schedules;
    }

    // ── Ejecución ─────────────────────────────────────────────────────────────

    public static function run(): void {
        $instance = new self();
        $instance->process_pending_orders();
    }

    private function process_pending_orders(): void {
        // Ventana de tiempo: solo órdenes entre MIN_AGE y MAX_AGE minutos de antigüedad.
        //
        // MIN_AGE (30 min): evita consultar órdenes que el webhook o el redirect
        //                   ya están por resolver.
        //
        // MAX_AGE: duration_time (tiempo de vida de la intención) + 5 min de buffer
        //          para que Nave haya procesado la expiración. Pasado ese tiempo,
        //          la intención ya está EXPIRED o en estado final → no tiene sentido consultar.
        //          Usamos el duration_time del gateway; si no está disponible, default 900s (15 min).
        $gateways     = WC()->payment_gateways()->payment_gateways();
        $gateway      = $gateways[ NAVE_WC_SLUG ] ?? null;
        $duration_sec = $gateway ? (int) $gateway->get_option( 'duration_time', 900 ) : 900;
        $max_age_min  = (int) ceil( $duration_sec / 60 ) + 5; // duration + 5 min buffer

        $cutoff_min = gmdate( 'Y-m-d H:i:s', time() - ( self::MIN_AGE * MINUTE_IN_SECONDS ) );
        $cutoff_max = gmdate( 'Y-m-d H:i:s', time() - ( $max_age_min * MINUTE_IN_SECONDS ) );

        // Buscar órdenes Nave en pending creadas dentro de la ventana activa.
        $order_ids = wc_get_orders( [
            'payment_method' => NAVE_WC_SLUG,
            'status'         => [ 'pending', 'on-hold' ],
            'date_created'   => $cutoff_max . '...' . $cutoff_min, // Entre MAX_AGE y MIN_AGE
            'limit'          => 20,
            'return'         => 'ids',
            'meta_query'     => [
                [
                    'key'     => '_nave_payment_request_id',
                    'compare' => 'EXISTS',
                ],
            ],
        ] );

        if ( empty( $order_ids ) ) {
            return;
        }

        $this->log( 'Cron polling: ' . count( $order_ids ) . ' ordenes pendientes encontradas.' );

        $return_handler = new ReturnHandler();

        foreach ( $order_ids as $order_id ) {
            $order = wc_get_order( $order_id );
            if ( ! $order ) {
                continue;
            }

            // Saltar si el webhook ya resolvió la orden recientemente.
            $webhook_received = $order->get_meta( '_nave_webhook_received' );
            if ( $webhook_received ) {
                $webhook_time = strtotime( $webhook_received );
                // Si el webhook llegó hace menos de 5 minutos, el cron lo saltea.
                if ( $webhook_time && ( time() - $webhook_time ) < 5 * MINUTE_IN_SECONDS ) {
                    $this->log( 'Cron: orden #' . $order_id . ' resuelta por webhook recientemente. Saltando.' );
                    continue;
                }
            }

            $this->log( 'Cron polling: consultando estado de orden #' . $order_id );

            try {
                $return_handler->process_order( $order );
            } catch ( \Throwable $e ) {
                $this->log( 'Cron: error procesando orden #' . $order_id . ': ' . $e->getMessage(), 'error' );
            }

            // Pausa entre requests para no saturar la API de Nave.
            usleep( 300000 ); // 300ms
        }
    }

    private function log( string $message, string $level = 'debug' ): void {
        $gateways = WC()->payment_gateways()->payment_gateways();
        $gateway  = $gateways[ NAVE_WC_SLUG ] ?? null;
        if ( ! $gateway || 'yes' !== $gateway->get_option( 'debug' ) ) {
            return;
        }
        wc_get_logger()->log( $level, '[CronHandler] ' . $message, [ 'source' => 'nave-for-woocommerce' ] );
    }
}
