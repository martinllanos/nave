/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { PaymentNave } from "@pos_nave/app/payment_nave";

// "Forzar terminación" del core marca la línea como cobrada sin preguntarle nada al medio de pago.
// En una línea de Nave se consulta a Nave primero (ver PaymentNave.force_done); el resto de los
// medios de pago sigue igual.
patch(PaymentScreen.prototype, {
    async sendForceDone(line) {
        const terminal = line.payment_method_id.payment_terminal;
        if (terminal instanceof PaymentNave && !(await terminal.force_done(line))) {
            return;
        }
        return super.sendForceDone(...arguments);
    },
});
