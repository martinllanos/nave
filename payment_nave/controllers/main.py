# -*- coding: utf-8 -*-

import json
import logging
from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class PaymentNaveController(http.Controller):

    @http.route('/payment/nave/webhook', type='http', auth='public', methods=['POST', 'OPTIONS'], csrf=False)
    def nave_webhook(self):
        """
        Endpoint S2S (Server-to-Server) público que recibe las notificaciones de estado asíncronas de Nave.
        Procesa el payload y actualiza la transacción correspondiente de forma segura.
        """
        if request.httprequest.method == 'OPTIONS':
            headers = [
                ('Content-Type', 'text/plain'),
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'POST, OPTIONS'),
                ('Access-Control-Allow-Headers', 'Content-Type, Authorization'),
            ]
            return request.make_response("", headers=headers, status=200)

        try:
            data = request.get_json_data() or json.loads(request.httprequest.data.decode('utf-8'))
        except Exception as e:
            # La falla es de quien manda el aviso, no de Odoo: es una advertencia, no un error.
            _logger.warning("[payment_nave] Webhook con un JSON que no se pudo leer: %s", e)
            return request.make_response("Invalid JSON", [('Content-Type', 'text/plain')], status=400)

        _logger.info("Recibido Webhook de Nave: %s", json.dumps(data) if isinstance(data, dict) else data)

        if not isinstance(data, dict):
            return request.make_response("Bad Request", [('Content-Type', 'text/plain')], status=400)

        # Verificar datos requeridos
        external_payment_id = data.get('external_payment_id')
        payment_id = data.get('payment_id')
        if not external_payment_id or not payment_id:
            _logger.warning("Webhook omitido: Faltan campos clave (external_payment_id o payment_id).")
            return request.make_response("Bad Request", [('Content-Type', 'text/plain')], status=400)

        # El código de respuesta le dice a Nave si tiene sentido reintentar:
        # - 400: el aviso no trae lo mínimo para procesarlo (arriba).
        # - 200: se aplicó, o no corresponde a ninguna transacción del sitio y ningún reintento lo va
        #   a cambiar. Nave manda a esta URL los pagos de todo el comercio, también los del punto de
        #   venta, que se resuelven consultando la intención y no necesitan el aviso. Es lo que hace
        #   el core con Stripe (payment_stripe/controllers/main.py).
        # - 500: falló algo que un reintento puede resolver, como la consulta del pago a Nave.
        #
        # El savepoint descarta lo que el procesamiento haya escrito antes de fallar: si no, el
        # cursor se confirma igual al devolver la respuesta, y el reintento encontraría la
        # transacción a medio aplicar. Se usa sudo() porque es una llamada S2S pública.
        try:
            with request.env.cr.savepoint():
                request.env['payment.transaction'].sudo()._handle_notification_data('nave', data)
        except ValidationError as e:
            # Hay dos casos: el aviso no es de ninguna transacción del sitio (por ejemplo, un cobro del
            # punto de venta), o es de una transacción pero no se aplica (un pago ajeno, §3.44). El
            # segundo ya dejó su advertencia; mencionar el punto de venta ahí confundía.
            existe = request.env['payment.transaction'].sudo().search_count([
                ('reference', '=', external_payment_id), ('provider_code', '=', 'nave'),
            ])
            if existe:
                _logger.info(
                    "[payment_nave] Aviso de Nave que no se aplica; se acusa sin aplicar. Referencia: %s. "
                    "Pago: %s. Motivo: %s", external_payment_id, payment_id, e,
                )
            else:
                _logger.info(
                    "[payment_nave] Aviso de Nave que no corresponde a ninguna transacción del sitio "
                    "(puede ser un cobro del punto de venta); se acusa sin aplicar. Referencia: %s. "
                    "Pago: %s. Motivo: %s", external_payment_id, payment_id, e,
                )
        except Exception as e:
            _logger.error("Error al procesar la notificación del Webhook para %s: %s", external_payment_id, e)
            return request.make_response("Internal Server Error", [('Content-Type', 'text/plain')], status=500)

        return request.make_response("OK", [('Content-Type', 'text/plain')], status=200)

    @http.route('/payment/nave/return', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def nave_return(self, **kwargs):
        """
        Punto de retorno para el cliente tras completar o cancelar el pago en el Checkout de Nave.
        Redirige al flujo estándar de Odoo (/payment/status) para mostrar el cartel interactivo.
        """
        _logger.info("Cliente retornado desde Nave Checkout. Parámetros recibidos: %s", kwargs)
        # Redireccionar directamente al panel de estado de cobros de Odoo
        return request.redirect('/payment/status')
