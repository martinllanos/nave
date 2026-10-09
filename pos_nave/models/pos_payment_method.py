# -*- coding: utf-8 -*-

import logging
import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError

from odoo.addons.payment_nave.models.nave_reasons import (
    NAVE_INTENT_ERROR_MESSAGES,
    nave_intent_error,
    nave_reason_message,
)

_logger = logging.getLogger(__name__)

# Timeouts de las llamadas a Nave, en segundos.
#
# Crear la intención es la más lenta con diferencia: Nave tiene que alcanzar la terminal física,
# que puede estar en 4G, y recién ahí responde. Diez segundos se quedaban cortos incluso con la
# API sana (los hosts responden en ~0,3 s, así que no es un problema de red). Las consultas de
# estado sí tienen que ser rápidas: corren cada 3 segundos dentro del bucle de polling.
#
# Ajustables con los parámetros de sistema `pos_nave.timeout_<nombre>`.
NAVE_TIMEOUTS = {
    'intent': 30,
    'status': 5,
    'cancel': 10,
    'refund': 15,
}

# Desenlace de un cobro según el estado que informa Nave.
#
# La consulta devuelve el estado de la INTENCIÓN (SUCCESS_PROCESSED, BLOCKED, …), que no es el mismo
# vocabulario que el del PAGO (APPROVED, REJECTED, …). Se aceptan los dos por si el endpoint
# devolviera el del pago.
#
# Se clasifica acá y no en el navegador porque de esta clasificación depende dar una venta por
# cobrada, también cuando el cajero fuerza la terminación, y eso tiene que poder probarse. Un
# estado que no está en la tabla es 'unknown': el POS lo trata como una espera, nunca como un cobro.
#
# BLOCKED es un rechazo y no un bloqueo de seguridad: Nave lo define como "intención bloqueada por
# fraude o intentos excedidos", y el caso corriente es una tarjeta sin fondos que agotó los
# intentos. Un fraude se distingue por el motivo del pago (`nave_reason`), no por este estado.
NAVE_OUTCOME_BY_STATUS = {
    'SUCCESS_PROCESSED': 'approved',
    'APPROVED': 'approved',
    'FAILURE_PROCESSED': 'rejected',
    'REJECTED': 'rejected',
    'BLOCKED': 'rejected',
    # Cancelada en la terminal, vencida por el tope propio de la terminal, o porque Nave no pudo
    # avisarle al equipo.
    'DISABLED': 'disabled',
    'CANCELLED': 'disabled',
    'EXPIRED': 'expired',
    'PENDING': 'pending',
    'PROCESSED': 'pending',
    'PROCESSING': 'pending',
}

# Motivo de baja que Odoo informa al cancelar un cobro desde el punto de venta.
#
# La descripción NO es texto libre, aunque la documentación de Nave la presente así: Nave exige un
# texto fijo para cada código, comparado exacto y con mayúsculas, y rechaza cualquier otro con
# `400 validation_exception "Invalid input reason"`. Con una descripción propia ("Cancelado desde
# Odoo POS") Nave rechazó todas las cancelaciones, y la terminal siguió cobrando (C4). Pares
# verificados en `docs/nave_codigos_referencia.md` §5.
#
# `disabled_from_saas` es la baja pedida por el sistema del comercio. No confundir con
# `manual_disabled_by_user`, que es la baja hecha en la terminal.
NAVE_CANCEL_REASON = {'code': 'disabled_from_saas', 'description': 'disabled from SAAS'}

# Desenlaces en los que el cobro ya terminó, salga bien o mal. Al llegar a uno de ellos el POS deja
# de consultar, así que es el momento de dejar registrado el desenlace.
NAVE_FINAL_OUTCOMES = {'approved', 'rejected', 'disabled', 'expired'}

# Cuánto vale una intención de cobro presencial, en segundos. Cinco minutos es holgado con el
# cliente parado frente a la caja, y es la cota de cuánto puede quedar la terminal esperando.
#
# El punto de venta deriva de acá su propio tope de espera, así que este es el único lugar donde
# se declara: tenerlo repetido en el navegador hacía que un cambio desincronizara los dos en
# silencio, y el síntoma era que el cajero recibía el aviso equivocado al vencer un cobro.
NAVE_INTENT_DURATION_SECONDS = 300


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    def _get_payment_terminal_selection(self):
        return super()._get_payment_terminal_selection() + [
            ('nave', 'Nave Point'),
            ('nave_qr', 'Nave QR'),
        ]

    nave_terminal_id = fields.Char(
        string='ID del punto de venta en Nave',
        help='Identificador del dispositivo con el que cobra este método: la terminal Nave Point o '
             'el QR físico.\n'
             'Se copia del archivo POS_ID-<CUIT>.xlsx que se descarga desde Nave › Integraciones › '
             'Sistema de gestión › Descargar archivo:\n'
             '- Nave Point: la fila con Medio de cobro NAVE POINT cuyo Nombre/N° de serie es el '
             'número de serie impreso en la terminal.\n'
             '- QR: la fila con Medio de cobro QR del local que corresponda (Nombre del local), con '
             'el nombre de ese QR.\n'
             'Cada identificador sirve para un solo medio de cobro: si se carga el de otro, Nave '
             'rechaza el cobro con invalid_pos.',
        copy=False
    )

    nave_fast_payments = fields.Boolean(
        string='Enviar el total al seleccionar',
        default=True,
        help='Activo: al tocar el método de pago se envía el saldo completo a la terminal, sin '
             'pasar por el teclado numérico. Es lo más rápido para el cajero en una venta común.\n'
             'Desactivalo si necesitás cobros divididos: así el cajero escribe primero cuánto va '
             'por este medio (por ejemplo $500 con tarjeta) y recién ahí se envía a la terminal.',
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Carga los campos necesarios en el frontend (JS/OWL)."""
        params = super()._load_pos_data_fields(config_id)
        params += ['nave_terminal_id', 'nave_fast_payments']
        return params

    def _nave_payment_type(self):
        """ Tipo de pago de Nave según la terminal configurada.

        Cada tipo tiene su endpoint, su host de sandbox y su propio pos_id.
        """
        self.ensure_one()
        return 'static_qr' if self.use_payment_terminal == 'nave_qr' else 'smart_pos'

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
        payment_type = payment_method._nave_payment_type()
        token = provider._nave_get_access_token()
        base_url = provider._nave_get_api_url(payment_type)

        api_url = f"{base_url}/api/payment_request/{payment_type}"
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
            'duration_time': NAVE_INTENT_DURATION_SECONDS,
        }

        if payment_type == 'static_qr':
            # Obligatorio para QR: indica que el monto viene cerrado y el cliente no lo edita.
            payload['transactions'][0]['qr_amount'] = 'close'

        headers = {
            'Authorization': f"Bearer {token}",
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        destino = 'al QR' if payment_type == 'static_qr' else 'a la terminal'
        _logger.info("[pos_nave] Enviando el cobro %s %s (Ref: %s)", destino, pos_id, reference)

        timeout = payment_method._nave_timeout('intent')

        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            # El punto de venta necesita saber cuánto vale esta intención para no dejar de esperar
            # antes de que Nave alcance a informar que venció. Viaja con la respuesta y no con la
            # configuración del método porque describe esta intención, no cómo está configurado el
            # medio de cobro.
            data['nave_duration_seconds'] = NAVE_INTENT_DURATION_SECONDS
            return data
        except requests.exceptions.RequestException as e:
            response = getattr(e, 'response', None)
            _logger.error(
                "[pos_nave] Nave no aceptó el cobro %s %s (HTTP %s). Respuesta: %s",
                destino, pos_id, getattr(response, 'status_code', '-'), self._nave_error_body(e) or e,
            )
            provider._nave_log_invalid_pos(e, payment_type, pos_id)
            return {'error': True, 'message': self._nave_intent_error_message(e)}

    @api.model
    def nave_check_payment_status(self, payment_method_id, intent_id):
        """
        Llamada desde el JS del POS (Polling) para consultar el estado de la intención de pago Smart POS.
        Endpoint: GET /api/payment_requests/{payment_request_id}

        OJO: este endpoint devuelve el estado de la INTENCIÓN (PENDING, PROCESSED,
        SUCCESS_PROCESSED, FAILURE_PROCESSED, DISABLED, EXPIRED, BLOCKED), que NO es el mismo
        vocabulario que el del PAGO (APPROVED, REJECTED, ...) que devuelve
        GET /ranty-payments/payments/{payment_id}. La clasificación está en NAVE_OUTCOME_BY_STATUS.
        """
        if not self.env.user.has_group('point_of_sale.group_pos_user'):
            raise AccessError(_("No tienes permisos para consultar solicitudes a Nave."))

        payment_method = self.browse(payment_method_id)
        provider = payment_method._get_nave_payment_provider()
        payment_type = payment_method._nave_payment_type()
        token = provider._nave_get_access_token()
        base_url = provider._nave_get_api_url(payment_type)

        api_url = f"{base_url}/api/payment_requests/{intent_id}"

        headers = {
            'Authorization': f"Bearer {token}",
            'Accept': 'application/json',
        }

        timeout = payment_method._nave_timeout('status')

        try:
            response = requests.get(api_url, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            _logger.debug("[pos_nave] Estado de intención %s: %s", intent_id, data)

            # La intención expone el pago asociado en payment_attempts. Lo adjuntamos para que el
            # POS pueda guardar el payment_id correcto e imprimir los datos de la tarjeta sin
            # tener que hacer otra vuelta al servidor.
            payment_id = self._nave_extract_payment_id(data)
            if payment_id:
                data['nave_payment_id'] = payment_id
                payment = self._nave_fetch_payment(provider, payment_id, payment_type)
                if payment:
                    data['nave_payment'] = payment
            data['nave_outcome'] = self._nave_outcome(intent_id, data)
            reason = self._nave_resolve_reason(data)
            if reason:
                data['nave_reason'] = reason
            self._nave_log_outcome(intent_id, data)
            return data
        except requests.exceptions.RequestException as e:
            # Nave responde 400 `payment_request_is_disabled` cuando la intención fue dada de baja,
            # por ejemplo porque no pudo notificar a la terminal y la deshabilitó sola
            # (`disabled_by_user_timeout`). Eso no es un fallo de la consulta: es el desenlace del
            # cobro. Se traduce al vocabulario de estados para que el POS lo cierre como
            # corresponde en vez de mostrar un error técnico.
            if self._nave_error_code(e) == 'payment_request_is_disabled':
                # Se registra el cuerpo entero porque todavía no sabemos si Nave informa acá el
                # motivo de la baja, que sí documenta: si lo trae, el log lo muestra y lo usamos.
                _logger.info(
                    "[pos_nave] La intención %s fue dada de baja en Nave. Respuesta: %s",
                    intent_id, self._nave_error_body(e),
                )
                # El nombre del error HTTP no se informa como motivo: no es un motivo de negocio,
                # y copiarlo hacía que el cajero leyera `payment_request_is_disabled` en pantalla.
                data = {
                    'id': intent_id,
                    'status': {'name': 'DISABLED'},
                    'nave_outcome': 'disabled',
                }
                reason = self._nave_disabled_reason(self._nave_error_payload(e))
                if reason:
                    data['nave_reason'] = reason
                self._nave_log_outcome(intent_id, data)
                return data
            _logger.error("[pos_nave] Error consultando estado en Nave: %s", e)
            return {'error': True, 'message': self._nave_error_message(e)}

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers internos
    # ──────────────────────────────────────────────────────────────────────────

    def _nave_timeout(self, kind):
        """ Timeout en segundos para una llamada a Nave, con override por parámetro de sistema. """
        default = NAVE_TIMEOUTS[kind]
        param = self.env['ir.config_parameter'].sudo().get_param(
            f'pos_nave.timeout_{kind}', default
        )
        try:
            return int(param)
        except (TypeError, ValueError):
            _logger.warning(
                "[pos_nave] pos_nave.timeout_%s no es un entero (%r). Se usa %s.",
                kind, param, default,
            )
            return default

    def _nave_http_hint(self, status_code):
        """ Mensaje para el cajero cuando Nave no explica el error.

        Los 5xx y las páginas de error HTML no traen nada aprovechable, y volcarle el cuerpo crudo
        a alguien que está cobrando sólo lo asusta. Se le dice qué pasó y qué puede hacer.
        """
        if status_code in (401, 403):
            return _(
                "Nave rechazó las credenciales del comercio (error %s). "
                "Avisá al administrador: el cobro no se puede hacer hasta que se corrijan.",
                status_code,
            )
        if status_code == 404:
            return _(
                "Nave no encontró el punto de venta o el cobro indicado (error %s). "
                "Verificá la configuración del método de pago.", status_code,
            )
        if status_code in (408, 504):
            return _(
                "Nave tardó demasiado en responder (error %s). Verificá que la terminal esté "
                "encendida y con conexión, y reintentá.", status_code,
            )
        if status_code >= 500:
            return _(
                "Nave no está respondiendo en este momento (error %s). Reintentá en unos segundos "
                "o cobrá por otro medio.", status_code,
            )
        return _("Nave respondió con un error %s.", status_code)

    def _nave_error_payload(self, exc):
        """ Cuerpo JSON de una respuesta de error de Nave, o {} si no lo hay o no es un objeto. """
        response = getattr(exc, 'response', None)
        if response is None:
            return {}
        try:
            payload = response.json()
        except ValueError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _nave_error_body(self, exc):
        """ Cuerpo crudo de una respuesta de error, recortado para el log. """
        response = getattr(exc, 'response', None)
        if response is None:
            return ''
        return (response.text or '')[:500]

    def _nave_reason_rejected(self, exc):
        """ True si Nave rechazó una baja por el motivo informado, y no por otra causa. """
        response = getattr(exc, 'response', None)
        if response is None or response.status_code != 400:
            return False
        return 'invalid input reason' in self._nave_error_body(exc).lower()

    def _nave_error_code(self, exc):
        """ Código de error que devuelve Nave en el cuerpo, o False si no lo trae. """
        return self._nave_error_payload(exc).get('code') or False

    def _nave_reason(self, code, source):
        """ Motivo listo para el POS: el código tal cual, para soporte, y el mensaje de Nave.

        `message` queda vacío si Nave no publica uno para ese código. El POS describe entonces la
        situación sin motivo, y el código sigue visible en el bloque de soporte.
        """
        code = str(code).strip()
        return {
            'code': code,
            'message': nave_reason_message(self.env, code),
            'source': source,
        }

    def _nave_resolve_reason(self, data):
        """ Motivo del desenlace de un cobro, o False si Nave no informa ninguno.

        Se toma del pago, que es donde Nave informa por qué se rechazó la tarjeta
        (`status.reason_code`). La intención tiene su propio motivo, que describe a la intención:
        una tarjeta sin fondos la deja en BLOCKED con "payment retries limit reached". Ese sólo se
        usa si no hay pago, y como no está en el catálogo, no llega a la explicación del aviso.
        """
        payment_status = (data.get('nave_payment') or {}).get('status') or {}
        if payment_status.get('reason_code'):
            return self._nave_reason(payment_status['reason_code'], 'payment')

        intent_status = data.get('status') or {}
        code = (
            intent_status.get('reason_code')
            or intent_status.get('reason_name')
            or self._nave_disabled_reason_code(data)
        )
        return self._nave_reason(code, 'intent') if code else False

    def _nave_disabled_reason_code(self, payload):
        """ Código del motivo de baja de una intención, si viene en `payload`.

        Nave documenta el motivo como `reason.code` y, en la notificación de la intención, como
        `disabled_reason`. Se aceptan las dos formas porque no está verificado cuál usa cada
        respuesta.
        """
        for key in ('reason', 'disabled_reason'):
            value = payload.get(key)
            if isinstance(value, dict) and value.get('code'):
                return value['code']
            if isinstance(value, str) and value.strip():
                return value
        return False

    def _nave_disabled_reason(self, payload):
        """ Motivo de baja que trae el cuerpo de un 400 `payment_request_is_disabled`, o False. """
        code = self._nave_disabled_reason_code(payload)
        return self._nave_reason(code, 'intent') if code else False

    def _nave_outcome(self, intent_id, data):
        """ Desenlace del cobro según el estado de la intención. Ver NAVE_OUTCOME_BY_STATUS. """
        status = str((data.get('status') or {}).get('name') or '').upper()
        outcome = NAVE_OUTCOME_BY_STATUS.get(status, 'unknown')
        if outcome == 'unknown':
            # Se registra para poder agregarlo a la tabla. Mientras tanto el POS sigue esperando y
            # no da nada por cobrado.
            _logger.warning(
                "[pos_nave] Nave informó un estado no contemplado para la intención %s: %r",
                intent_id, status,
            )
        return outcome

    def _nave_log_outcome(self, intent_id, data):
        """ Registra el desenlace de un cobro que llegó a un estado final.

        Es el único rastro que queda: el aviso del POS desaparece cuando el cajero lo cierra, y un
        cobro rechazado no deja ningún registro en Odoo. Lleva lo que pide la soporte para buscarlo
        del lado de Nave.
        """
        if data.get('nave_outcome') not in NAVE_FINAL_OUTCOMES:
            return
        status = str((data.get('status') or {}).get('name') or '').upper()
        reason = data.get('nave_reason') or {}
        _logger.info(
            "[pos_nave] Cobro %s terminado en %s. Intención: %s. Pago: %s. Motivo: %s (%s).",
            data.get('external_payment_id') or '-', status, intent_id,
            data.get('nave_payment_id') or '-', reason.get('code') or '-',
            reason.get('message') or 'sin mensaje publicado',
        )

    def _nave_intent_error_message(self, exc):
        """ Aviso al cajero cuando Nave no acepta crear un cobro.

        Para los errores del catálogo (`NAVE_INTENT_ERROR_MESSAGES`), el aviso dice qué pasó y qué
        hacer, y deja el código de Nave y el HTTP para soporte. Para cualquier otro, queda como
        siempre: lo que informe Nave, o la pista por código HTTP si Nave no explica nada.
        """
        payload = self._nave_error_payload(exc)
        key = nave_intent_error(payload)
        if not key:
            return self._nave_error_message(exc)
        code = str(payload.get('code') or '').strip()
        if not code or code.isdigit():
            code = str(payload.get('message') or '').strip()
        response = getattr(exc, 'response', None)
        lines = [
            self.env._(NAVE_INTENT_ERROR_MESSAGES[key]),
            "",
            _("Para soporte:"),
            _("Código: %s", code),
        ]
        if response is not None:
            lines.append(_("HTTP: %s", response.status_code))
        return "\n".join(lines)

    def _nave_error_message(self, exc):
        """ Extrae un mensaje legible de una excepción de `requests` contra la API de Nave. """
        response = getattr(exc, 'response', None)
        if response is None:
            return str(exc)

        status_code = response.status_code
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            msg = (
                payload.get('message')
                or payload.get('error')
                or payload.get('description')
            )
            detail = payload.get('detail')
            if msg and detail:
                return f"{msg}: {detail} (HTTP {status_code})"
            if msg:
                return f"{msg} (HTTP {status_code})"

        # Sin JSON aprovechable: se registra el cuerpo crudo para diagnóstico y al cajero se le
        # muestra algo que pueda accionar.
        _logger.error(
            "[pos_nave] Respuesta sin JSON de Nave (HTTP %s): %s",
            status_code, (response.text or '')[:500],
        )
        return self._nave_http_hint(status_code)

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

    def _nave_fetch_payment(self, provider, payment_id, payment_type):
        """ GET /ranty-payments/payments/{payment_id}. Devuelve el pago o False si no se pudo. """
        token = provider._nave_get_access_token()
        base_url = provider._nave_get_api_url(payment_type)
        api_url = f"{base_url}/ranty-payments/payments/{payment_id}"
        headers = {
            'Authorization': f"Bearer {token}",
            'Accept': 'application/json',
        }
        timeout = self._nave_timeout('status')

        try:
            response = requests.get(api_url, headers=headers, timeout=timeout)
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
        payment_type = payment_method._nave_payment_type()
        token = provider._nave_get_access_token()
        base_url = provider._nave_get_api_url(payment_type)

        api_url = f"{base_url}/api/payment_requests/{intent_id}"

        headers = {
            'Authorization': f"Bearer {token}",
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        payload = {'reason': dict(NAVE_CANCEL_REASON)}
        timeout = payment_method._nave_timeout('cancel')

        try:
            try:
                response = requests.delete(api_url, json=payload, headers=headers, timeout=timeout)
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                if not self._nave_reason_rejected(e):
                    raise
                # El texto del motivo no está documentado y Nave puede cambiarlo. Una baja sin
                # motivo también pasa su validación, así que la cancelación no depende de él.
                _logger.warning(
                    "[pos_nave] Nave rechazó el motivo de baja de la intención %s; se reintenta "
                    "sin motivo. Respuesta: %s", intent_id, self._nave_error_body(e),
                )
                headers_sin_cuerpo = {k: v for k, v in headers.items() if k != 'Content-Type'}
                response = requests.delete(api_url, headers=headers_sin_cuerpo, timeout=timeout)
                response.raise_for_status()
            return {'success': True}
        except requests.exceptions.RequestException as e:
            response = getattr(e, 'response', None)
            _logger.error(
                "[pos_nave] Nave no dio de baja la intención %s (HTTP %s). Respuesta: %s",
                intent_id, getattr(response, 'status_code', '-'), self._nave_error_body(e) or e,
            )
            return {'error': True, 'message': self._nave_error_message(e)}

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
        payment_type = payment_method._nave_payment_type()
        token = provider._nave_get_access_token()
        base_url = provider._nave_get_api_url(payment_type)

        api_url = f"{base_url}/api/payments/{transaction_id}"

        headers = {
            'Authorization': f"Bearer {token}",
            'Accept': 'application/json',
        }

        timeout = payment_method._nave_timeout('refund')

        try:
            response = requests.delete(api_url, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            return data
        except requests.exceptions.RequestException as e:
            _logger.error("[pos_nave] Error solicitando reembolso en Nave: %s", e)
            return {'error': True, 'message': str(e)}
