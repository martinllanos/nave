# -*- coding: utf-8 -*-

import json
import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PaymentNaveController(http.Controller):

    @http.route('/payment/nave/webhook', type='json', auth='public', methods=['POST'], csrf=False)
    def nave_webhook(self):
        """
        Endpoint S2S (Server-to-Server) público que recibe las notificaciones de estado asíncronas de Nave.
        Procesa el payload y actualiza la transacción correspondiente de forma segura.
        """
        try:
            # En Odoo 17/18, type='json' parsea el json automáticamente y lo expone en request.dispatcher.jsonrequest
            data = request.dispatcher.jsonrequest
        except Exception as e:
            _logger.error("Error al recibir o parsear el json del webhook: %s", e)
            return http.Response("Invalid JSON", status=400)

        _logger.info("Recibido Webhook de Nave: %s", json.dumps(data))

        # Verificar datos requeridos
        external_payment_id = data.get('external_payment_id')
        payment_id = data.get('payment_id')
        if not external_payment_id or not payment_id:
            _logger.warning("Webhook omitido: Faltan campos clave (external_payment_id o payment_id).")
            return http.Response("Bad Request", status=400)

        # Delegar el procesamiento al modelo transaction
        # Usar sudo() ya que es una llamada S2S pública
        try:
            request.env['payment.transaction'].sudo()._handle_notification('nave', data)
        except Exception as e:
            _logger.error("Error al procesar la notificación del Webhook para %s: %s", external_payment_id, e)
            # Responder con HTTP 500 para forzar el reintento de Nave si hubo una falla del lado de Odoo
            return http.Response("Internal Server Error", status=500)

        # Responder HTTP 200 de forma inmediata conforme a la especificación técnica de Nave
        return {}

    @http.route('/payment/nave/return', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def nave_return(self, **kwargs):
        """
        Punto de retorno para el cliente tras completar o cancelar el pago en el Checkout de Nave.
        Redirige al flujo estándar de Odoo (/payment/status) para mostrar el cartel interactivo.
        """
        _logger.info("Cliente retornado desde Nave Checkout. Parámetros recibidos: %s", kwargs)
        # Redireccionar directamente al panel de estado de cobros de Odoo
        return request.redirect('/payment/status')
