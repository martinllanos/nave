/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { PaymentInterface } from "@point_of_sale/app/payment/payment_interface";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { register_payment_method } from "@point_of_sale/app/store/pos_store";

/**
 * Estados que puede devolver Nave al consultar el recurso.
 *
 * Importante: el polling consulta GET /api/payment_requests/{id}, que devuelve el estado de la
 * INTENCIÓN, cuyo vocabulario es distinto del estado del PAGO (GET /ranty-payments/payments/{id}).
 * Un cobro exitoso en la intención es SUCCESS_PROCESSED, no APPROVED. Aceptamos ambos vocabularios
 * para ser tolerantes si el endpoint devolviera el del pago.
 */
const NAVE_STATUS = {
    // Cobro exitoso
    SUCCESS: ["SUCCESS_PROCESSED", "APPROVED"],
    // Cobro rechazado por el emisor o la terminal
    FAILURE: ["FAILURE_PROCESSED", "REJECTED"],
    // Intención dada de baja (por el cajero en la terminal, por batería, por timeout...)
    DISABLED: ["DISABLED", "CANCELLED"],
    // La intención superó su duration_time sin cobrarse
    EXPIRED: ["EXPIRED"],
    // Bloqueada por seguridad o fraude
    BLOCKED: ["BLOCKED"],
    // Todavía en curso: seguimos consultando
    IN_PROGRESS: ["PENDING", "PROCESSED", "PROCESSING"],
};

/**
 * Interfaz de Pagos POS para Terminales Smart POS de Nave.
 * Hereda de PaymentInterface para integrarse nativamente con Odoo 18.
 */
export class PaymentNave extends PaymentInterface {
    setup() {
        super.setup(...arguments);
        this.pollInterval = 3000; // 3 segundos entre consultas
        // Tope del bucle de polling. Debe acompañar al duration_time que manda el backend
        // (pos_payment_method.py), porque pasado ese plazo la intención ya no es cobrable.
        this.pollTimeoutMs = 300000; // 5 minutos
        // Cuántos fallos de transporte seguidos toleramos antes de cortar.
        this.maxTransportErrors = 3;
        this.pollingTimeout = null;
        this.pollDeadline = 0;
        this.transportErrors = 0;
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

            // silentCall devuelve false ante cualquier excepción del servidor (permisos, token
            // Auth0 vencido, error de red). Hay que distinguirlo de una respuesta válida de Nave.
            if (!data) {
                this._showError(
                    _t("No se pudo contactar al servidor de Odoo para iniciar el cobro. Revisá la conexión y reintentá."),
                    _t("Error de conexión")
                );
                line.set_payment_status("retry");
                return false;
            }

            if (data.error) {
                this._showError(data.message, _t("Error al solicitar cobro"));
                line.set_payment_status("retry");
                return false;
            }

            if (data.id) {
                // OJO: esto es el id de la INTENCIÓN (payment_request_id), no el payment_id que
                // pide DELETE /api/payments/{payment_id} para devolver. Pendiente de resolver.
                line.transaction_id = data.id;
                line.set_payment_status("waitingCard");
                this.isPolling = true;
                this.transportErrors = 0;
                this.pollDeadline = Date.now() + this.pollTimeoutMs;
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
     * Bucle de Polling: consulta la intención hasta llegar a un estado terminal, agotar el
     * tiempo de la intención, o perder la conexión. Nunca gira indefinidamente.
     */
    async _poll_payment_status(line, payment_method_id, intent_id) {
        if (!this.isPolling) {
            line.set_payment_status("retry");
            return false;
        }

        // Tope de espera: pasado el duration_time, la intención ya no es cobrable.
        if (Date.now() > this.pollDeadline) {
            this._stop_polling();
            this._showError(
                _t("Se agotó el tiempo de espera del cobro. Verificá el estado en la terminal antes de reintentar."),
                _t("Tiempo agotado")
            );
            line.set_payment_status("retry");
            return false;
        }

        try {
            const data = await this.pos.data.silentCall(
                "pos.payment.method",
                "nave_check_payment_status",
                [[payment_method_id], intent_id]
            );

            // silentCall devuelve false ante cualquier excepción del servidor. Toleramos algunos
            // fallos seguidos (un corte breve de red) antes de darnos por vencidos.
            if (!data) {
                this.transportErrors += 1;
                if (this.transportErrors >= this.maxTransportErrors) {
                    this._stop_polling();
                    this._showError(
                        _t("Se perdió la conexión con el servidor mientras se consultaba el cobro. Verificá el estado en la terminal antes de reintentar."),
                        _t("Desconexión")
                    );
                    line.set_payment_status("retry");
                    return false;
                }
                return await this._schedule_next_poll(line, payment_method_id, intent_id);
            }

            if (data.error) {
                this._stop_polling();
                this._showError(data.message, _t("Error consultando estado en Nave"));
                line.set_payment_status("retry");
                return false;
            }

            this.transportErrors = 0;
            const statusName = String(data?.status?.name || "").toUpperCase();
            const reason = data?.status?.reason_name || data?.status?.reason_code || "";

            if (NAVE_STATUS.SUCCESS.includes(statusName)) {
                this._stop_polling();
                this._apply_payment_details(line, data, intent_id);
                line.set_payment_status("done");
                return true;
            }

            if (NAVE_STATUS.FAILURE.includes(statusName)) {
                this._stop_polling();
                this._showError(
                    _t("Pago rechazado: %s", reason || _t("sin motivo informado")),
                    _t("Rechazo en terminal")
                );
                line.set_payment_status("retry");
                return false;
            }

            if (NAVE_STATUS.DISABLED.includes(statusName)) {
                this._stop_polling();
                this._showError(
                    reason
                        ? _t("El cobro fue dado de baja: %s", reason)
                        : _t("El cobro fue dado de baja en la terminal."),
                    _t("Cobro cancelado")
                );
                line.set_payment_status("retry");
                return false;
            }

            if (NAVE_STATUS.EXPIRED.includes(statusName)) {
                this._stop_polling();
                this._showError(
                    _t("La intención de cobro expiró sin recibir el pago. Generá un cobro nuevo."),
                    _t("Cobro expirado")
                );
                line.set_payment_status("retry");
                return false;
            }

            if (NAVE_STATUS.BLOCKED.includes(statusName)) {
                this._stop_polling();
                this._showError(
                    _t("Nave bloqueó la operación por motivos de seguridad. Contactá a Nave antes de reintentar."),
                    _t("Operación bloqueada")
                );
                line.set_payment_status("retry");
                return false;
            }

            if (!NAVE_STATUS.IN_PROGRESS.includes(statusName)) {
                // Estado no contemplado: lo dejamos registrado para poder mapearlo después, pero
                // seguimos esperando en vez de cortar un cobro que podría estar en curso.
                console.warn("[pos_nave] Estado no contemplado devuelto por Nave:", statusName, data);
            }

            return await this._schedule_next_poll(line, payment_method_id, intent_id);

        } catch (error) {
            // Red de seguridad: ante cualquier error inesperado cortamos el bucle en vez de
            // dejarlo vivo con la pantalla colgada.
            console.error("[pos_nave] Error inesperado durante el polling:", error);
            this._stop_polling();
            this._showError(String(error.message || error), _t("Error inesperado"));
            line.set_payment_status("retry");
            return false;
        }
    }

    /**
     * Vuelca en la línea de pago los datos del cobro: el identificador que sirve para devolver,
     * y los datos de la tarjeta que van impresos en el ticket.
     */
    _apply_payment_details(line, data, intent_id) {
        // El payment_id identifica al pago y es el que espera el endpoint de devolución.
        // El id de la intención no sirve para eso.
        line.transaction_id = data.nave_payment_id || data.id || intent_id;

        const payment = data.nave_payment;
        if (!payment) {
            // El cobro salió bien igual; sólo nos quedamos sin los datos de la tarjeta.
            return;
        }

        const method = payment.payment_method || {};
        const authData = payment.transactions?.[0]?.auth_data || {};

        line.card_brand = method.card_brand || "";
        line.card_type = method.card_type || "";
        line.card_no = method.card_last4 || "";
        line.cardholder_name = method.card_holder_name || "";
        line.payment_method_issuer_bank = method.issuer || "";
        line.payment_method_payment_mode = payment.payment_input || "";
        line.payment_ref_no = payment.payment_code || "";
        line.payment_method_authcode = authData.auth_id || "";

        line.set_receipt_info(this._format_receipt(payment, method, authData));
    }

    /**
     * Arma el texto que se imprime en el ticket. Nave pide que figuren los últimos cuatro
     * dígitos y el número de cupón y lote.
     */
    _format_receipt(payment, method, authData) {
        const rows = [];
        const wallet = payment.wallet?.name || method.wallet_name;
        if (wallet) {
            rows.push(_t("Billetera: %s", wallet));
        }
        if (method.card_brand || method.card_last4) {
            rows.push(_t("Tarjeta: %s ****%s", method.card_brand || "", method.card_last4 || ""));
        }
        if (method.card_type) {
            rows.push(_t("Tipo: %s", method.card_type));
        }
        if (payment.payment_code) {
            rows.push(_t("Cupón: %s", payment.payment_code));
        }
        if (authData.auth_id) {
            rows.push(_t("Autorización: %s", authData.auth_id));
        }
        if (authData.ticket?.batch) {
            rows.push(_t("Lote: %s", authData.ticket.batch));
        }
        const plan = method.installment_plan;
        if (plan && plan.installments > 1) {
            rows.push(_t("Cuotas: %s", plan.installments));
        }
        if (method.issuer) {
            rows.push(_t("Emisor: %s", method.issuer));
        }
        return rows.length ? "\n" + rows.join("\n") : "";
    }

    /**
     * Agenda la próxima consulta respetando el intervalo de polling.
     */
    _schedule_next_poll(line, payment_method_id, intent_id) {
        return new Promise((resolve) => {
            this.pollingTimeout = setTimeout(async () => {
                resolve(await this._poll_payment_status(line, payment_method_id, intent_id));
            }, this.pollInterval);
        });
    }

    /**
     * Corta el bucle y limpia el temporizador pendiente.
     */
    _stop_polling() {
        this.isPolling = false;
        if (this.pollingTimeout) {
            clearTimeout(this.pollingTimeout);
            this.pollingTimeout = null;
        }
    }

    /**
     * Se llama al salir de la pantalla de pago. Sin esto el temporizador seguía vivo
     * consultando a Nave después de que el cajero abandonó la pantalla.
     */
    close() {
        this._stop_polling();
        super.close(...arguments);
    }

    /**
     * Cancela la intención de cobro que está en curso.
     */
    async send_payment_cancel(order, uuid) {
        super.send_payment_cancel(...arguments);
        const line = this.pos.get_order().get_selected_paymentline();
        const payment_method_id = this.payment_method_id.id;

        // Detener polling localmente
        this._stop_polling();

        if (!line.transaction_id) {
            line.set_payment_status("retry");
            return true;
        }

        const data = await this.pos.data.silentCall(
            "pos.payment.method",
            "nave_cancel_payment_intent",
            [[payment_method_id], line.transaction_id]
        );

        // Nave rechaza la baja de las intenciones de terminal: su catálogo sólo admite dar de baja
        // payment_link, dynamic_qr y static_qr. Callarlo sería peor que el error: el cajero daría
        // por cancelado un cobro que sigue vivo hasta que expira, y si el cliente apoya la tarjeta
        // en ese lapso, se cobra.
        if (!data || data.error) {
            this._showError(
                _t(
                    "Odoo dejó de esperar el cobro, pero Nave no confirmó la baja: el cobro puede " +
                    "seguir activo en la terminal. Cancelalo desde el equipo antes de reintentar.%s",
                    data && data.message ? `\n\n${data.message}` : ""
                ),
                _t("La terminal puede seguir cobrando")
            );
        }

        // Se devuelve true en todos los casos a propósito: con false, el POS deja la línea en
        // "esperando tarjeta" (ver sendPaymentCancel del core) y el polling ya está detenido, con
        // lo cual el cajero queda trabado sin nada que lo saque de ahí. Es preferible liberar la
        // pantalla y avisar por diálogo qué pasó realmente.
        line.set_payment_status("retry");
        return true;
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

// Nave Point y QR interoperable comparten toda la mecánica del cliente: intención, polling,
// cancelación y estados. Lo único que cambia es el endpoint y el host, y eso lo resuelve el
// backend a partir del método de pago, así que se registra la misma clase para los dos.
register_payment_method("nave", PaymentNave);
register_payment_method("nave_qr", PaymentNave);
