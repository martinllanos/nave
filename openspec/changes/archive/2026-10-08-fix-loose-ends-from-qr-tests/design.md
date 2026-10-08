# Design

## Context

- **Texto de espera.** Lo dibuja la plantilla del core `point_of_sale.PaymentScreenPaymentLines`
  cuando `line.payment_status == 'waitingCard'`, sin distinguir la terminal. `pos_nave` pone ese
  estado al crear la intención, tanto para `nave` como para `nave_qr`
  (`payment_nave.js`, `send_payment_request`).
- **Token.** `_nave_get_access_token` reusa el token si `expiry - 5 min > ahora`. Nave devuelve el
  mismo token mientras no vence, con su vida restante en `expires_in`: verificado en producción el
  2026-10-08.
- `pos_nave` no tiene `i18n/` y escribe sus textos en castellano.

## Goals / Non-Goals

**Goals:** los cinco puntos de la propuesta, sin tocar el flujo del cobro.

**Non-Goals:**

- Cambiar el estado de la línea, o agregar uno propio para el QR.
- Reintentar una llamada que falle con 401 por un token que venció en el camino. Hoy, la consulta
  del POS lo toma como una falla pasajera y repite en la vuelta siguiente, y el webhook responde 500
  y Nave reintenta. En los dos casos, la vuelta siguiente pide un token nuevo.
- El nombre de la billetera en el ticket (cambio `name-the-wallet-the-customer-used`).

## Decisions

### El texto se cambia extendiendo la plantilla, sólo para `nave_qr`

Una plantilla con `t-inherit` sobre `point_of_sale.PaymentScreenPaymentLines` reemplaza el texto del
estado `waitingCard`:

- si `line.payment_method_id.use_payment_terminal === 'nave_qr'`, *"Esperando el escaneo del QR"*;
- si no, el texto del core, sin cambios, para Nave Point y para cualquier otra terminal.

Los botones (*Forzar terminación*, *Cancelar*) no se tocan.

Alternativa descartada: **un estado propio para el QR.** El core decide qué botones mostrar según el
estado; con uno nuevo habría que reproducir toda esa lógica.

### El margen del token pasa de 5 minutos a 30 segundos

Antes de vencer, no hay forma de obtener un token distinto. El margen sólo tiene que cubrir la demora
de la llamada que lo usa, con su tope de 10 s, más el desfase de reloj. 30 s lo cubre.

En los últimos 30 s de vida, cada llamada sigue pidiendo token y recibe el mismo: a lo sumo unas
diez llamadas, una vez por día, en lugar de unas cien.

Alternativas descartadas:

- **Detectar que Nave devolvió el mismo token y no volver a pedir hasta que venza.** Necesita
  guardar más estado para ahorrar esas pocas llamadas.
- **Sin margen, con un reintento ante un 401.** Toca cada llamada a la API.

### El log y el comentario dicen lo que pasa

- El log del envío nombra el destino según el tipo: *"a la terminal"* para `smart_pos` y *"al QR"*
  para `static_qr`, con el `pos_id` como hasta ahora.
- El comentario de `close()` explica que Odoo 18 no lo llama al salir de la pantalla de pago, y que
  conviene así: el seguimiento sigue y un pago hecho mientras tanto se registra (C7c).
- El JSON roto pasa de `_logger.error` a `_logger.warning`. La respuesta sigue siendo 400.

## Risks / Trade-offs

- **[Riesgo] Un token que vence durante una llamada.** → Con 30 s de margen y un tope de 10 s por
  llamada, no debería pasar. Si pasa, la llamada siguiente lo renueva (ver Non-Goals).
- **[Trade-off] El texto del QR está fijo en castellano**, como el resto de `pos_nave`. → Se traduce
  junto con todo el módulo si alguna vez hace falta.

## Migration Plan

Subir `payment_nave` a `18.0.1.12.3` y `pos_nave` a `18.0.1.11.2`. Desplegar con el procedimiento de
siempre, actualizando **los dos** módulos, y verificar en el contenedor las versiones y los hashes.
Sin cambios de datos.
