/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { PaymentInterface } from "@point_of_sale/app/payment/payment_interface";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { register_payment_method } from "@point_of_sale/app/store/pos_store";

/**
 * Interfaz de Pagos POS para Terminales Smart POS de Nave.
 * Hereda de PaymentInterface para integrarse nativamente con Odoo 18.
 */
export class PaymentNave extends PaymentInterface {
    setup() {
        super.setup(...arguments);
        this.pollInterval = 3000; // 3 segundos entre consultas
        this.pollingTimeout = null;
        this.isPolling = false;
    }

    /**
     * Inicia el flujo de cobro enviando la intención de pago a Nave.
     */
    async send_payment_request(uuid) {
        await super.send_payment_request(...arguments);
        const line = this.pos.get_order().get_selected_paymentline();
        const payment_method_id = this.payment_method_id.id;
        const amount = line.amount;

        line.set_payment_status("waiting");

        try {
            // Manejo de reembolsos/devoluciones en la terminal
            if (amount < 0) {
                return await this._handle_refund(line, payment_method_id, amount);
            }

            // Flujo normal de cobro
            const data = await this.pos.data.silentCall(
                "pos.payment.method",
                "nave_send_payment_intent",
                [[payment_method_id], amount, uuid]
            );

            if (data && data.error) {
                this._showError(data.message, _t("Error al solicitar cobro"));
                line.set_payment_status("retry");
                return false;
            }

            // Asumimos que data devuelve el ID de la intención (ej: data.id)
            if (data && data.id) {
                line.transaction_id = data.id; // Guardamos el intent id temporalmente
                line.set_payment_status("waitingCard");
                this.isPolling = true;
                return await this._poll_payment_status(line, payment_method_id, data.id);
            } else {
                this._showError(_t("Respuesta inválida de Nave. Faltan datos."), _t("Error"));
                line.set_payment_status("retry");
                return false;
            }

        } catch (error) {
            console.error("Nave Error:", error);
            this._showError(String(error.message || error), _t("Falla de Conexión"));
            line.set_payment_status("retry");
            return false;
        }
    }

    /**
     * Maneja el reembolso (montos negativos) mandando a cancelar o reembolsar.
     */
    async _handle_refund(line, payment_method_id, amount) {
        try {
            // Asumimos que si estamos devolviendo, idealmente el usuario escaneó el ticket
            // y tenemos el refund_transaction_id guardado. Odoo en v18 maneja esto a veces
            // pero si no, intentamos un reembolso ciego si Nave lo permite.
            // Para simplificar, mandamos el llamado de reembolso con transaction dummy
            const data = await this.pos.data.silentCall(
                "pos.payment.method",
                "nave_refund_payment",
                [[payment_method_id], "REFUND-CIEGO", amount] // Se debería adaptar para recibir el trans original
            );

            if (data && data.error) {
                this._showError(data.message, _t("Error en Devolución Nave"));
                line.set_payment_status("retry");
                return false;
            }
            line.set_payment_status("done");
            return true;
        } catch (error) {
            console.error(error);
            this._showError(String(error.message || error), _t("Falla de Devolución"));
            line.set_payment_status("retry");
            return false;
        }
    }

    /**
     * Bucle de Polling: Consulta la API asíncronamente hasta que el pago se apruebe o rechace.
     */
    async _poll_payment_status(line, payment_method_id, intent_id) {
        if (!this.isPolling) {
            line.set_payment_status("retry");
            return false;
        }

        try {
            const data = await this.pos.data.silentCall(
                "pos.payment.method",
                "nave_check_payment_status",
                [[payment_method_id], intent_id]
            );

            if (data && data.error) {
                // Fallo técnico en la consulta
                this._showError(data.message, _t("Error Consultando Estado Nave"));
                line.set_payment_status("retry");
                this.isPolling = false;
                return false;
            }

            // Evaluación de estados (suponiendo estructura {status: {name: '...'}})
            const statusName = data?.status?.name || 'PENDING';

            if (statusName === 'APPROVED') {
                this.isPolling = false;
                line.set_payment_status("done");
                line.transaction_id = data.id || intent_id; // Reemplazar por el ID final
                return true;
            } else if (statusName === 'REJECTED' || statusName === 'CANCELLED') {
                this.isPolling = false;
                const reason = data?.status?.reason_code || 'Transacción fallida';
                this._showError(_t("Pago rechazado o cancelado: %s", reason), _t("Rechazo en Terminal"));
                line.set_payment_status("retry");
                return false;
            } else {
                // Estado en progreso (PENDING, PROCESSING, etc.)
                // Esperar y volver a consultar
                return new Promise((resolve) => {
                    this.pollingTimeout = setTimeout(async () => {
                        resolve(await this._poll_payment_status(line, payment_method_id, intent_id));
                    }, this.pollInterval);
                });
            }

        } catch (error) {
            console.error("Polling Error:", error);
            this._showError(_t("Pérdida de conexión con Nave durante la consulta de estado."), _t("Desconexión"));
            line.set_payment_status("retry"); // Al poner retry, el cajero puede darle a "Reintentar" o cancelar
            this.isPolling = false;
            return false;
        }
    }

    /**
     * Cancela la intención de cobro que está en curso.
     */
    async send_payment_cancel(order, uuid) {
        super.send_payment_cancel(...arguments);
        const line = this.pos.get_order().get_selected_paymentline();
        const payment_method_id = this.payment_method_id.id;
        
        // Detener polling localmente
        this.isPolling = false;
        if (this.pollingTimeout) {
            clearTimeout(this.pollingTimeout);
        }

        if (!line.transaction_id) {
            line.set_payment_status("retry");
            return true;
        }

        try {
            // Mandar petición de cancelación a la terminal Nave
            await this.pos.data.silentCall(
                "pos.payment.method",
                "nave_cancel_payment_intent",
                [[payment_method_id], line.transaction_id]
            );
            line.set_payment_status("retry");
            return true;
        } catch (error) {
            console.error("Cancel Error:", error);
            // Igual permitimos reintentar o borrar línea en el POS
            line.set_payment_status("retry");
            return true;
        }
    }

    // ──────────────────────────────────────────────
    // Helper para mostrar diálogos de error de Odoo
    // ──────────────────────────────────────────────
    _showError(msg, title) {
        if (!title) {
            title = _t("Error de Terminal Nave");
        }
        this.env.services.dialog.add(AlertDialog, {
            title: title,
            body: msg,
        });
    }
}

register_payment_method("nave", PaymentNave);
