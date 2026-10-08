/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { PaymentInterface } from "@point_of_sale/app/payment/payment_interface";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { register_payment_method } from "@point_of_sale/app/store/pos_store";
import { ask } from "@point_of_sale/app/store/make_awaitable_dialog";

// Resultado de una llamada que no respondió a tiempo. Ver _call.
const TIMED_OUT = Symbol("nave_timed_out");

// Los estados de Nave se clasifican en el backend (`nave_outcome`): de esa clasificación depende dar
// una venta por cobrada, y en el navegador no hay cómo probarla. Ver NAVE_OUTCOME_BY_STATUS en
// pos_nave/models/pos_payment_method.py.

/**
 * Interfaz de Pagos POS para Terminales Smart POS de Nave.
 * Hereda de PaymentInterface para integrarse nativamente con Odoo 18.
 */
export class PaymentNave extends PaymentInterface {
    setup() {
        super.setup(...arguments);
        this.pollInterval = 3000; // 3 segundos entre consultas
        // Respaldo por si la respuesta de la intención no trajera su plazo: un cobro nunca debe
        // quedar esperando sin tope. El plazo real lo manda el backend en cada intención.
        this.fallbackPollTimeoutMs = 300000; // 5 minutos
        // Margen que se concede por encima del plazo de la intención, para que Nave alcance a
        // informar el vencimiento antes de que cortemos por nuestra cuenta. Si cortáramos primero,
        // el cajero leería "verificá la terminal" cuando no hay nada que verificar.
        //
        // Es proporcional para que acompañe a plazos distintos —con un plazo corto, un margen fijo
        // sería más largo que el plazo mismo—, con un piso que cubra una consulta de estado y su
        // procesamiento.
        this.pollGraceRatio = 0.1;
        this.pollGraceMinMs = 10000;
        // Con cuántas consultas seguidas sin respuesta se avisa que no hay conexión. No corta el
        // cobro: la terminal sigue cobrando aunque Odoo no pueda consultarla (ver _poll).
        this.offlineNoticeAfter = 3;
        // Tope de cada llamada desde el navegador. Sin él, con el cable de red desenchufado la
        // llamada no falla sino que queda esperando, y el polling no avanza ni respeta el plazo.
        // La consulta de estado: el backend corta su llamada a Nave a los 5 s. La creación de la
        // intención: el backend espera hasta 30 s a que Nave alcance la terminal.
        this.statusTimeoutMs = 10000;
        this.intentTimeoutMs = 45000;
        // El cobro en curso. Ver _await_outcome.
        this.charge = null;
    }

    /**
     * Si es true, el cobro se dispara apenas el cajero toca el método de pago, con el saldo
     * completo. Si es false, primero puede escribir el importe: es lo que hace falta para un
     * cobro dividido. Se configura por método de pago (`nave_fast_payments`).
     */
    get fast_payments() {
        return this.payment_method_id.nave_fast_payments ?? true;
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

            // Si la línea ya tuvo una intención, primero se pregunta por ella: pudo haberse
            // aprobado sin que Odoo se enterara, por ejemplo durante un corte de red (C8).
            if (line.transaction_id) {
                const previous = await this._reconcile_previous(
                    line, payment_method_id, line.transaction_id
                );
                if (previous !== null) {
                    return previous;
                }
            }

            // Flujo normal de cobro
            const data = await this._call(
                "nave_send_payment_intent",
                [[payment_method_id], amount, uuid],
                this.intentTimeoutMs
            );

            // Sin respuesta a tiempo no sabemos si la intención llegó a crearse, y sin su
            // identificador no hay forma de consultarla después.
            if (data === TIMED_OUT) {
                this._showError(
                    _t("Nave no confirmó si el cobro llegó a la terminal. Revisá la terminal antes de reintentar: si muestra el cobro, cancelalo ahí."),
                    _t("Cobro sin confirmar")
                );
                line.set_payment_status("retry");
                return false;
            }

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
                // El id de la INTENCIÓN. Si el cobro se aprueba, _apply_payment_details lo reemplaza
                // por el del pago; si no, queda para que un reintento pregunte por esta intención.
                line.transaction_id = data.id;
                line.set_payment_status("waitingCard");
                return await this._await_outcome(
                    line, payment_method_id, data.id, data.nave_duration_seconds
                );
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
     * Espera el desenlace del cobro que se acaba de enviar a la terminal.
     *
     * Devuelve una promesa que el core espera para fijar el estado de la línea (`line.pay()`):
     * `true` la da por cobrada y `false` la deja reintentable. La promesa se resuelve una sola vez,
     * con el primero que llegue a un desenlace —el polling, la cancelación o "Forzar terminación"—,
     * y cualquier respuesta posterior sobre el mismo cobro se descarta. Sin esa regla, una
     * respuesta tardía podía pisar el desenlace: es lo que devolvió a reintentable la línea que el
     * cajero había forzado en C9.
     */
    _await_outcome(line, payment_method_id, intent_id, durationSeconds) {
        this._abandon_charge();
        return new Promise((resolve) => {
            this.charge = {
                line,
                paymentMethodId: payment_method_id,
                intentId: intent_id,
                deadline: Date.now() + this._poll_timeout_ms(durationSeconds),
                transportErrors: 0,
                timer: null,
                settled: false,
                // Mientras el cajero responde si vio la aprobación (ver force_done).
                awaitingCashier: false,
                // Cierra el aviso de falta de conexión, si está abierto.
                closeOfflineNotice: null,
                resolve,
            };
            this._poll(this.charge);
        });
    }

    /**
     * Una vuelta del polling. Nunca gira indefinidamente: corta al vencer el plazo de la intención,
     * al perder la conexión o ante un error.
     */
    async _poll(charge) {
        if (charge.settled) {
            return;
        }
        // El cajero está decidiendo si vio la aprobación: el cobro queda en sus manos. Sin esta
        // pausa, con la red caída el polling cortaba por desconexión mientras el cajero leía la
        // pregunta, y su respuesta ya no tenía efecto.
        if (charge.awaitingCashier) {
            this._schedule_next_poll(charge);
            return;
        }

        // Tope de espera: pasado el duration_time, la intención ya no es cobrable.
        if (Date.now() > charge.deadline) {
            if (this._settle(charge, false)) {
                this._showError(
                    _t("No se pudo confirmar el cobro con Nave. Tocá Volver a intentar: Odoo va a consultar primero el cobro anterior y no lo va a cobrar dos veces."),
                    _t("Cobro sin confirmar")
                );
            }
            return;
        }

        let data;
        try {
            data = await this._query_status(charge.paymentMethodId, charge.intentId);
        } catch (error) {
            // Red de seguridad: ante cualquier error inesperado cortamos en vez de dejar la
            // pantalla colgada.
            console.error("[pos_nave] Error inesperado durante el polling:", error);
            if (this._settle(charge, false)) {
                this._showError(String(error.message || error), _t("Error inesperado"));
            }
            return;
        }

        // Mientras esperábamos la respuesta, el cobro pudo resolverse por otro lado, o el cajero
        // pudo quedar a cargo.
        if (charge.settled) {
            return;
        }
        if (charge.awaitingCashier) {
            this._schedule_next_poll(charge);
            return;
        }

        // Sin respuesta —la red falla, la llamada no responde a tiempo o Nave contesta con un
        // error— el cobro NO termina: la intención existe en la terminal y el cliente puede estar
        // pagando. Darlo por fallido dejaba la línea lista para cobrar de nuevo, y en C8 Nave
        // aprobó el pago 28 s después. Sólo lo terminan Nave, el plazo o el cajero.
        if (!data || data.error) {
            charge.transportErrors += 1;
            if (charge.transportErrors >= this.offlineNoticeAfter) {
                this._show_offline_notice(charge);
            }
            this._schedule_next_poll(charge);
            return;
        }

        charge.transportErrors = 0;
        this._close_offline_notice(charge);
        if (!this._finish(charge, data)) {
            this._schedule_next_poll(charge);
        }
    }

    async _query_status(payment_method_id, intent_id) {
        const data = await this._call(
            "nave_check_payment_status",
            [[payment_method_id], intent_id],
            this.statusTimeoutMs
        );
        return data === TIMED_OUT ? false : data;
    }

    /**
     * Llama al backend con un tope de tiempo. Devuelve TIMED_OUT si no respondió a tiempo; la
     * respuesta que llegue después se descarta.
     */
    _call(method, args, timeoutMs) {
        let timer;
        const timeout = new Promise((resolve) => {
            timer = setTimeout(() => resolve(TIMED_OUT), timeoutMs);
        });
        return Promise.race([
            this.pos.data.silentCall("pos.payment.method", method, args),
            timeout,
        ]).finally(() => clearTimeout(timer));
    }

    /**
     * Avisa, una sola vez por corte, que no hay conexión y que el cobro puede seguir activo.
     *
     * Es una notificación y no un diálogo porque no hay nada que decidir: el cajero tiene que
     * esperar, y Cancelar y Forzar terminación siguen en la línea.
     */
    _show_offline_notice(charge) {
        if (charge.closeOfflineNotice) {
            return;
        }
        charge.closeOfflineNotice = this.env.services.notification.add(
            _t("El cobro puede seguir activo en la terminal: no lo cobres de nuevo ni por otro medio. Odoo lo va a confirmar cuando vuelva la conexión."),
            { title: _t("Sin conexión con Nave"), type: "warning", sticky: true }
        );
    }

    _close_offline_notice(charge) {
        if (charge.closeOfflineNotice) {
            charge.closeOfflineNotice();
            charge.closeOfflineNotice = null;
        }
    }

    /**
     * Antes de cobrar de nuevo, pregunta por la intención anterior de la línea.
     *
     * Devuelve null si corresponde crear un cobro nuevo, o el desenlace del reintento (true o
     * false, o la espera de esa misma intención). Se pregunta siempre, y no sólo cuando el
     * desenlace anterior fue desconocido: así no hace falta recordar nada que sobreviva a una
     * recarga del POS, y el costo es una consulta por reintento.
     */
    async _reconcile_previous(line, payment_method_id, intent_id) {
        const data = await this._query_status(payment_method_id, intent_id);
        if (!data || data.error) {
            this._showError(
                _t("No se pudo consultar a Nave por el cobro anterior de esta línea, y ese cobro pudo haberse aprobado. No lo cobres de nuevo: esperá a que vuelva la conexión y reintentá."),
                _t("No se puede confirmar el cobro anterior")
            );
            line.set_payment_status("retry");
            return false;
        }
        switch (data.nave_outcome) {
            case "approved":
                this._apply_payment_details(line, data, intent_id);
                this.env.services.notification.add(
                    _t("El cobro anterior de esta línea ya estaba aprobado en Nave. No se cobró de nuevo."),
                    { title: _t("Cobro confirmado"), type: "success" }
                );
                return true;
            case "rejected":
            case "disabled":
            case "expired":
                return null;
            default:
                // En curso o desconocido: se retoma la espera de esa misma intención. No sabemos
                // cuándo se creó, así que se usa el plazo de respaldo; Nave la termina antes.
                line.set_payment_status("waitingCard");
                return this._await_outcome(line, payment_method_id, intent_id, null);
        }
    }

    /**
     * Termina el cobro si Nave ya informó un desenlace. Devuelve false si todavía hay que esperar.
     */
    _finish(charge, data) {
        if (charge.settled) {
            return true;
        }
        if (data.nave_outcome === "approved") {
            this._apply_payment_details(charge.line, data, charge.intentId);
            this._settle(charge, true);
            return true;
        }
        const notice = this._final_notice(data, charge.intentId);
        if (notice) {
            if (this._settle(charge, false)) {
                this._showError(notice.body, notice.title);
            }
            return true;
        }
        if (data.nave_outcome === "unknown") {
            // El backend ya lo registró. Seguimos esperando en vez de cortar un cobro que podría
            // estar en curso, y nunca lo damos por cobrado.
            console.warn("[pos_nave] Estado no contemplado devuelto por Nave:", data?.status?.name, data);
        }
        return false;
    }

    /**
     * El aviso de un cobro que terminó sin cobrarse, o null si el cobro no terminó o salió bien.
     */
    _final_notice(data, intent_id) {
        switch (data.nave_outcome) {
            case "rejected":
                return {
                    title: _t("Pago rechazado"),
                    body: this._outcome_notice(
                        data, intent_id,
                        _t("El pago fue rechazado."),
                        _t("Podés reintentar o cobrar con otro medio.")
                    ),
                };
            case "disabled":
                return {
                    title: _t("Cobro dado de baja"),
                    body: this._outcome_notice(
                        data, intent_id,
                        _t("El cobro ya no está disponible."),
                        _t("Generá un cobro nuevo.")
                    ),
                };
            case "expired":
                return {
                    title: _t("Cobro expirado"),
                    body: this._outcome_notice(
                        data, intent_id,
                        _t("La intención de cobro expiró sin recibir el pago."),
                        _t("Generá un cobro nuevo.")
                    ),
                };
            default:
                return null;
        }
    }

    /**
     * Resuelve el cobro una sola vez. Devuelve false si ya estaba resuelto, para que quien llegue
     * tarde no muestre un segundo aviso.
     */
    _settle(charge, isPaymentSuccessful) {
        if (!charge || charge.settled) {
            return false;
        }
        charge.settled = true;
        clearTimeout(charge.timer);
        this._close_offline_notice(charge);
        if (this.charge === charge) {
            this.charge = null;
        }
        if (!isPaymentSuccessful) {
            charge.line.set_payment_status("retry");
        }
        charge.resolve(isPaymentSuccessful);
        return true;
    }

    /**
     * Deja de consultar sin resolver el cobro. La línea queda como estaba; si después se fuerza la
     * terminación, se consulta a Nave igual (ver force_done).
     */
    _abandon_charge() {
        if (this.charge) {
            this.charge.settled = true;
            clearTimeout(this.charge.timer);
            this._close_offline_notice(this.charge);
            this.charge = null;
        }
    }

    /**
     * "Forzar terminación" sobre una línea de Nave: decide lo que diga Nave, no el botón.
     *
     * El botón del core da la línea por cobrada sin preguntarle nada al medio de pago. Está pensado
     * para terminales locales que pierden la conexión; con Nave el estado siempre se puede
     * consultar. En C9, tocarlo mientras la terminal esperaba la tarjeta dejó una venta validable
     * sin cobro.
     *
     * Devuelve true sólo si hay que seguir con el comportamiento del core, que es marcar la línea y
     * validar la venta. Con un cobro en curso nunca hace falta: se lo resuelve con el desenlace, y
     * el cobro aprobado sigue el mismo camino que uno detectado por el polling.
     */
    async force_done(line) {
        if (line.get_payment_status() === "waiting") {
            this._showError(
                _t("El cobro todavía se está enviando a la terminal. Esperá a que la terminal pida la tarjeta."),
                _t("El cobro se está enviando")
            );
            return false;
        }

        const charge = this.charge && this.charge.line === line ? this.charge : null;
        const intent_id = charge ? charge.intentId : line.transaction_id;
        const payment_method_id = this.payment_method_id.id;

        let data = false;
        if (intent_id) {
            try {
                data = await this._query_status(payment_method_id, intent_id);
            } catch (error) {
                console.error("[pos_nave] No se pudo consultar a Nave al forzar la terminación:", error);
                data = false;
            }
        }
        if (charge?.settled) {
            // El polling llegó primero mientras consultábamos.
            return false;
        }

        if (!data || data.error) {
            if (charge) {
                charge.awaitingCashier = true;
            }
            const confirmed = await ask(this.env.services.dialog, {
                title: _t("No se pudo consultar a Nave"),
                body: _t(
                    "Odoo no pudo confirmar el cobro con Nave. Marcalo como cobrado sólo si viste la " +
                    "aprobación en la terminal o en el cupón."
                ),
                confirmLabel: _t("Vi la aprobación"),
                cancelLabel: _t("Volver"),
            });
            if (charge) {
                charge.awaitingCashier = false;
            }
            if (!confirmed) {
                if (charge) {
                    // Se reanuda desde cero: los fallos de antes de la pregunta no cuentan.
                    charge.transportErrors = 0;
                }
                return false;
            }
            if (charge) {
                this._settle(charge, true);
                return false;
            }
            return true;
        }

        if (charge) {
            if (!this._finish(charge, data)) {
                this._show_still_waiting(data, intent_id);
            }
            return false;
        }

        // Sin un cobro en curso en esta pantalla, por ejemplo después de recargar el POS.
        if (data.nave_outcome === "approved") {
            this._apply_payment_details(line, data, intent_id);
            return true;
        }
        const notice = this._final_notice(data, intent_id);
        if (notice) {
            line.set_payment_status("retry");
            this._showError(notice.body, notice.title);
            return false;
        }
        this._show_still_waiting(data, intent_id);
        return false;
    }

    _show_still_waiting(data, intent_id) {
        this._showError(
            this._outcome_notice(
                data, intent_id,
                _t("La terminal todavía está esperando la tarjeta y Nave no confirmó ningún cobro."),
                _t("Podés esperar o cancelar el cobro.")
            ),
            _t("El cobro sigue en curso")
        );
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
    _schedule_next_poll(charge) {
        charge.timer = setTimeout(() => this._poll(charge), this.pollInterval);
    }

    /**
     * Arma el aviso de un cobro que no se completó: qué pasó, qué hacer y los datos para soporte.
     *
     * Qué pasó sale del mensaje que Nave publica para el motivo, que el backend ya resolvió. Si
     * Nave no publica uno, se usa `situation`, que describe el desenlace sin atribuirle una causa.
     * El código no va nunca en la explicación: va aparte, rotulado, para que el cajero se lo pueda
     * dictar a la soporte sin que se lea como la causa de lo que pasó.
     */
    _outcome_notice(data, intent_id, situation, action) {
        const reason = data?.nave_reason || {};
        const lines = [`${reason.message || situation} ${action}`];

        const support = [];
        if (reason.code) {
            support.push(_t("Código: %s", reason.code));
        }
        if (data?.nave_payment_id) {
            support.push(_t("Pago: %s", data.nave_payment_id));
        }
        support.push(_t("Intención: %s", data?.id || intent_id));

        lines.push("", _t("Para soporte:"), ...support);
        return lines.join("\n");
    }

    /**
     * Cuánto esperar como mucho, derivado del plazo con el que se creó la intención.
     *
     * El tope local es la red para cuando Nave no contesta: tiene que vencer *después* del plazo
     * de la intención, nunca antes, para que el aviso de vencimiento le gane y el cajero entienda
     * qué pasó.
     */
    _poll_timeout_ms(durationSeconds) {
        if (!durationSeconds || durationSeconds <= 0) {
            return this.fallbackPollTimeoutMs;
        }
        const durationMs = durationSeconds * 1000;
        return durationMs + Math.max(durationMs * this.pollGraceRatio, this.pollGraceMinMs);
    }

    /**
     * Hook de PaymentInterface que el core documenta "al cerrar la pantalla de pago", pero que
     * Odoo 18 no llama nunca: no tiene llamadores en point_of_sale ni en enterprise. Así, tocar
     * "Regresar" no corta el seguimiento del cobro, y conviene que sea así: en C7c el cliente pagó
     * con el cajero en productos y el pago se registró igual (plan de homologación §3.38). Si una
     * versión futura lo llamara, el cobro quedaría sin seguimiento y la línea esperando.
     */
    close() {
        this._abandon_charge();
        super.close(...arguments);
    }

    /**
     * Cancela la intención de cobro que está en curso.
     */
    async send_payment_cancel(order, uuid) {
        super.send_payment_cancel(...arguments);
        const line = this.pos.get_order().get_selected_paymentline();
        const payment_method_id = this.payment_method_id.id;

        // El cobro termina acá: lo que responda Nave después sobre esta intención ya no cuenta.
        if (this.charge && this.charge.line === line) {
            this._settle(this.charge, false);
        }

        if (!line.transaction_id) {
            line.set_payment_status("retry");
            return true;
        }

        const data = await this.pos.data.silentCall(
            "pos.payment.method",
            "nave_cancel_payment_intent",
            [[payment_method_id], line.transaction_id]
        );

        // Si Nave no confirma la baja, hay que decirlo: el cajero daría por cancelado un cobro que
        // sigue vivo en la terminal hasta que vence, y si el cliente apoya la tarjeta en ese lapso,
        // se cobra. Hasta C4, Nave rechazaba todas las bajas por el texto del motivo (ver
        // NAVE_CANCEL_REASON en el backend).
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
