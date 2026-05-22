# -*- coding: utf-8 -*-

import logging
import requests
from datetime import timedelta

from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('nave', 'Nave')],
        ondelete={'nave': 'set default'}
    )

    nave_client_id = fields.Char(
        string="Client ID",
        required_if_provider='nave',
        help="ID de cliente provisto por Nave Galicia/Naranja X."
    )
    nave_client_secret = fields.Char(
        string="Client Secret",
        required_if_provider='nave',
        groups='base.group_system',
        help="Clave secreta del cliente provisto por Nave."
    )
    nave_pos_id = fields.Char(
        string="POS ID (Tienda)",
        required_if_provider='nave',
        help="ID único de la tienda/POS de e-commerce en Nave (obtenido desde Nave > Integraciones)."
    )
    nave_access_token = fields.Char(
        string="Cached Access Token",
        groups='base.group_system'
    )
    nave_token_expiry = fields.Datetime(
        string="Vencimiento de Token"
    )

    # ==========================================
    # ODOO CORE PAYMENT PROVIDER METHODS OVERRIDES
    # ==========================================

    def _get_supported_currencies(self):
        """ Retorna las monedas soportadas por Nave. Únicamente pesos argentinos (ARS). """
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'nave':
            return self.env['res.currency'].search([('name', '=', 'ARS')])
        return supported_currencies

    # ==========================================
    # NAVE AUTHENTICATION LOGIC (OAUTH CACHE)
    # ==========================================

    def _nave_get_access_token(self):
        """
        Retorna el token de acceso Bearer cacheado. Si no existe o ya expiró (con margen de 5 minutos),
        realiza una petición de autenticación M2M a Auth0 y lo guarda en la base de datos.
        """
        self.ensure_one()
        now = fields.Datetime.now()
        margin = timedelta(minutes=5)

        # Si el token existe y sigue vigente con un margen de 5 minutos
        if self.nave_access_token and self.nave_token_expiry and (self.nave_token_expiry - margin) > now:
            return self.nave_access_token

        # Si no, realizamos el flujo de Auth0 M2M
        auth_url = self._nave_get_auth_url()
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        payload = {
            'client_id': self.nave_client_id,
            'client_secret': self.nave_client_secret,
            'audience': 'https://naranja.com/ranty/merchants/api'
        }

        _logger.info("Solicitando nuevo token de acceso a Nave Auth0 (%s)...", auth_url)

        try:
            response = requests.post(auth_url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            _logger.error("Error al autenticar con Nave Auth0: %s", e)
            raise UserError(_(
                "No se pudo establecer conexión con Nave para la autenticación. "
                "Por favor verifique las credenciales e intente de nuevo."
            ))

        access_token = data.get('access_token')
        expires_in = data.get('expires_in', 86400)  # Valor por defecto: 24 horas

        if not access_token:
            _logger.error("La respuesta de Nave Auth0 no contiene 'access_token'. Response: %s", data)
            raise UserError(_("Nave no devolvió un token de acceso válido."))

        # Guardar en caché con el tiempo de expiración
        expiry_datetime = now + timedelta(seconds=expires_in)
        self.write({
            'nave_access_token': access_token,
            'nave_token_expiry': expiry_datetime
        })

        return access_token

    def _nave_get_auth_url(self):
        """ Retorna el endpoint de autenticación según el estado del proveedor (Prueba o Producción). """
        self.ensure_one()
        if self.state == 'test':
            return 'https://homoservices.apinaranja.com/security-ms/api/security/auth0/b2b/m2msPrivate'
        return 'https://services.apinaranja.com/security-ms/api/security/auth0/b2b/m2msPrivate'

    def _nave_get_api_url(self):
        """ Retorna la URL base de la API según el estado del proveedor (Prueba o Producción). """
        self.ensure_one()
        if self.state == 'test':
            return 'https://api-sandbox.ranty.io'
        return 'https://api.ranty.io'
