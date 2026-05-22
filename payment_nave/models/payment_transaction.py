# -*- coding: utf-8 -*-

import logging
import requests
from werkzeug import urls

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

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

        # Determinar si es E-commerce o Link de Pago
        is_invoice = bool(self.invoice_ids)
        endpoint = '/api/payment_request/payment_link' if is_invoice else '/api/payment_request/ecommerce'
        api_url = f"{base_url}{endpoint}"

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
                'pos_id': self.provider_id.nave_pos_id
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
            # Duración por defecto (50 minutos = 3000 segundos)
            'duration_time': 3000
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
            _logger.error("Error al crear intención de pago en Nave: %s", e)
            raise UserError(_(
                "Error de comunicación con la pasarela de pagos Nave. "
                "Por favor intente nuevamente."
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

        # Retornamos el api_url que usará el template xml para hacer la redirección automática
        return {
            'api_url': checkout_url,
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
                products.append({
                    'name': line.product_id.name[:100],  # Recortar por seguridad de longitud
                    'description': line.name[:150] or '',
                    'quantity': int(line.product_uom_qty) or 1,
                    'unit_price': {
                        'currency': 'ARS',
                        'value': f"{line.price_reduce_taxexcl:.2f}"
                    }
                })

        # Si no hay venta, intentar leer desde las líneas de Facturas vinculadas
        elif self.invoice_ids:
            for line in self.invoice_ids.mapped('invoice_line_ids').filtered(lambda inv_line: not inv_line.display_type):
                products.append({
                    'name': line.product_id.name[:100] if line.product_id else line.name[:100],
                    'description': line.name[:150] or '',
                    'quantity': int(line.quantity) or 1,
                    'unit_price': {
                        'currency': 'ARS',
                        'value': f"{line.price_unit:.2f}"
                    }
                })

        # Fallback si no hay ventas ni facturas mapeadas directamente
        if not products:
            products.append({
                'name': f"Pago de transacción {self.reference}",
                'description': f"Referencia Odoo: {self.reference}",
                'quantity': 1,
                'unit_price': {
                    'currency': 'ARS',
                    'value': f"{self.amount:.2f}"
                }
            })

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

        self.nave_payment_id = payment_id

        # GET seguro para comprobar el estado real de la transacción
        token = self.provider_id._nave_get_access_token()
        base_url = self.provider_id._nave_get_api_url()
        check_url = f"{base_url}/ranty-payments/payments/{payment_id}"

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
            _logger.error("Error al consultar estado de pago en Nave: %s", e)
            self._set_error(_("Error al consultar el estado seguro del pago en la API de Nave."))
            return

        # Evaluar estado devuelto por la API oficial
        status_info = payment_data.get('status', {})
        status_name = status_info.get('name')
        reason_code = status_info.get('reason_code', 'transaction_successful')

        _logger.info("Resultado de verificación en Nave para %s: %s (%s)", self.reference, status_name, reason_code)

        if status_name == 'APPROVED':
            # Extraer información de billetera si está disponible para documentar en el chatter
            wallet_name = payment_data.get('wallet', {}).get('name', 'N/A')
            msg = f"Pago Aprobado con éxito. Billetera utilizada: {wallet_name.upper()}. Nave ID: {payment_id}"
            self._set_done(state_message=msg)
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
