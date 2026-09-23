# Casos de uso de los cobros Nave en Odoo

> Elaborado el 2026-09-23. Complementa `tasks/plan_homologacion_nave.md`: éste define **qué se cobra
> y en qué situación**; aquél define **cómo se prueba**.

## El criterio, en dos preguntas

Elegir el flujo correcto se reduce a responder dos cosas:

1. **¿El cliente está frente al mostrador en el momento del cobro?**
2. **¿Qué documento de Odoo origina el cobro?** — un pedido web, un ticket de POS, o una factura.

Todo lo demás se deduce de ahí.

| | Cliente presente | Cliente a distancia |
|---|---|---|
| **Pedido web** | — | **Checkout e-commerce** |
| **Ticket de POS** | **Nave Point** o **QR interoperable** | — |
| **Factura o presupuesto** | Link de pago *(ver §4)* | **Link de pago** |

---

## 1. Checkout e-commerce

**Situación**: el cliente compra en `www.onlyone.ar`, elige pagar con Nave y termina la compra solo,
sin que intervenga nadie del comercio.

| | |
|---|---|
| Documento Odoo | `sale.order` del sitio web |
| Endpoint | `POST /api/payment_request/ecommerce` |
| Dispara | El botón de pago del checkout de Odoo |
| Vuelve | A `/payment/status` vía `additional_info.callback_url` |
| Concilia | Webhook → `payment.transaction` → pedido confirmado |
| Canal de liquidación | Tienda online (nº de comercio `315305` / `823043843`) |

**Cómo paga el cliente**: en escritorio se le muestra un QR para escanear con billetera o app
bancaria. En celular, el checkout redirige a MODO. El ingreso manual de datos de tarjeta **depende de
que esté habilitado para el comercio** (§3.9.f del plan) — si no lo está, siempre es por billetera.

**Estado**: implementado y probado. Hay un cobro real aprobado del 2026-08-11 (§4.2 del plan).

---

## 2. Punto de venta — Nave Point (terminal)

**Situación**: venta de mostrador. El cajero arma el ticket en el POS de Odoo y el cliente paga ahí
mismo, con tarjeta o acercando el celular a la terminal.

| | |
|---|---|
| Documento Odoo | `pos.order` |
| Endpoint | `POST /api/payment_request/smart_pos` |
| Dispara | El cajero al elegir el método de pago con terminal `nave` |
| El cliente | Inserta o apoya la tarjeta en la terminal, o escanea el QR que ésta muestra |
| Concilia | **Polling** desde el POS, no webhook |
| Canal de liquidación | Nave Point (nº de comercio `315306` / `823043850`) |

**Por qué polling y no webhook**: el cajero necesita saber *ahora* si el cobro salió, para entregar
la mercadería. El POS consulta cada 3 segundos hasta que Nave resuelve, con un tope de 5 minutos.

**Lo que devuelve y termina en el ticket**: marca de tarjeta, tipo, últimos cuatro dígitos, emisor,
cupón, lote y plan de cuotas.

**Estado**: implementado. La terminal de test cobra sólo por QR; el cobro con plástico se prueba
desde el 2026-09-28 con la terminal de producción (§3.15 del plan).

---

## 3. Punto de venta — QR interoperable (QR físico)

**Situación**: la misma venta de mostrador, pero el cliente paga escaneando un **QR impreso que está
sobre el mostrador**, no la pantalla de la terminal. Sirve para cobrar sin terminal, o para tener un
segundo punto de cobro en paralelo.

| | |
|---|---|
| Documento Odoo | `pos.order` |
| Endpoint | `POST /api/payment_request/static_qr` |
| Dispara | El cajero al elegir el método de pago con terminal `nave_qr` |
| El cliente | Escanea el QR del mostrador con cualquier billetera o app bancaria |
| Concilia | Polling, igual que Nave Point |

**La diferencia clave con el QR de la terminal**: el QR físico es **fijo**. No se genera uno por
venta: la intención le *asigna un monto* al QR que ya está pegado en el mostrador. Por eso cada QR
tiene su propio `pos_id` y hay que darlos de alta en el panel de Nave.

**Estado**: implementado el 2026-09-22. Falta el `pos_id` de un QR para probarlo (hay dos dados de
alta en el local: "QR 1" y "QR 2").

---

## 4. Link de pago desde una factura

**Situación**: se emitió una factura y el cliente no está pagando en ese momento. Puede ser un
cliente de cuenta corriente, una venta telefónica, una seña, o una factura que se manda por WhatsApp.

| | |
|---|---|
| Documento Odoo | `account.move` (factura) o `sale.order` (presupuesto) |
| Endpoint | `POST /api/payment_request/payment_link` |
| Dispara | El wizard *Generar Link de Pago*, desde el menú Acción del documento |
| El cliente | Abre el link y paga desde donde esté, dentro del plazo configurado |
| Concilia | Webhook → la transacción que el wizard creó → factura pagada |
| Canal de liquidación | Tienda online |

**El plazo** se configura al generar el link (`duration_hours`). El panel de Nave ofrece 24 h, 48 h o
7 días; la API admite cualquier valor. Cada link es **único y de un solo uso**.

**Estado**: implementado, y desde `b334209` el link queda respaldado por una `payment.transaction`,
que es lo que permite que el webhook lo concilie. Antes el cobro se hacía y la factura quedaba impaga.

### 4.1 El caso híbrido: link de pago con el cliente presente

Es posible mostrarle el QR del link de pago en una pantalla del mostrador, o imprimirlo en la
factura, y que el cliente lo escanee ahí mismo. Técnicamente funciona: la respuesta del link trae
`qr_data`, una cadena que se dibuja como QR donde uno quiera.

**Pero no es un cobro presencial a los ojos de Nave.** Se liquida por el canal online, con el número
de comercio de la tienda, no con el de Nave Point. Como los números de comercio son distintos por
canal, **los aranceles y plazos de acreditación pueden diferir**.

Antes de usar esto como reemplazo del cobro de mostrador, conviene que Comercial confirme el cuadro
de aranceles de cada canal con Nave. Técnicamente está a un paso; la pregunta es si conviene.

**Estado**: no implementado. Hoy el wizard descarta el `qr_data` que Nave devuelve.

---

## 5. Qué cubre cada uno, en una línea

- **Checkout**: el cliente se cobra solo, en la web.
- **Nave Point**: el cajero cobra, con la terminal en la mano.
- **QR interoperable**: el cajero cobra, sin terminal, con el QR del mostrador.
- **Link de pago**: el cobro no ocurre ahora — se manda y se espera.

## 6. Lo que NO cubre ninguno hoy

- **Devoluciones**: congeladas. El endpoint que usábamos desapareció de la documentación vigente de
  Nave (pregunta N12, en el hilo abierto con ellos).
- **Cobro recurrente / suscripciones**: no hay tokenización. Cada cobro exige una acción del cliente.
- **Pago parcial de una factura**: el link se genera por un monto; no hay flujo de cuotas o señas
  parciales contra el mismo documento.
- **Cobro presencial con liquidación online**, o al revés: el canal lo determina el flujo elegido.
