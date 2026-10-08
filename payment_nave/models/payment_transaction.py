# -*- coding: utf-8 -*-

import logging
import requests
from datetime import timedelta
from urllib.parse import parse_qsl, urlparse, urlunparse
from werkzeug import urls

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .nave_payload import nave_product_entry
from .payment_provider import NAVE_TRUSTED_DOMAIN

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    nave_payment_request_id = fields.Char(
        string="Nave Intención ID",
        readonly=True
    )
    nave_checkout_url = fields.Char(
        string="Nave Checkout URL",
        readonly=True
    )
    nave_payment_id = fields.Char(
        string="Nave Pago ID",
        readonly=True
    )

    # ==========================================
    # 1. CORE OVERRIDES: SPECIFIC RENDERING
    # ==========================================

    def _get_specific_rendering_values(self, processing_values):
        """
        Método central que prepara la redirección. Llama a la API de Nave para
        crear la intención de pago (E-commerce o Link de Pago) y retorna el URL del checkout.
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'nave':
            return res

        # Obtener token de acceso
        token = self.provider_id._nave_get_access_token()
        base_url = self.provider_id._nave_get_api_url()

        # El medio de cobro define el endpoint y también el pos_id: una factura pagada desde el
        # portal va por el circuito de link de pago, no por el de la tienda. Sale de una sola
        # variable para que los dos no puedan quedar desalineados, que es lo que hace que Nave
        # responda `invalid_pos`.
        payment_type = 'payment_link' if self.invoice_ids else 'ecommerce'
        api_url = f"{base_url}/api/payment_request/{payment_type}"

        # Preparar datos de transacción/productos
        products_data = self._nave_get_products_payload()

        # Callback redirect URL (Retorno tras checkout)
        return_url = urls.url_join(self.get_base_url(), '/payment/nave/return')

        # Formatear el monto exacto a 2 decimales string
        formatted_amount = f"{self.amount:.2f}"

        # Cuerpo del payload según especificación de Nave
        payload = {
            'external_payment_id': self.reference,
            'seller': {
                'pos_id': self.provider_id._nave_get_pos_id(payment_type)
            },
            'transactions': [
                {
                    'amount': {
                        'currency': 'ARS',
                        'value': formatted_amount
                    },
                    'products': products_data
                }
            ],
            'buyer': self._nave_get_buyer_payload(),
            'additional_info': {
                'callback_url': return_url
            },
            # Lo que el cliente tiene para terminar de pagar. Configurable en el proveedor: 50
            # minutos fijos dejaban vencer intenciones sin que nadie pudiera estirar el plazo.
            'duration_time': self.provider_id.nave_checkout_duration_minutes * 60
        }

        headers = {
            'Authorization': f"Bearer {token}",
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        _logger.info("Enviando Intención de Pago a Nave (%s): %s", api_url, payload)

        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            self.provider_id._nave_log_invalid_pos(e, payment_type, payload['seller']['pos_id'])
            _logger.error("Error al crear intención de pago en Nave: %s", e)
            error_details = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    response_json = e.response.json()
                    if isinstance(response_json, dict):
                        msg = (
                            response_json.get('message')
                            or response_json.get('error')
                            or response_json.get('description')
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
            raise UserError(_(
                "Error de comunicación con la pasarela de pagos Nave. Detalle: %s", error_details
            ))

        checkout_url = data.get('checkout_url')
        payment_request_id = data.get('id')

        if not checkout_url or not payment_request_id:
            _logger.error("La API de Nave no devolvió 'checkout_url' o 'id'. Respuesta: %s", data)
            raise UserError(_("Nave no pudo procesar esta intención de pago de forma exitosa."))

        # Guardar metadatos en la transacción
        self.write({
            'nave_payment_request_id': payment_request_id,
            'nave_checkout_url': checkout_url,
        })

        # El formulario de redirección se envía con GET, y un envío GET descarta el query string
        # de la acción y lo reemplaza por los campos del formulario. Por eso la URL viaja partida:
        # los parámetros van como campos y el navegador los vuelve a poner. Dejarlos en la acción
        # hacía que el cliente llegara a Nave sin la intención, ante una pantalla en blanco.
        return self._nave_redirect_values(checkout_url)

    def _nave_redirect_values(self, checkout_url):
        """ Parte la URL del checkout en acción y parámetros, para que el envío GET los conserve.

        Los parámetros se leen de lo que Nave devuelve, en vez de darse por sabidos: hoy manda sólo
        `payment_request_id`, pero eso no figura en la documentación y no es un contrato.
        """
        partes = urlparse(checkout_url)
        return {
            'api_url': urlunparse(partes._replace(query='')),
            'nave_redirect_params': parse_qsl(partes.query),
        }

    # ==========================================
    # 2. AYUDANTES DE PAYLOAD (MAPPING ODOO -> NAVE)
    # ==========================================

    def _nave_get_products_payload(self):
        """ Construye la lista de productos basada en el pedido o factura vinculada. """
        self.ensure_one()
        products = []

        # Intentar leer desde las líneas de Sale Orders vinculadas
        if self.sale_order_ids:
            for line in self.sale_order_ids.mapped('order_line').filtered(lambda order_line: not order_line.display_type):
                products.append(nave_product_entry(
                    self.env,
                    name=line.product_id.name,
                    description=line.name,
                    quantity=line.product_uom_qty,
                    line_total=line.price_total,
                    uom_name=line.product_uom.name,
                ))

        # Si no hay venta, intentar leer desde las líneas de Facturas vinculadas
        elif self.invoice_ids:
            for line in self.invoice_ids.mapped('invoice_line_ids').filtered(lambda inv_line: not inv_line.display_type):
                products.append(nave_product_entry(
                    self.env,
                    name=line.product_id.name if line.product_id else line.name,
                    description=line.name,
                    quantity=line.quantity,
                    line_total=line.price_total,
                    uom_name=line.product_uom_id.name,
                ))

        # Fallback si no hay ventas ni facturas mapeadas directamente
        if not products:
            products.append(nave_product_entry(
                self.env,
                name=f"Pago de transacción {self.reference}",
                description=f"Referencia Odoo: {self.reference}",
                quantity=1,
                line_total=self.amount,
            ))

        return products

    def _nave_get_buyer_payload(self):
        """ Mapea los datos del partner de Odoo al objeto buyer de Nave. """
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            return {}

        # Mapeo simple de DNI / CUIT si está disponible
        doc_type = 'DNI'
        doc_number = partner.vat or '00000000'
        if doc_number and len(doc_number) > 8:
            doc_type = 'CUIT'

        return {
            'doc_type': doc_type,
            'doc_number': doc_number,
            'name': partner.name[:50],
            'user_email': partner.email or 'correo@temporal.com',
            'user_id': str(partner.id),
            'billing_address': {
                'street_1': partner.street[:100] if partner.street else 'S/D',
                'street_2': partner.street2[:100] if partner.street2 else 'N/A',
                'city': partner.city or 'S/D',
                'region': partner.state_id.name or 'S/D',
                'country': 'AR',
                'zipcode': partner.zip or '0000'
            }
        }

    # ==========================================
    # 3. WEBHOOK Y CONCILIACIÓN
    # ==========================================

    @api.model
    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Busca la transacción correspondiente basándose en la referencia. """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'nave':
            return tx

        reference = notification_data.get('external_payment_id')
        if not reference:
            raise ValidationError("Nave: no se recibió 'external_payment_id' en la notificación.")

        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'nave')])
        if not tx:
            raise ValidationError(f"Nave: no se encontró transacción para la referencia {reference}.")

        return tx

    # ──────────────────────────────────────────────────────────────────────────
    # Conciliación de respaldo (webhooks perdidos)
    # ──────────────────────────────────────────────────────────────────────────

    @api.model
    def _cron_nave_poll_pending_transactions(self):
        """ Reconsulta contra Nave las transacciones que quedaron esperando el webhook.

        Nave reintenta la notificación cinco veces a lo largo de unas 7h45m y después se rinde. Sin
        esta red, un webhook perdido deja la transacción pendiente para siempre.

        Se ignoran las más recientes para no adelantarse al webhook, y las demasiado viejas para no
        arrastrar indefinidamente intenciones que nunca se pagaron. Ambos límites se pueden ajustar
        con los parámetros `payment_nave.poll_min_age_minutes` y `payment_nave.poll_max_age_days`.
        """
        params = self.env['ir.config_parameter'].sudo()
        min_age = int(params.get_param('payment_nave.poll_min_age_minutes', 30))
        max_age = int(params.get_param('payment_nave.poll_max_age_days', 2))
        now = fields.Datetime.now()

        transactions = self.search([
            ('provider_code', '=', 'nave'),
            ('state', 'in', ('draft', 'pending')),
            ('nave_payment_request_id', '!=', False),
            ('create_date', '<=', now - timedelta(minutes=min_age)),
            ('create_date', '>=', now - timedelta(days=max_age)),
        ])
        if not transactions:
            return

        _logger.info("[payment_nave] Reconsultando %s transacciones pendientes.", len(transactions))
        for tx in transactions:
            # Un savepoint por transacción: que una falla no se lleve puesto el resto del lote.
            try:
                with self.env.cr.savepoint():
                    tx._nave_poll_payment_request()
            except Exception:
                _logger.exception(
                    "[payment_nave] Error reconsultando la transacción %s.", tx.reference
                )

    def _nave_poll_payment_request(self):
        """ Consulta la intención y, si ya se resolvió, lleva la transacción a su estado final. """
        self.ensure_one()

        token = self.provider_id._nave_get_access_token()
        base_url = self.provider_id._nave_get_api_url()
        api_url = f"{base_url}/api/payment_requests/{self.nave_payment_request_id}"
        headers = {
            'Authorization': f"Bearer {token}",
            'Accept': 'application/json',
        }

        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        status_name = (data.get('status') or {}).get('name')

        if status_name in ('SUCCESS_PROCESSED', 'FAILURE_PROCESSED'):
            payment_id = self._nave_extract_payment_id(data)
            if not payment_id:
                _logger.warning(
                    "[payment_nave] La intención %s está en %s pero no expone un payment_id.",
                    self.nave_payment_request_id, status_name,
                )
                return
            # Se reusa el mismo camino que el webhook, incluida la verificación del pago.
            self._process_notification_data({
                'payment_id': payment_id,
                'external_payment_id': self.reference,
            })
        elif status_name in ('EXPIRED', 'DISABLED', 'BLOCKED'):
            self._set_canceled(_("Nave informó la intención de pago como %s.", status_name))

    def _nave_extract_payment_id(self, intent_data):
        """ Devuelve el `payment_id` del último intento de pago de una intención, o False. """
        attempts = (intent_data or {}).get('payment_attempts') or {}
        payments = attempts.get('payments') or []
        if not payments:
            return False
        return payments[-1].get('payment_id') or False

    def _nave_store_payment_details(self, payment_data):
        """ Conserva lo que Nave informa del cobro: instrumento, comprobantes y financiación.

        Todo esto llega en la misma verificación que ya se hace para confirmar el estado, así que no
        cuesta una llamada extra. Antes se descartaba y la única forma de saber con qué pagó alguien
        era entrar al panel de Nave.
        """
        self.ensure_one()
        metodo = payment_data.get('payment_method') or {}
        transaccion = (payment_data.get('transactions') or [{}])[0]
        auth = transaccion.get('auth_data') or {}
        plan = metodo.get('installment_plan') or {}
        # La billetera viene en la raíz para QR y dentro del método para algunos flujos.
        billetera = (payment_data.get('wallet') or {}).get('name') or metodo.get('wallet_name')

        valores = {
            'nave_card_brand': metodo.get('card_brand') or False,
            'nave_card_type': metodo.get('card_type') or False,
            'nave_card_last4': metodo.get('card_last4') or False,
            'nave_card_issuer': metodo.get('issuer') or False,
            'nave_payment_input': payment_data.get('payment_input') or False,
            'nave_wallet_name': billetera or False,
            'nave_payment_code': payment_data.get('payment_code') or False,
            'nave_auth_code': auth.get('auth_id') or False,
            'nave_batch': (auth.get('ticket') or {}).get('batch') or False,
            'nave_installments': plan.get('installments') or 0,
            'nave_installment_has_interest': bool(plan.get('has_interest')),
            'nave_interest_rate': plan.get('interest_rate') or False,
            'nave_annual_nominal_rate': (
                str(plan['annual_nominal_rate']) if plan.get('annual_nominal_rate') is not None else False
            ),
            'nave_total_financial_cost': plan.get('total_financial_cost') or False,
            'nave_customer_total': float(((plan.get('total_amount') or {}).get('value')) or 0.0),
        }
        self.write(valores)
        self._nave_apply_card_brand(metodo.get('card_brand'))

    def _nave_apply_card_brand(self, card_brand):
        """ Refleja la marca en el medio de pago de la transacción.

        Odoo modela las marcas como sub-métodos de `card`, y es donde las muestran sus vistas e
        informes. Si Nave informa una que el proveedor no tiene vinculada, se deja el medio como
        estaba: el texto ya quedó guardado, y perder el dato sería peor que no poder clasificarlo.
        """
        self.ensure_one()
        if not card_brand:
            return
        marcas = self.provider_id.with_context(active_test=False).payment_method_ids.brand_ids
        marca = marcas.filtered(lambda m: m.name and m.name.lower() == card_brand.lower())[:1]
        if marca:
            self.payment_method_id = marca
        else:
            _logger.info(
                "[payment_nave] La marca '%s' informada por Nave no tiene un método de pago "
                "equivalente en el proveedor; se conserva sólo como dato de la transacción.",
                card_brand,
            )

    def _nave_payment_summary(self, payment_id):
        """ Describe el cobro según el medio que se usó.

        El texto anterior nombraba siempre la billetera, de modo que un pago con tarjeta quedaba
        registrado como "Billetera utilizada: N/A": un dato que no informa nada y que hace dudar de
        si falta o si el pago fue raro.
        """
        self.ensure_one()
        partes = []
        if self.nave_card_brand or self.nave_card_last4:
            tarjeta = " ".join(filter(None, [self.nave_card_brand, self.nave_card_type]))
            if self.nave_card_last4:
                tarjeta = f"{tarjeta} ****{self.nave_card_last4}".strip()
            partes.append(_("Tarjeta: %s", tarjeta.strip()))
        elif self.nave_wallet_name:
            partes.append(_("Billetera: %s", self.nave_wallet_name))

        if self.nave_installments > 1:
            cuotas = _("Cuotas: %s", self.nave_installments)
            if self.nave_customer_total:
                cuotas = _(
                    "%(cuotas)s · total pagado por el cliente: %(total)s",
                    cuotas=cuotas, total=f"{self.nave_customer_total:.2f}",
                )
            partes.append(cuotas)

        if self.nave_payment_code:
            partes.append(_("Cupón: %s", self.nave_payment_code))

        detalle = " · ".join(partes)
        if detalle:
            return _("Pago aprobado. %(detalle)s. Nave ID: %(id)s", detalle=detalle, id=payment_id)
        return _("Pago aprobado. Nave ID: %s", payment_id)

    # ── Datos del cobro informados por Nave ──────────────────────────────────
    # Nave los devuelve en la verificación de cada pago y antes se descartaban: la única forma de
    # saber con qué se pagó era entrar a su panel.
    nave_card_brand = fields.Char(string="Marca de tarjeta", readonly=True)
    nave_card_type = fields.Char(string="Tipo de tarjeta", readonly=True)
    nave_card_last4 = fields.Char(string="Últimos 4 dígitos", readonly=True)
    nave_card_issuer = fields.Char(string="Entidad emisora", readonly=True)
    nave_payment_input = fields.Char(string="Modo de ingreso", readonly=True)
    nave_wallet_name = fields.Char(string="Billetera", readonly=True)

    nave_payment_code = fields.Char(string="Código de cupón", readonly=True)
    nave_auth_code = fields.Char(string="Código de autorización", readonly=True)
    nave_batch = fields.Char(string="Lote", readonly=True)

    nave_installments = fields.Integer(string="Cuotas", readonly=True)
    nave_installment_has_interest = fields.Boolean(string="Cuotas con interés", readonly=True)
    nave_interest_rate = fields.Char(string="Tasa de interés", readonly=True)
    nave_annual_nominal_rate = fields.Char(string="Tasa nominal anual", readonly=True)
    nave_total_financial_cost = fields.Char(string="Costo financiero total", readonly=True)
    nave_customer_total = fields.Monetary(
        string="Total pagado por el cliente", readonly=True, currency_field='currency_id',
        help="Importe que efectivamente desembolsó el cliente. En una venta financiada difiere del "
             "monto de la transacción: el costo financiero lo paga el cliente al emisor y no es un "
             "ingreso del comercio.",
    )

    # Estado al que lleva cada desenlace que informa Nave, para distinguir una notificación
    # descartada de una repetida.
    NAVE_ESTADO_POR_DESENLACE = {
        'APPROVED': 'done',
        'REJECTED': 'cancel',
        'CANCELLED': 'cancel',
        'REFUNDED': 'cancel',
        'PURCHASE_REVERSED': 'cancel',
        'PENDING': 'pending',
    }

    def _nave_log_discarded_outcome(self, estado_previo, status_name, payment_id):
        """ Deja constancia cuando una notificación de Nave no pudo aplicarse al estado actual.

        El modelo base descarta una transición no permitida registrando sólo un warning genérico en
        el log de Odoo. Eso fue lo único que quedó de un cobro aprobado que no se registró, en un
        archivo que nadie mira. Acá se nombra la referencia, el desenlace que informó Nave y el
        estado que quedó, que es lo que permite encontrarlo.
        """
        self.ensure_one()
        if self.state != estado_previo:
            return  # La notificación se aplicó: no hay nada que advertir.
        if self.NAVE_ESTADO_POR_DESENLACE.get(status_name) == estado_previo:
            # El desenlace es el que la transacción ya tenía: es un reintento de Nave, que repite
            # cada webhook hasta cinco veces. Advertir por esto llenaría el log de avisos que no
            # requieren nada, y una advertencia que salta cuando no pasa nada termina haciendo que
            # se ignoren las que sí importan.
            return
        _logger.warning(
            "[payment_nave] La transacción %s quedó en '%s' y no pudo tomar el desenlace '%s' "
            "que informó Nave (pago %s). Revisá si corresponde resolverla a mano.",
            self.reference, estado_previo, status_name, payment_id,
        )

    def _nave_get_check_url(self, payment_id, notification_data):
        """ URL contra la que se verifica el estado real del pago.

        Nave manda en el webhook la `payment_check_url` a consultar, y usarla es lo que hace
        funcionar el flujo: la URL que podemos construir nosotros no siempre coincide con el host
        que corresponde. Pero el webhook **no viene firmado**, así que ese valor es dato no
        confiable: si se usara tal cual, alguien que adivine una referencia podría apuntar la
        verificación a un servidor propio que responda APPROVED y dar por pagada una factura.

        Sólo se acepta si apunta al dominio de Nave. En cualquier otro caso se cae al fallback
        construido localmente, que es seguro por definición.
        """
        self.ensure_one()
        fallback = f"{self.provider_id._nave_get_api_url()}/ranty-payments/payments/{payment_id}"

        check_url = (notification_data.get('payment_check_url') or '').strip()
        if not check_url:
            return fallback

        # Nave documenta la URL sin esquema ("api.ranty.io/ranty-payments/..."), así que hay que
        # normalizarla antes de poder mirarle el host. Se fuerza https en todos los casos.
        if not check_url.startswith(('http://', 'https://')):
            check_url = f"https://{check_url}"
        parsed = urlparse(check_url)
        host = (parsed.hostname or '').lower()

        if host != NAVE_TRUSTED_DOMAIN and not host.endswith(f".{NAVE_TRUSTED_DOMAIN}"):
            _logger.warning(
                "[payment_nave] Webhook de %s con payment_check_url fuera de %s (%r). "
                "Se ignora y se verifica contra la URL propia.",
                self.reference, NAVE_TRUSTED_DOMAIN, check_url,
            )
            return fallback

        # Se reconstruye el netloc a partir del host y el puerto, descartando cualquier
        # userinfo del tipo "https://otro-host@api.ranty.io/...".
        netloc = f"{host}:{parsed.port}" if parsed.port else host
        return urlunparse(parsed._replace(scheme='https', netloc=netloc))

    def _process_notification_data(self, notification_data):
        """
        Procesa los datos recibidos del Webhook.
        Realiza una petición GET complementaria a la API de Nave para validar de manera segura
        el estado del pago, evitando ataques de manipulación de webhooks.
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'nave':
            return

        payment_id = notification_data.get('payment_id')
        if not payment_id:
            raise ValidationError("Nave: No se recibió 'payment_id' en el webhook.")

        # El `payment_id` del pago cuyo desenlace se aplique se guarda recién al final: una
        # intención admite varios intentos, y escribirlo antes dejaría la transacción apuntando al
        # último pago notificado aunque su desenlace se haya descartado. Eso fue lo que pasó con el
        # pedido S00005, que quedó cancelado con el identificador del pago aprobado encima.
        payment_id_previo = self.nave_payment_id

        # GET seguro para comprobar el estado real de la transacción
        token = self.provider_id._nave_get_access_token()
        check_url = self._nave_get_check_url(payment_id, notification_data)

        headers = {
            'Authorization': f"Bearer {token}",
            'Accept': 'application/json',
        }

        _logger.info("Verificando transacción %s en Nave (%s)...", payment_id, check_url)

        try:
            response = requests.get(check_url, headers=headers, timeout=10)
            response.raise_for_status()
            payment_data = response.json()
        except requests.exceptions.RequestException as e:
            # Una falla de comunicación no dice nada del pago, que pudo haberse cobrado. Antes se
            # cerraba la transacción en error y el webhook respondía 200: Nave no reintentaba y la
            # conciliación periódica, que sólo mira las pendientes, tampoco la volvía a revisar.
            # Propagarla deja la transacción como estaba: el webhook responde 500 para que Nave
            # reintente, y la conciliación la retoma en la corrida siguiente.
            _logger.error(
                "[payment_nave] No se pudo consultar el pago %s de la transacción %s en Nave; "
                "queda como estaba. Error: %s", payment_id, self.reference, e,
            )
            raise

        # Evaluar estado devuelto por la API oficial
        status_info = payment_data.get('status', {})
        status_name = status_info.get('name')
        reason_code = status_info.get('reason_code', 'transaction_successful')

        _logger.info("Resultado de verificación en Nave para %s: %s (%s)", self.reference, status_name, reason_code)

        estado_previo = self.state

        if status_name == 'APPROVED':
            self._nave_store_payment_details(payment_data)
            msg = self._nave_payment_summary(payment_id)
            if estado_previo == 'cancel':
                # Una intención de Nave admite varios intentos: el cliente puede reintentar con otra
                # tarjeta después de un rechazo. Sin habilitar 'cancel' como origen, esa aprobación
                # se descarta y queda un cobro real sin registrar.
                msg = _("Tras un intento rechazado previamente — %s", msg)
            self._set_done(state_message=msg, extra_allowed_states=('cancel',))
        elif status_name in ['REJECTED', 'CANCELLED']:
            msg = f"Transacción rechazada/cancelada en Nave. Motivo: {reason_code}"
            self._set_canceled(state_message=msg)
        elif status_name == 'PENDING':
            self._set_pending()
        elif status_name in ['REFUNDED', 'PURCHASE_REVERSED']:
            # Si ya se reembolsó asíncronamente
            self._set_canceled(state_message=_("El pago fue reembolsado o reversado en Nave."))
        else:
            self._set_error(_("Estado desconocido devuelto por Nave: %s", status_name))

        # Sólo queda asociado el pago cuyo desenlace efectivamente se aplicó. Si no había ninguno,
        # se guarda igual para no perder la trazabilidad del primer intento.
        if self.state != estado_previo or not payment_id_previo:
            self.nave_payment_id = payment_id

        self._nave_log_discarded_outcome(estado_previo, status_name, payment_id)

    # ==========================================
    # 4. REEMBOLSOS / ANULACIONES AUTOMÁTICAS
    # ==========================================

    def _send_refund_request(self, amount_to_refund=None, **kwargs):
        """
        Sobrescribe el reverso de pago. Invoca el DELETE /api/payments/{payment_id}
        para solicitar el reembolso formal en las pasarelas bancarias a través de Nave.
        """
        res = super()._send_refund_request(amount_to_refund=amount_to_refund, **kwargs)
        if self.provider_code != 'nave':
            return res

        if not self.nave_payment_id:
            raise UserError(_("No existe un ID de pago de Nave registrado para procesar la devolución."))

        # Solicitar reembolso a Nave
        token = self.provider_id._nave_get_access_token()
        base_url = self.provider_id._nave_get_api_url()
        refund_url = f"{base_url}/api/payments/{self.nave_payment_id}"

        headers = {
            'Authorization': f"Bearer {token}",
            'Accept': 'application/json',
        }

        _logger.info("Solicitando reembolso a Nave del pago %s (%s)...", self.nave_payment_id, refund_url)

        try:
            response = requests.delete(refund_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            _logger.error("Error al procesar reembolso en Nave: %s", e)
            raise UserError(_("Fallo de comunicación al solicitar el reembolso a Nave. Detalle: %s", e))

        # El estado transiciona a CANCELLING mientras se realiza la devolución
        status = data.get('status')
        if status == 'CANCELLING':
            self._set_canceled(state_message=_("El reembolso está en proceso ('CANCELLING') en Nave."))

        return res
