# -*- coding: utf-8 -*-

import logging
import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError

_logger = logging.getLogger(__name__)


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    def _get_payment_terminal_selection(self):
        return super()._get_payment_terminal_selection() + [('nave', 'Nave')]

    nave_terminal_id = fields.Char(
        string='ID de Terminal Nave',
        help='El identificador único de la terminal física de Nave (Device ID / Terminal ID).',
        copy=False
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Carga los campos necesarios en el frontend (JS/OWL)."""
        params = super()._load_pos_data_fields(config_id)
        params += ['nave_terminal_id']
        return params

    def _get_nave_payment_provider(self):
        """Helper para obtener el proveedor de Nave activo de la compañía actual."""
        # Se requiere check_company=True indirectamente asegurando que el provider
        # pertenece a la compañía del entorno actual.
        provider = self.env['payment.provider'].search([
            ('code', '=', 'nave'),
            ('state', '!=', 'disabled'),
            ('company_id', '=', self.company_id.id or self.env.company.id)
        ], limit=1)

        if not provider:
            raise UserError(_("No se encontró un proveedor de pago Nave configurado para la compañía %s", self.env.company.name))

        return provider

    @api.model
    def nave_send_payment_intent(self, payment_method_id, amount, reference):
        """
        Llamada desde el JS del POS para enviar una solicitud de cobro a la terminal Smart POS.
        Endpoint: POST /api/payment_request/smart_pos
        """
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("No tienes permisos para enviar solicitudes a Nave."))

        payment_method = self.browse(payment_method_id)

        provider = payment_method._get_nave_payment_provider()
        token = provider._nave_get_access_token()
        base_url = provider._nave_get_api_url('smart_pos')

        api_url = f"{base_url}/api/payment_request/smart_pos"
        formatted_amount = f"{amount:.2f}"

        # El ID de la terminal (device_id) se envía en seller.pos_id, usando la terminal del método o el POS ID global
        pos_id = payment_method.nave_terminal_id or provider.nave_pos_id

        if not pos_id:
            raise UserError(_("No se ha configurado un ID de terminal Nave ni en el método de pago ni en el proveedor."))

        payload = {
            'external_payment_id': str(reference)[:36],
            'seller': {
                'pos_id': pos_id,
            },
            'transactions': [
                {
                    'amount': {
                        'currency': 'ARS',
                        'value': formatted_amount,
                    },
                    'products': [
                        {
                            'name': f'Venta POS {reference[:10]}',
                            'description': 'Cobro en Punto de Venta Odoo',
                            'quantity': 1,
                            'unit_price': {
                                'currency': 'ARS',
                                'value': formatted_amount,
                            }
                        }
                    ]
                }
            ],
            'duration_time': 300
        }

        headers = {
            'Authorization': f"Bearer {token}",
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        _logger.info("[pos_nave] Enviando solicitud Smart POS a la terminal %s (Ref: %s)", pos_id, reference)

        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data
        except requests.exceptions.RequestException as e:
            _logger.error("[pos_nave] Error enviando pago a la terminal Nave: %s", e)
            return {'error': True, 'message': self._nave_error_message(e)}

    @api.model
    def nave_check_payment_status(self, payment_method_id, intent_id):
        """
        Llamada desde el JS del POS (Polling) para consultar el estado de la intención de pago Smart POS.
        Endpoint: GET /api/payment_requests/{payment_request_id}

        OJO: este endpoint devuelve el estado de la INTENCIÓN (PENDING, PROCESSED,
        SUCCESS_PROCESSED, FAILURE_PROCESSED, DISABLED, EXPIRED, BLOCKED), que NO es el mismo
        vocabulario que el del PAGO (APPROVED, REJECTED, ...) que devuelve
        GET /ranty-payments/payments/{payment_id}. El mapeo vive en el JS (NAVE_STATUS).
        """
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("No tienes permisos para consultar solicitudes a Nave."))

        payment_method = self.browse(payment_method_id)
        provider = payment_method._get_nave_payment_provider()
        token = provider._nave_get_access_token()
        base_url = provider._nave_get_api_url('smart_pos')

        api_url = f"{base_url}/api/payment_requests/{intent_id}"

        headers = {
            'Authorization': f"Bearer {token}",
            'Accept': 'application/json',
        }

        try:
            response = requests.get(api_url, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            _logger.debug("[pos_nave] Estado de intención %s: %s", intent_id, data)

            # La intención expone el pago asociado en payment_attempts. Lo adjuntamos para que el
            # POS pueda guardar el payment_id correcto e imprimir los datos de la tarjeta sin
            # tener que hacer otra vuelta al servidor.
            payment_id = self._nave_extract_payment_id(data)
            if payment_id:
                data['nave_payment_id'] = payment_id
                payment = self._nave_fetch_payment(provider, payment_id)
                if payment:
                    data['nave_payment'] = payment
            return data
        except requests.exceptions.RequestException as e:
            _logger.error("[pos_nave] Error consultando estado en Nave: %s", e)
            return {'error': True, 'message': self._nave_error_message(e)}

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers internos
    # ──────────────────────────────────────────────────────────────────────────

    def _nave_error_message(self, exc):
        """ Extrae un mensaje legible de una excepción de `requests` contra la API de Nave. """
        if getattr(exc, 'response', None) is None:
            return str(exc)
        try:
            response_json = exc.response.json()
            if isinstance(response_json, dict):
                msg = (
                    response_json.get('message')
                    or response_json.get('error')
                    or response_json.get('description')
                )
                detail = response_json.get('detail')
                if msg and detail:
                    return f"{msg}: {detail} (HTTP {exc.response.status_code})"
                if msg:
                    return f"{msg} (HTTP {exc.response.status_code})"
        except Exception:
            pass
        try:
            return f"{exc.response.text[:200]} (HTTP {exc.response.status_code})"
        except Exception:
            return str(exc)

    def _nave_extract_payment_id(self, intent_data):
        """ Devuelve el `payment_id` del último intento de pago de una intención, o False.

        La intención expone los pagos asociados en `payment_attempts.payments`. Ese `payment_id` es
        el que identifica al pago propiamente dicho: es el que hay que usar para consultar
        `/ranty-payments/payments/{id}` y el que espera el endpoint de devolución. El `id` de la
        intención NO sirve para eso.
        """
        attempts = (intent_data or {}).get('payment_attempts') or {}
        payments = attempts.get('payments') or []
        if not payments:
            return False
        return payments[-1].get('payment_id') or False

    def _nave_fetch_payment(self, provider, payment_id):
        """ GET /ranty-payments/payments/{payment_id}. Devuelve el pago o False si no se pudo. """
        token = provider._nave_get_access_token()
        base_url = provider._nave_get_api_url('smart_pos')
        api_url = f"{base_url}/ranty-payments/payments/{payment_id}"
        headers = {
            'Authorization': f"Bearer {token}",
            'Accept': 'application/json',
        }
        try:
            response = requests.get(api_url, headers=headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # No es fatal: la intención ya nos dijo que el cobro salió bien. Sin estos datos el
            # ticket sale sin marca ni últimos 4, pero la venta se cierra igual.
            _logger.warning(
                "[pos_nave] No se pudieron recuperar los datos del pago %s: %s",
                payment_id, self._nave_error_message(e),
            )
            return False

    @api.model
    def nave_cancel_payment_intent(self, payment_method_id, intent_id):
        """
        Llamada desde el JS del POS para dar de baja la intención de pago antes de cobrarla.
        Endpoint: DELETE /api/payment_requests/{payment_request_id}
        """
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("No tienes permisos para cancelar solicitudes a Nave."))

        payment_method = self.browse(payment_method_id)
        provider = payment_method._get_nave_payment_provider()
        token = provider._nave_get_access_token()
        base_url = provider._nave_get_api_url('smart_pos')

        api_url = f"{base_url}/api/payment_requests/{intent_id}"

        headers = {
            'Authorization': f"Bearer {token}",
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        # 'disabled_from_saas' es el código correcto según el catálogo de bajas de Nave
        # ("Cancelación desde el SAAS por motivo externo"): la baja la origina Odoo, no la terminal.
        # No confundir con 'manual_disabled_by_user', que es la baja hecha DENTRO de la terminal.
        payload = {
            'reason': {
                'code': 'disabled_from_saas',
                'description': 'Cancelado desde Odoo POS'
            }
        }

        try:
            response = requests.delete(api_url, json=payload, headers=headers, timeout=5)
            response.raise_for_status()
            return {'success': True}
        except requests.exceptions.RequestException as e:
            _logger.error("[pos_nave] Error cancelando intención en Nave: %s", e)
            return {'error': True, 'message': str(e)}

    @api.model
    def nave_refund_payment(self, payment_method_id, transaction_id, amount):
        """
        Llamada desde el JS del POS para realizar una cancelación/devolución de un pago cobrado.
        Endpoint: DELETE /api/payments/{payment_id}
        """
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("No tienes permisos para realizar reembolsos en Nave."))

        payment_method = self.browse(payment_method_id)
        provider = payment_method._get_nave_payment_provider()
        token = provider._nave_get_access_token()
        base_url = provider._nave_get_api_url('smart_pos')

        api_url = f"{base_url}/api/payments/{transaction_id}"

        headers = {
            'Authorization': f"Bearer {token}",
            'Accept': 'application/json',
        }

        try:
            response = requests.delete(api_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data
        except requests.exceptions.RequestException as e:
            _logger.error("[pos_nave] Error solicitando reembolso en Nave: %s", e)
            return {'error': True, 'message': str(e)}
