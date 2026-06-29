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
        Llamada desde el JS del POS para enviar una solicitud de cobro a la terminal.
        """
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("No tienes permisos para enviar solicitudes a Nave."))

        payment_method = self.browse(payment_method_id)
        if not payment_method.nave_terminal_id:
            raise UserError(_("El método de pago no tiene configurado un ID de terminal Nave."))

        provider = payment_method._get_nave_payment_provider()
        token = provider._nave_get_access_token()
        base_url = "https://e3-api.ranty.io" if provider.state == 'test' else "https://e3-api.naranjax.com"

        # El endpoint para mandar el pago al Smart POS en Nave (según doc)
        # Asumiendo un endpoint de Intención de pago presencial (Instore API)
        # La documentación indica POST /instore/payment_intents
        api_url = f"{base_url}/instore/payment_intents"

        # El amount debe ser string con 2 decimales
        formatted_amount = f"{amount:.2f}"

        payload = {
            'device_id': payment_method.nave_terminal_id,
            'external_reference': reference,
            'amount': {
                'currency': 'ARS',
                'value': formatted_amount
            },
            'pos_id': provider.nave_pos_id
        }

        headers = {
            'Authorization': f"Bearer {token}",
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        _logger.info("[pos_nave] Enviando intención de pago a la terminal %s (Ref: %s)", payment_method.nave_terminal_id, reference)

        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data
        except requests.exceptions.RequestException as e:
            _logger.error("[pos_nave] Error enviando pago a la terminal Nave: %s", e)
            error_details = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    response_json = e.response.json()
                    if isinstance(response_json, dict):
                        msg = (
                            response_json.get('message') or 
                            response_json.get('error') or 
                            response_json.get('description')
                        )
                        validation_errors = response_json.get('errors') or response_json.get('validation_errors')
                        if msg:
                            error_details = f"{msg} (HTTP {e.response.status_code})"
                        if validation_errors:
                            error_details += f" - Detalle: {validation_errors}"
                except Exception:
                    try:
                        error_details = f"{e.response.text[:200]} (HTTP {e.response.status_code})"
                    except Exception:
                        pass
            return {'error': True, 'message': error_details}

    @api.model
    def nave_check_payment_status(self, payment_method_id, intent_id):
        """
        Llamada desde el JS del POS (Polling) para consultar el estado del cobro en la terminal.
        """
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("No tienes permisos para consultar solicitudes a Nave."))

        payment_method = self.browse(payment_method_id)
        provider = payment_method._get_nave_payment_provider()
        token = provider._nave_get_access_token()
        base_url = "https://e3-api.ranty.io" if provider.state == 'test' else "https://e3-api.naranjax.com"

        # Consultar estado de la intención de pago
        api_url = f"{base_url}/instore/payment_intents/{intent_id}"

        headers = {
            'Authorization': f"Bearer {token}",
            'Accept': 'application/json',
        }

        try:
            response = requests.get(api_url, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            return data
        except requests.exceptions.RequestException as e:
            _logger.error("[pos_nave] Error consultando estado en Nave: %s", e)
            error_details = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    response_json = e.response.json()
                    if isinstance(response_json, dict):
                        msg = (
                            response_json.get('message') or 
                            response_json.get('error') or 
                            response_json.get('description')
                        )
                        if msg:
                            error_details = f"{msg} (HTTP {e.response.status_code})"
                except Exception:
                    try:
                        error_details = f"{e.response.text[:200]} (HTTP {e.response.status_code})"
                    except Exception:
                        pass
            return {'error': True, 'message': error_details}

    @api.model
    def nave_cancel_payment_intent(self, payment_method_id, intent_id):
        """
        Llamada desde el JS del POS para cancelar la intención de pago antes de que se apruebe.
        """
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("No tienes permisos para cancelar solicitudes a Nave."))

        payment_method = self.browse(payment_method_id)
        provider = payment_method._get_nave_payment_provider()
        token = provider._nave_get_access_token()
        base_url = "https://e3-api.ranty.io" if provider.state == 'test' else "https://e3-api.naranjax.com"

        api_url = f"{base_url}/instore/payment_intents/{intent_id}/cancel"

        headers = {
            'Authorization': f"Bearer {token}",
            'Accept': 'application/json',
        }

        try:
            response = requests.post(api_url, headers=headers, timeout=5)
            response.raise_for_status()
            return {'success': True}
        except requests.exceptions.RequestException as e:
            _logger.error("[pos_nave] Error cancelando intención en Nave: %s", e)
            return {'error': True, 'message': str(e)}

    @api.model
    def nave_refund_payment(self, payment_method_id, transaction_id, amount):
        """
        Llamada desde el JS del POS para realizar un reembolso/devolución.
        """
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("No tienes permisos para realizar reembolsos en Nave."))

        payment_method = self.browse(payment_method_id)
        provider = payment_method._get_nave_payment_provider()
        token = provider._nave_get_access_token()
        base_url = "https://e3-api.ranty.io" if provider.state == 'test' else "https://e3-api.naranjax.com"

        # El endpoint de reembolsos puede variar según la API (asumimos refund estándar instore)
        api_url = f"{base_url}/instore/refunds"

        formatted_amount = f"{abs(amount):.2f}"

        payload = {
            'payment_id': transaction_id,
            'device_id': payment_method.nave_terminal_id,
            'amount': {
                'currency': 'ARS',
                'value': formatted_amount
            }
        }

        headers = {
            'Authorization': f"Bearer {token}",
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data
        except requests.exceptions.RequestException as e:
            _logger.error("[pos_nave] Error solicitando reembolso en Nave: %s", e)
            return {'error': True, 'message': str(e)}
