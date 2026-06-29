# -*- coding: utf-8 -*-
# [ADD] payment_nave: Wizard para generar links de pago Nave desde facturas y pedidos de venta.
# Este wizard permite al usuario generar un link de Checkout de Nave directamente
# desde el backoffice (factura o pedido), evitando el flujo estándar de /payment/pay.
# El link generado apunta a la pasarela de Nave y se puede copiar o enviar por email.

import logging
import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Duración predeterminada del link de pago en segundos (24 horas)
_DEFAULT_LINK_DURATION = 86400


class NavePaymentLinkWizard(models.TransientModel):
    """
    Wizard transient para generar Links de Pago de Nave desde facturas o pedidos.
    Invoca directamente la API de Nave (/api/payment_request/payment_link)
    y retorna la URL del checkout al usuario para que la copie o la envíe.
    """
    _name = 'nave.payment.link.wizard'
    _description = 'Generador de Link de Pago Nave'

    # ──────────────────────────────────────────────
    # Campos del wizard
    # ──────────────────────────────────────────────
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
    )
    provider_id = fields.Many2one(
        'payment.provider',
        string='Proveedor Nave',
        domain="[('code', '=', 'nave'), ('state', '!=', 'disabled'), "
               "('company_id', '=', company_id)]",
        required=True,
        check_company=True,
    )
    move_id = fields.Many2one(
        'account.move',
        string='Factura',
        readonly=True,
    )
    sale_id = fields.Many2one(
        'sale.order',
        string='Pedido de Venta',
        readonly=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        readonly=True,
    )
    amount = fields.Monetary(
        string='Monto a Cobrar',
        currency_field='currency_id',
        required=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        readonly=True,
        default=lambda self: self.env.ref('base.ARS', raise_if_not_found=False),
    )
    duration_hours = fields.Integer(
        string='Validez del Link (horas)',
        default=24,
        help='Tiempo en horas durante el cual el link de pago estará activo. Máximo recomendado: 168h (1 semana).',
    )
    external_reference = fields.Char(
        string='Referencia Externa',
        readonly=True,
        help='Referencia única del documento en Odoo, que se enviará a Nave como external_payment_id.',
    )

    # Resultado
    nave_link = fields.Char(
        string='Link de Pago Nave',
        readonly=True,
    )
    nave_payment_request_id = fields.Char(
        string='Nave Payment Request ID',
        readonly=True,
    )
    link_generated = fields.Boolean(default=False)

    # ──────────────────────────────────────────────
    # Valores por defecto desde contexto
    # ──────────────────────────────────────────────

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')

        if not active_model or not active_id:
            return res

        # Detectar si se abre desde una Factura
        if active_model == 'account.move':
            move = self.env['account.move'].browse(active_id)
            if move.exists() and move.move_type in ('out_invoice', 'out_refund'):
                res.update({
                    'move_id': move.id,
                    'partner_id': move.partner_id.id,
                    'amount': move.amount_residual,
                    'currency_id': move.currency_id.id,
                    'company_id': move.company_id.id,
                    'external_reference': move.name or f'MOVE-{move.id}',
                })

        # Detectar si se abre desde un Pedido de Venta
        elif active_model == 'sale.order':
            sale = self.env['sale.order'].browse(active_id)
            if sale.exists():
                res.update({
                    'sale_id': sale.id,
                    'partner_id': sale.partner_id.id,
                    'amount': sale.amount_total,
                    'currency_id': sale.currency_id.id,
                    'company_id': sale.company_id.id,
                    'external_reference': sale.name or f'SO-{sale.id}',
                })

        # Pre-seleccionar el proveedor Nave activo de la compañía
        company_id = res.get('company_id', self.env.company.id)
        nave_provider = self.env['payment.provider'].search([
            ('code', '=', 'nave'),
            ('state', '!=', 'disabled'),
            ('company_id', '=', company_id),
        ], limit=1)
        if nave_provider:
            res['provider_id'] = nave_provider.id

        return res

    # ──────────────────────────────────────────────
    # Acción principal: Generar el Link en Nave
    # ──────────────────────────────────────────────

    def action_generate_link(self):
        """
        [ADD] Genera el Link de Pago en la API de Nave usando el endpoint
        POST /api/payment_request/payment_link y almacena la URL resultante en el wizard.
        Opera con multi-compañía usando with_company para respetar credenciales de la
        compañía correcta.
        """
        self.ensure_one()

        if self.amount <= 0:
            raise UserError(_('El monto a cobrar debe ser mayor a cero.'))

        if not self.external_reference:
            raise UserError(_('La referencia externa es obligatoria para identificar el pago en Nave.'))

        # Respetar contexto de compañía (multi-company)
        provider = self.provider_id.with_company(self.company_id)

        # Obtener token (caché automático)
        token = provider._nave_get_access_token()
        base_url = provider._nave_get_api_url()
        api_endpoint = f"{base_url}/api/payment_request/payment_link"

        # Duración del link en segundos
        duration_seconds = self.duration_hours * 3600

        # Construir payload de productos
        products_payload = self._nave_build_products_payload()

        payload = {
            'external_payment_id': self.external_reference[:36],  # Máx 36 chars
            'seller': {
                'pos_id': provider.nave_pos_id,
            },
            'transactions': [
                {
                    'amount': {
                        'currency': 'ARS',
                        'value': f"{self.amount:.2f}",
                    },
                    'products': products_payload,
                }
            ],
            'buyer': self._nave_build_buyer_payload(),
            'duration_time': duration_seconds,
        }

        headers = {
            'Authorization': f"Bearer {token}",
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        _logger.info(
            "[payment_nave] Generando Link de Pago para '%s' (compañía: %s) en Nave: %s",
            self.external_reference,
            self.company_id.name,
            api_endpoint,
        )

        try:
            response = requests.post(
                api_endpoint,
                json=payload,
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.Timeout:
            raise UserError(_(
                "Nave no respondió dentro del tiempo esperado. Por favor intente nuevamente."
            ))
        except requests.exceptions.RequestException as e:
            _logger.error("[payment_nave] Error al generar link de pago en Nave: %s", e)
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
            raise UserError(_(
                "Error de comunicación con Nave al generar el link de pago. Detalle: %s", error_details
            ))

        checkout_url = data.get('checkout_url')
        payment_request_id = data.get('id')

        if not checkout_url:
            _logger.error("[payment_nave] Nave no devolvió 'checkout_url'. Respuesta: %s", data)
            raise UserError(_(
                "Nave procesó la solicitud pero no devolvió una URL de pago válida."
            ))

        # Guardar resultado en el wizard para mostrarlo en el formulario
        self.write({
            'nave_link': checkout_url,
            'nave_payment_request_id': payment_request_id,
            'link_generated': True,
        })

        # Registrar el link en el chatter del documento origen (si aplica)
        self._post_link_to_chatter(checkout_url)

        # Re-abrir el mismo wizard (ya con el campo del link visible)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    # ──────────────────────────────────────────────
    # Helpers internos de construcción de payloads
    # ──────────────────────────────────────────────

    def _nave_build_products_payload(self):
        """Construye la lista de productos desde la factura o pedido de venta."""
        self.ensure_one()
        products = []

        if self.move_id:
            for line in self.move_id.invoice_line_ids.filtered(lambda inv_line: not inv_line.display_type):
                products.append({
                    'name': (line.product_id.name or line.name or 'Ítem')[:100],
                    'description': (line.name or '')[:150],
                    'quantity': int(line.quantity) or 1,
                    'unit_price': {
                        'currency': 'ARS',
                        'value': f"{line.price_unit:.2f}",
                    },
                })
        elif self.sale_id:
            for line in self.sale_id.order_line.filtered(lambda sale_line: not sale_line.display_type):
                products.append({
                    'name': (line.product_id.name or line.name or 'Ítem')[:100],
                    'description': (line.name or '')[:150],
                    'quantity': int(line.product_uom_qty) or 1,
                    'unit_price': {
                        'currency': 'ARS',
                        'value': f"{line.price_reduce_taxexcl:.2f}",
                    },
                })

        # Fallback genérico si no hay líneas de detalle
        if not products:
            products.append({
                'name': f"Pago {self.external_reference}"[:100],
                'description': 'Link de pago generado desde Odoo',
                'quantity': 1,
                'unit_price': {
                    'currency': 'ARS',
                    'value': f"{self.amount:.2f}",
                },
            })

        return products

    def _nave_build_buyer_payload(self):
        """Mapea el partner de Odoo al objeto buyer de Nave."""
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            return {}

        doc_number = partner.vat or '00000000'
        doc_type = 'CUIT' if len(doc_number) > 8 else 'DNI'

        return {
            'doc_type': doc_type,
            'doc_number': doc_number,
            'name': (partner.name or '')[:50],
            'user_email': partner.email or '',
            'user_id': str(partner.id),
            'billing_address': {
                'street_1': (partner.street or 'S/D')[:100],
                'street_2': (partner.street2 or '')[:100],
                'city': partner.city or 'S/D',
                'region': partner.state_id.name or 'S/D',
                'country': 'AR',
                'zipcode': partner.zip or '0000',
            },
        }

    def _post_link_to_chatter(self, checkout_url):
        """
        Registra el link de pago generado en el chatter del documento fuente.
        Esto permite trazabilidad completa de los links enviados desde Odoo.
        """
        self.ensure_one()
        msg = _(
            "📎 <b>Link de Pago Nave generado:</b><br/>"
            "<a href='%(url)s' target='_blank'>%(url)s</a><br/>"
            "<small>Referencia: %(ref)s | Monto: %(amount)s ARS</small>",
            url=checkout_url,
            ref=self.external_reference,
            amount=f"{self.amount:.2f}",
        )
        doc = self.move_id or self.sale_id
        if doc and hasattr(doc, 'message_post'):
            doc.message_post(body=msg, message_type='comment', subtype_xmlid='mail.mt_note')
