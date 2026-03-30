<?php
/**
 * Order State Resolver.
 *
 * Traduce los estados de Nave a estados de WooCommerce y aplica la transición.
 *
 * @package NaveWC\Resolver
 */

declare( strict_types=1 );

namespace NaveWC\Resolver;

defined( 'ABSPATH' ) || exit;

final class OrderStateResolver {

    /**
     * Mapeo de estados de la INTENCIÓN de pago → WooCommerce.
     *
     * Máquina de estados real (ver diagrama Nave):
     *   PENDING → PROCESSED → SUCCESS_PROCESSED (final positivo)
     *                       → FAILURE_PROCESSED (puede reintentar, no es final)
     *                       → EXPIRED           (final — tiempo agotado)
     *                       → BLOCKED           (final — bloqueado por Nave)
     *   PENDING → DISABLED  (final — intención deshabilitada antes de procesarse)
     *
     * FAILURE_PROCESSED no está en FINAL_STATUSES porque puede volver a PROCESSED
     * si el comercio tiene reintentos habilitados (payment_retries_allowed, default 5).
     *
     * @var array<string,string>
     */
    private const STATUS_MAP = [
        'PENDING'           => 'pending',   // Intención creada, esperando pago
        'PROCESSED'         => 'on-hold',   // Pago en proceso (estado intermedio)
        'SUCCESS_PROCESSED' => 'completed', // Pago exitoso — final positivo
        'FAILURE_PROCESSED' => 'pending',   // Intento fallido pero puede reintentar → no usar failed
        'EXPIRED'           => 'cancelled', // Tiempo agotado — final
        'DISABLED'          => 'cancelled', // Deshabilitado — final
        'BLOCKED'           => 'cancelled', // Bloqueado por Nave — final
    ];

    /**
     * Estados finales de la intención — no admiten nuevos reintentos.
     * Basado en el diagrama oficial de Nave.
     *
     * FAILURE_PROCESSED está excluido porque el diagrama muestra que puede
     * recibir "Nuevo intento de pago" (flecha de vuelta a PROCESSED).
     * El límite de reintentos lo controla Nave vía payment_retries_allowed (default 5).
     *
     * @var array<string>
     */
    private const FINAL_STATUSES = [
        'SUCCESS_PROCESSED', // Final positivo — pago exitoso
        'EXPIRED',           // Final — tiempo de la intención agotado
        'DISABLED',          // Final — intención deshabilitada
        'BLOCKED',           // Final — bloqueado por Nave, sin más reintentos
    ];

    /**
     * Mapeo de estados del payment → estado WooCommerce.
     *
     * Máquina de estados del payment Nave:
     *
     *   PENDING ──→ APPROVED (pago aprobado)
     *   PENDING ──→ REJECTED (pago rechazado — final)
     *
     *   APPROVED ──→ CANCELLED            (cancelación manual antes del cierre del lote — final)
     *   APPROVED ──→ REFUNDED             (devolución total emitida — final)
     *   APPROVED ──→ PARTIALLY_REFUNDED   (devolución parcial aprobada — puede evolucionar a REFUNDED)
     *   APPROVED ──→ PURCHASE_REVERSED    (reversado antes de liquidarse — final)
     *   APPROVED ──→ CHARGEBACK_REVIEW    (disputa en proceso por contracargo)
     *   PARTIALLY_REFUNDED ──→ REFUNDED   (devolución total posterior — final)
     *   CHARGEBACK_REVIEW ──→ APPROVED    (disputa ganada por el comercio)
     *   CHARGEBACK_REVIEW ──→ CHARGED_BACK (contracargo confirmado por la entidad emisora — final)
     *
     * Solo se mapean los estados que Nave envía en el campo status.name del payment.
     * REVERSE_PURCHASE y CANCEL son eventos internos, no estados — Nave nunca los envía.
     *
     * @var array<string,string>
     */
    private const PAYMENT_STATUS_MAP = [
        'APPROVED'             => 'completed', // Pago aprobado — orden completada
        'REJECTED'             => 'pending',   // Terminal para ese payment, pero la intención puede tener más reintentos
        'CANCELLED'            => 'cancelled', // Cancelación manual antes del cierre del lote — final
        'REFUNDED'             => 'refunded',  // Devolución total emitida — final
        'PARTIALLY_REFUNDED'   => 'completed', // Devolución parcial aprobada — la orden sigue activa (WC 'refunded' implica devolución total)
        'PURCHASE_REVERSED'    => 'refunded',  // Reversado antes de liquidarse — final
        'CHARGEBACK_REVIEW'    => 'on-hold',   // Disputa activa — suspender hasta resolución
        'CHARGED_BACK'         => 'refunded',  // Contracargo confirmado por la entidad emisora — final
        // PENDING: sin transición, transacción iniciada sin resultado final
    ];

    /**
     * Estados terminales de un payment — no pueden cambiar más.
     *
     * APPROVED NO es terminal: puede derivar en CANCELLED, REFUNDED, PARTIALLY_REFUNDED, PURCHASE_REVERSED o CHARGEBACK_REVIEW.
     * PARTIALLY_REFUNDED NO es terminal: puede derivar en REFUNDED (devolución total posterior).
     * CHARGEBACK_REVIEW NO es terminal: puede volver a APPROVED (disputa ganada) o ir a CHARGED_BACK.
     *
     * @var array<string>
     */
    private const PAYMENT_FINAL_STATUSES = [
        'REJECTED',          // Terminal absoluto
        'CANCELLED',         // Terminal
        'REFUNDED',          // Terminal
        'PURCHASE_REVERSED', // Terminal
        'CHARGED_BACK',      // Terminal
    ];

    /**
     * Aplica la transición de estado WC basándose en el estado del PAYMENT.
     *
     * Este es el método principal de resolución. El estado del payment es la
     * fuente de verdad porque una intención puede tener muchos pagos, y los
     * estados post-aprobación (REFUNDED, CHARGED_BACK, etc.) solo se reflejan
     * a nivel payment — la intención queda en SUCCESS_PROCESSED.
     *
     * @param \WC_Order $order
     * @param string    $payment_status Estado del payment devuelto por la API de Nave.
     * @return bool  true si se aplicó algún cambio, false si no hubo transición.
     */
    public function resolve_by_payment_status( \WC_Order $order, string $payment_status ): bool {
        if ( ! $payment_status ) {
            return false;
        }

        // Guardar el estado del payment en meta.
        $order->update_meta_data( '_nave_payment_status', sanitize_text_field( $payment_status ) );

        // Agregar nota descriptiva y número de operación si corresponde.
        $this->add_payment_status_note( $order );
        $this->add_payment_code_note_if_missing( $order );

        // Determinar el estado WC objetivo.
        if ( ! isset( self::PAYMENT_STATUS_MAP[ $payment_status ] ) ) {
            // Estado transitorio (ej. PENDING) — no transicionar WC.
            $order->save();
            return false;
        }

        $wc_status = self::PAYMENT_STATUS_MAP[ $payment_status ];

        // Idempotencia: si la orden ya está en el estado objetivo, no hacer nada.
        if ( $order->get_status() === $wc_status ) {
            $order->save();
            return false;
        }

        // APPROVED → usar payment_complete() para reducir stock y disparar hooks WC.
        if ( 'APPROVED' === $payment_status ) {
            // Si ya está pagada, no reprocesar.
            if ( $order->is_paid() ) {
                $order->save();
                return false;
            }
            // La nota descriptiva ya fue agregada por add_payment_status_note().
            // Suprimimos la nota genérica "Payment complete." de WC.
            $this->payment_complete_silent( $order );
            $order->save();
            return true;
        }

        // Resto de estados: transición directa via update_status().
        // No pasamos nota como segundo argumento porque add_payment_status_note()
        // ya agregó la nota descriptiva correspondiente al estado.
        $order->update_status( $wc_status );
        $order->save();

        return true;
    }

    /**
     * Aplica la transición de estado basándose en el estado de la INTENCIÓN.
     *
     * Método de fallback: se usa solo cuando no hay estado de payment disponible
     * (ej. la intención expiró antes de que se generara un pago, o fue bloqueada/deshabilitada).
     * En el flujo normal, resolve_by_payment_status() es el método principal.
     *
     * @param \WC_Order $order
     * @param string    $nave_status Estado de la intención devuelto por la API de Nave.
     * @return bool  true si se aplicó algún cambio, false si ya estaba en estado final.
     */
    public function resolve( \WC_Order $order, string $nave_status ): bool {
        // Si la orden ya está completada/pagada y Nave confirma SUCCESS_PROCESSED, no hacer nada.
        // Para cualquier otro estado (ej. REFUNDED, CHARGED_BACK) sí procesamos aunque esté pagada.
        if ( $order->is_paid() && 'SUCCESS_PROCESSED' === $nave_status ) {
            return false;
        }

        // Actualizar meta con el estado Nave.
        $order->update_meta_data( '_nave_status', sanitize_text_field( $nave_status ) );

        $wc_status = self::STATUS_MAP[ $nave_status ] ?? 'on-hold';

        if ( 'SUCCESS_PROCESSED' === $nave_status ) {
            // payment_complete() maneja la transición a completed desde cualquier estado,
            // incluyendo failed y cancelled, respetando el filtro
            // woocommerce_valid_order_statuses_for_payment_complete que registramos en Bootstrap.
            // Suprimimos la nota genérica "Payment complete." de WC.
            $this->payment_complete_silent( $order );
        } else {
            // Para el resto de estados usamos update_status sin nota en el segundo argumento
            // porque WC concatena esa nota con "Order status changed from X to Y" (en inglés).
            // La nota descriptiva de Nave la agrega add_payment_status_note() abajo.
            $order->update_status( $wc_status );
        }

        // Nota: payment_complete() ya reduce stock internamente.
        // No llamar wc_reduce_stock_levels() manualmente para evitar doble reducción.

        // Primero intentar nota de payment (si hay _nave_payment_status).
        // Si no, agregar nota descriptiva basada en la intención.
        $this->add_payment_status_note( $order );
        $this->add_payment_code_note_if_missing( $order );

        if ( ! $order->get_meta( '_nave_payment_status' ) ) {
            $this->add_intent_status_note( $order, $nave_status );
        }

        $order->save();

        return true;
    }


    /**
     * Llama a payment_complete() suprimiendo la nota genérica "Payment complete." de WC.
     *
     * WooCommerce agrega esa nota en inglés dentro de payment_complete().
     * Nosotros ya agregamos una nota descriptiva en español vía add_payment_status_note(),
     * así que la de WC es redundante. Se elimina inmediatamente después de la inserción.
     */
    private function payment_complete_silent( \WC_Order $order ): void {
        $order->payment_complete();

        // Eliminar la nota "Payment complete." que WC acaba de insertar.
        $notes = wc_get_order_notes( [
            'order_id' => $order->get_id(),
            'limit'    => 3,
            'orderby'  => 'date_created',
            'order'    => 'DESC',
        ] );
        foreach ( $notes as $note ) {
            if ( 'Payment complete.' === trim( $note->content ) ) {
                wc_delete_order_note( $note->id );
                break;
            }
        }
    }

    /**
     * Agrega una order note descriptiva basada en el estado de la INTENCIÓN.
     * Se usa como fallback cuando no hay payment (la intención expiró, fue bloqueada, etc.).
     * Idempotente: usa _nave_intent_status_noted como guard.
     */
    private function add_intent_status_note( \WC_Order $order, string $nave_status ): void {
        $last_noted = $order->get_meta( '_nave_intent_status_noted' );
        if ( $nave_status === $last_noted ) {
            return;
        }

        $notes = [
            'PENDING'           => __( '[Nave] Intención de pago creada, aguardando que el cliente pague.', 'nave-for-woocommerce' ),
            'PROCESSED'         => __( '[Nave] Intención en proceso, el cliente está pagando.', 'nave-for-woocommerce' ),
            'SUCCESS_PROCESSED' => __( '[Nave] Intención procesada exitosamente.', 'nave-for-woocommerce' ),
            'FAILURE_PROCESSED' => __( '[Nave] Intento de pago fallido. El cliente puede reintentar.', 'nave-for-woocommerce' ),
            'EXPIRED'           => __( '[Nave] Intención de pago expirada. El cliente no completó el pago a tiempo.', 'nave-for-woocommerce' ),
            'DISABLED'          => __( '[Nave] Intención de pago deshabilitada.', 'nave-for-woocommerce' ),
            'BLOCKED'           => __( '[Nave] Intención de pago bloqueada por Nave.', 'nave-for-woocommerce' ),
        ];

        $note = $notes[ $nave_status ] ?? sprintf(
            /* translators: %s: Estado de la intención Nave */
            __( '[Nave] Estado de la intención: %s', 'nave-for-woocommerce' ),
            $nave_status
        );

        $order->add_order_note( $note );
        $order->update_meta_data( '_nave_intent_status_noted', sanitize_text_field( $nave_status ) );
    }

    /**
     * Agrega una order note si el estado del payment cambió desde la última vez que se registró.
     * Cubre todos los estados posibles de un pago Nave.
     * Seguro de llamar múltiples veces — usa _nave_payment_status_noted como guard.
     *
     * NOTA: Este método solo agrega notas informativas y el número de operación.
     * La transición de estado WC la maneja resolve_by_payment_status().
     */
    public function add_payment_status_note( \WC_Order $order ): void {
        $payment_status = $order->get_meta( '_nave_payment_status' );
        $payment_code   = $order->get_meta( '_nave_payment_code' );

        if ( ! $payment_status ) {
            return;
        }

        // Solo actuar si el estado cambió desde la última nota registrada.
        $last_noted = $order->get_meta( '_nave_payment_status_noted' );
        if ( $payment_status === $last_noted ) {
            return;
        }

        // Notas alineadas con los estados del payment de Nave.
        $notes = [
            'PENDING'           => __( '[Nave] Pago iniciado, aguardando resultado.', 'nave-for-woocommerce' ),
            'APPROVED'          => __( '[Nave] Pago aprobado por la entidad emisora.', 'nave-for-woocommerce' ),
            'REJECTED'          => __( '[Nave] Pago rechazado por la entidad emisora. Si el cliente reintenta, Nave generará un nuevo intento de pago.', 'nave-for-woocommerce' ),
            'CANCELLED'         => __( '[Nave] Cancelación manual antes del cierre del lote. La devolución puede tardar algunos días hábiles.', 'nave-for-woocommerce' ),
            'REFUNDED'          => __( '[Nave] Devolución total del pago emitida. La acreditación puede tardar algunos días hábiles.', 'nave-for-woocommerce' ),
            'PARTIALLY_REFUNDED' => __( '[Nave] Devolución parcial aprobada. La acreditación parcial puede tardar algunos días hábiles.', 'nave-for-woocommerce' ),
            'PURCHASE_REVERSED' => __( '[Nave] Pago reversado antes de liquidarse. El importe no fue debitado al cliente.', 'nave-for-woocommerce' ),
            'CHARGEBACK_REVIEW' => __( '[Nave] Disputa en proceso por contracargo. La orden queda suspendida hasta la resolución. Revisar con Nave.', 'nave-for-woocommerce' ),
            'CHARGED_BACK'      => __( '[Nave] Contracargo confirmado por la entidad emisora. El importe fue devuelto al cliente.', 'nave-for-woocommerce' ),
        ];

        $note = $notes[ $payment_status ] ?? sprintf(
            /* translators: %s: Estado del pago Nave */
            __( '[Nave] Estado del pago actualizado: %s', 'nave-for-woocommerce' ),
            $payment_status
        );

        // Estados donde incluir el número de operación en la nota.
        $states_with_code = [ 'APPROVED', 'REFUNDED', 'PARTIALLY_REFUNDED', 'PURCHASE_REVERSED', 'CHARGED_BACK', 'CANCELLED' ];
        if ( $payment_code && in_array( $payment_status, $states_with_code, true ) ) {
            $note .= ' ' . sprintf(
                /* translators: %s: Número de operación del pago */
                __( 'Número de operación: %s', 'nave-for-woocommerce' ),
                $payment_code
            );
        }

        $order->add_order_note( $note );
        $order->update_meta_data( '_nave_payment_status_noted', sanitize_text_field( $payment_status ) );

        // Guardar si el código de operación ya fue incluido en la nota.
        if ( $payment_code && in_array( $payment_status, $states_with_code, true ) ) {
            $order->update_meta_data( '_nave_payment_code_noted', sanitize_text_field( $payment_code ) );
        }
    }

    /**
     * Si el payment_code llegó después de que la nota de estado ya se había grabado
     * (ej. APPROVED sin código en el primer webhook, código disponible en un refresh),
     * agrega una nota complementaria con el número de operación.
     * Idempotente: usa _nave_payment_code_noted como guard.
     */
    public function add_payment_code_note_if_missing( \WC_Order $order ): void {
        $payment_code   = $order->get_meta( '_nave_payment_code' );
        $payment_status = $order->get_meta( '_nave_payment_status' );
        $code_noted     = $order->get_meta( '_nave_payment_code_noted' );

        if ( ! $payment_code || $payment_code === $code_noted ) {
            return;
        }

        $states_with_code = [ 'APPROVED', 'REFUNDED', 'PARTIALLY_REFUNDED', 'PURCHASE_REVERSED', 'CHARGED_BACK', 'CANCELLED' ];
        if ( ! in_array( $payment_status, $states_with_code, true ) ) {
            return;
        }

        $order->add_order_note(
            sprintf(
                /* translators: %s: Número de operación del pago */
                __( '[Nave] Número de operación: %s', 'nave-for-woocommerce' ),
                $payment_code
            )
        );
        $order->update_meta_data( '_nave_payment_code_noted', sanitize_text_field( $payment_code ) );
        $order->save();
    }

    /**
     * Indica si el estado de la intención Nave es final (no se debe consultar de nuevo).
     */
    public function is_final_status( string $nave_status ): bool {
        return in_array( $nave_status, self::FINAL_STATUSES, true );
    }

    /**
     * Indica si el estado del payment es terminal (no puede cambiar más).
     */
    public function is_payment_final_status( string $payment_status ): bool {
        return in_array( $payment_status, self::PAYMENT_FINAL_STATUSES, true );
    }

    /**
     * Devuelve el estado WooCommerce correspondiente a un estado Nave.
     *
     * @param string $nave_status
     */
    public function get_wc_status( string $nave_status ): string {
        return self::STATUS_MAP[ $nave_status ] ?? 'on-hold';
    }
}
