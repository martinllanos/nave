# -*- coding: utf-8 -*-

import logging
from datetime import timedelta

import requests
from werkzeug import urls

from odoo import fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.payment_nave import const

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

    def _get_supported_currencies(self):
        """Return currencies supported by Nave (ARS only)."""
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'nave':
            return supported_currencies.filtered(
                lambda currency: currency.name in const.SUPPORTED_CURRENCIES
            )
        return supported_currencies

    def _get_default_payment_method_codes(self):
        """Return the default payment method codes for Nave."""
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'nave':
            return default_codes
        return const.DEFAULT_PAYMENT_METHOD_CODES

    def _nave_get_access_token(self):
        """Return a valid Bearer token, refreshing the Auth0 M2M cache when needed."""
        self.ensure_one()
        now = fields.Datetime.now()
        margin = timedelta(minutes=5)

        if (
            self.nave_access_token
            and self.nave_token_expiry
            and (self.nave_token_expiry - margin) > now
        ):
            return self.nave_access_token

        auth_url = self._nave_get_auth_url()
        payload = {
            'client_id': self.nave_client_id,
            'client_secret': self.nave_client_secret,
            'audience': 'https://naranja.com/ranty/merchants/api',
        }
        _logger.info("Requesting new Nave access token from Auth0.")

        try:
            response = requests.post(
                auth_url,
                json=payload,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException:
            _logger.exception("Nave Auth0 authentication failed.")
            raise UserError(_(
                "Nave: Could not authenticate. Please verify your credentials and try again."
            ))

        access_token = data.get('access_token')
        expires_in = data.get('expires_in', 86400)
        if not access_token:
            raise UserError(_("Nave: The authentication response did not include an access token."))

        expiry_datetime = now + timedelta(seconds=expires_in)
        self.write({
            'nave_access_token': access_token,
            'nave_token_expiry': expiry_datetime,
        })
        return access_token

    def _nave_get_auth_url(self):
        """Return the Auth0 endpoint for the current provider state."""
        self.ensure_one()
        if self.state == 'test':
            return (
                'https://homoservices.apinaranja.com/security-ms/api/security/'
                'auth0/b2b/m2msPrivate'
            )
        return (
            'https://services.apinaranja.com/security-ms/api/security/'
            'auth0/b2b/m2msPrivate'
        )

    def _nave_get_api_url(self):
        """Return the Nave API base URL for the current provider state."""
        self.ensure_one()
        if self.state == 'test':
            return 'https://api-sandbox.ranty.io'
        return 'https://api.ranty.io'

    def _nave_make_request(self, endpoint, payload=None, method='POST'):
        """Make an authenticated request to the Nave API.

        :param str endpoint: API path (e.g. '/api/payment_request/ecommerce').
        :param dict payload: JSON body for POST or unused for GET/DELETE.
        :param str method: HTTP method ('GET', 'POST', or 'DELETE').
        :return: Parsed JSON response body.
        :rtype: dict
        :raise ValidationError: If the HTTP request fails.
        """
        self.ensure_one()
        url = urls.url_join(self._nave_get_api_url(), endpoint)
        headers = {
            'Authorization': f'Bearer {self._nave_get_access_token()}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=15)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=15)
            else:
                response = requests.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            _logger.exception("Nave API request failed at %s", url)
            raise ValidationError(_("Nave: Could not establish the connection to the API."))
        if not response.content:
            return {}
        return response.json()
