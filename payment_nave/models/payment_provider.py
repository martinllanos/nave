# -*- coding: utf-8 -*-

import logging
import requests
from datetime import timedelta

from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Nave Point (payment_type 'smart_pos') se sirve desde un host de sandbox distinto del resto de los
# flujos. En producción todos comparten el mismo. Ver tasks/doc_actualizada_2026-09-22.md §3.
NAVE_SANDBOX_API_URLS = {
    'smart_pos': 'https://e3-api.ranty.io',
}
NAVE_SANDBOX_API_URL = 'https://api-sandbox.ranty.io'
NAVE_PRODUCTION_API_URL = 'https://api.ranty.io'

# Campo del que sale el `pos_id` de cada medio de cobro online. Nave asigna uno distinto por medio
# y rechaza con 409 INVALID_POS la intención que llega con el de otro. Un medio ausente de este
# mapa usa `nave_pos_id`.
NAVE_POS_ID_FIELDS = {
    'payment_link': 'nave_payment_link_pos_id',
}

# Único dominio al que se le permite a un webhook redirigirnos. El payload de Nave no viene
# firmado, así que la `payment_check_url` que trae es dato no confiable: sin esta restricción,
# cualquiera que adivine una referencia puede apuntar la verificación a un host propio.
NAVE_TRUSTED_DOMAIN = 'ranty.io'

# Métodos de pago que el proveedor activa al pasar a Prueba o Producción. Sin esto Odoo no activa
# ninguno y los métodos de Nave quedan archivados, o sea invisibles en el checkout.
NAVE_DEFAULT_PAYMENT_METHOD_CODES = {'card', 'naranja', 'nave_qr'}


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
    nave_payment_link_pos_id = fields.Char(
        string="POS ID (Link de pago)",
        help="ID del punto de venta del medio LINK DE PAGO en Nave, para los links generados desde "
             "facturas y pedidos. Se descarga desde Nave > Integraciones > Sistema de gestión.\n"
             "Nave asigna un ID distinto por medio de cobro: usar el de la tienda acá hace que la "
             "API rechace el link con 409 INVALID_POS.\n"
             "Si se deja vacío se usa el POS ID (Tienda), que es el comportamiento anterior.",
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
            error_details = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    response_json = e.response.json()
                    if isinstance(response_json, dict):
                        msg = (
                            response_json.get('message')
                            or response_json.get('error')
                            or response_json.get('description')
                            or response_json.get('error_description')
                        )
                        if msg:
                            error_details = f"{msg} (HTTP {e.response.status_code})"
                except Exception:
                    try:
                        error_details = f"{e.response.text[:200]} (HTTP {e.response.status_code})"
                    except Exception:
                        pass
            raise UserError(_(
                "No se pudo establecer conexión con Nave para la autenticación. Detalle: %s", error_details
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

    def write(self, vals):
        """ Invalida el token cacheado cuando cambia el ambiente o las credenciales.

        El token se guarda en el propio proveedor y sólo se renueva por vencimiento (hasta 24 h).
        Al pasar de Prueba a Producción, o al reemplazar las credenciales, el token viejo sigue
        siendo válido en el tiempo pero pertenece al otro ambiente: sin esto, el módulo mandaría
        un token de sandbox a la API de producción hasta que expire, y todas las llamadas
        fallarían con 401 sin que nada las reintente.
        """
        res = super().write(vals)
        if not {'state', 'nave_client_id', 'nave_client_secret'} & set(vals):
            return res
        stale = self.filtered(lambda p: p.code == 'nave' and p.nave_access_token)
        if stale:
            _logger.info(
                "[payment_nave] Se invalida el token cacheado de %s proveedor(es) "
                "por cambio de ambiente o credenciales.", len(stale)
            )
            super(PaymentProvider, stale).write({
                'nave_access_token': False,
                'nave_token_expiry': False,
            })
        return res

    def _get_default_payment_method_codes(self):
        """ Métodos que se activan solos al habilitar el proveedor.

        Odoo los archiva por defecto y sólo activa los que devuelve este método
        (`_activate_default_pms`). Sin sobreescribirlo, el proveedor quedaba habilitado pero sin
        un solo método visible en el checkout.
        """
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'nave':
            return default_codes
        return NAVE_DEFAULT_PAYMENT_METHOD_CODES

    def _nave_log_invalid_pos(self, exc, payment_type, pos_id):
        """ Deja rastro de qué medio y qué `pos_id` produjeron un rechazo por identidad.

        Nave responde `409 INVALID_POS` — "Given POS is for a different payment type" — sin decir
        cuál de los identificadores configurados está mal. Sin estos dos datos, diagnosticarlo
        obliga a reproducir el cobro.
        """
        response = getattr(exc, 'response', None)
        if response is None or response.status_code != 409:
            return
        try:
            code = (response.json() or {}).get('message')
        except ValueError:
            code = None
        if code != 'INVALID_POS':
            return
        _logger.error(
            "[payment_nave] Nave rechazó la intención por identidad: medio '%s', pos_id '%s'. "
            "Ese pos_id pertenece a otro medio de cobro: revisá la configuración del proveedor.",
            payment_type, pos_id,
        )

    def _nave_get_pos_id(self, payment_type=None):
        """ Devuelve el `pos_id` que corresponde a un medio de cobro de Nave.

        Nave asigna un identificador distinto por medio —tienda de e-commerce, link de pago— y
        rechaza con `409 INVALID_POS` la intención que llega con el de otro. Los puntos de uso ya
        saben a qué medio pertenecen, porque eso determina el endpoint, así que piden el `pos_id`
        declarándolo, igual que piden el host con `_nave_get_api_url`.

        :param str payment_type: tipo de pago de Nave ('ecommerce', 'payment_link').
        """
        self.ensure_one()
        field_name = NAVE_POS_ID_FIELDS.get(payment_type)
        # El campo propio del medio es opcional: sin él se usa el de la tienda, que es como venían
        # configuradas las instalaciones cuando el proveedor admitía un solo identificador.
        return (field_name and self[field_name]) or self.nave_pos_id

    def _nave_get_auth_url(self):
        """ Retorna el endpoint de autenticación según el estado del proveedor (Prueba o Producción). """
        self.ensure_one()
        if self.state == 'test':
            return 'https://homoservices.apinaranja.com/security-ms/api/security/auth0/b2b/m2msPrivate'
        return 'https://services.apinaranja.com/security-ms/api/security/auth0/b2b/m2msPrivate'

    def _nave_get_api_url(self, payment_type=None):
        """ Retorna la URL base de la API según el estado del proveedor y el tipo de pago.

        :param str payment_type: tipo de pago de Nave ('smart_pos', 'static_qr', 'payment_link',
            'ecommerce'). Sólo 'smart_pos' usa un host de sandbox propio; el resto comparte
            api-sandbox. En producción el host es el mismo para todos.
        """
        self.ensure_one()
        if self.state == 'test':
            return NAVE_SANDBOX_API_URLS.get(payment_type, NAVE_SANDBOX_API_URL)
        return NAVE_PRODUCTION_API_URL
