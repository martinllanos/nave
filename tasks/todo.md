# Plan de Desarrollo Odoo 18 - Integración API Nave

## Fase 1: Planificación y Diseño (SDD)
- [x] Analizar funcionalidades de Cobros Online (Nave Checkout / Link)
- [x] Analizar funcionalidades de Pagos Presenciales (Nave Point / QR)
- [x] Absorber estándares Odoo 18 (OWL 2.0, Python ORM, Vistas XML)
- [x] Elaborar y aprobar el Implementation Plan (Spec Driven Development)
- [ ] Armar entorno de desarrollo local (Repositorios Odoo 18.0 y Enterprise)

## Fase 2: Módulo `payment_nave` (Cobros Online)
- [x] Configurar estructura del módulo y dependencias (`payment`).
- [x] `payment.provider`: Campos para API Keys, ambiente (Sandbox/Prod), vistas de configuración.
- [x] **[NUEVO]** `payment.method`: Configurar y vincular los métodos de pago soportados (Tarjetas, QR, etc.) para su correcta visualización y filtrado en el checkout.
- [x] `payment.transaction`: Generación de payloads, firma de datos y llamadas a Nave API para crear Intención de Pago.
- [x] **[NUEVO]** Reembolsos / Anulaciones: Implementar lógica de reembolso (`_refund`) en `payment.transaction` para anular cobros en Nave ante notas de crédito en Odoo.
- [x] Controladores (`controllers/main.py`): Manejar redirecciones y webhooks (S2S), **incluyendo validación estricta de firma/hash para evitar falsificaciones**.
- [x] Enlace de Pagos (Facturas / Pedidos): Wizard `nave.payment.link.wizard` con acciones en Facturas y Pedidos de Venta.
- [x] Tests Funcionales: 10 tests cubriendo auth/caché, checkout, webhook aprobado/rechazado, reembolso y wizard de link.

## Fase 3: Módulo `pos_nave` (Pagos Presenciales)
- [x] Configurar estructura del módulo y dependencias (`point_of_sale`).
- [x] `pos.payment.method`: Añadir configuración de `nave_terminal_id` y claves de API.
- [x] Cliente JS/OWL (`payment_nave.js`): Implementar integración extendiendo la nueva arquitectura `PaymentPlugin` del `pos_store` (Odoo 18), métodos `send_payment_request`, `send_payment_cancel`.
- [x] Lógica de Polling JS: Bucle (interval) para consultar el estado del pago a Nave Cloud (`in_progress`, `approved`, etc.).
- [x] **[NUEVO]** Contingencia POS (Fallbacks): Implementar botón de "Re-consultar Estado" / "Forzar Aprobación" en caso de pérdida de conexión durante el polling.
- [x] Flujo UI en Odoo POS: Vistas y mensajes de estado para el cajero (OWL).
- [x] **[NUEVO]** Reembolsos POS: Implementar la reversión de pago hacia la terminal Nave al procesar una devolución de pedido en el POS.
- [x] Conciliación Backend: Guardar `transaction_id` devuelto en el pago del POS.
- [x] Tests Funcionales: Simulación de respuestas de la API de Nave para cobro exitoso, rechazo, y timeout.

## Fase 4: Módulo `sale_nave_simulator` (Simulador de Cuotas & Listas de Precios)
- [x] Crear estructura del módulo dependiente de `sale` y `product`.
- [x] `product.pricelist`: Añadir campos configurables para aplicar recargos basados en la parametrización de Nave (Medio de pago, Plazo, Cuotas).
- [x] `nave.commission.rule`: Crear modelo intermedio para guardar las métricas.
- [x] **[NUEVO]** Vistas ABM para `nave.commission.rule`: Crear interfaces (Tree/Form views y un menú accesible) que permitan a administradores mantener y actualizar dinámicamente las tasas de interés y comisiones sin tocar código.
- [ ] Motor predictivo: Script Python/ORM para calcular el precio final necesario para que el Payout (Neto) iguale el precio base del producto.
- [ ] Integración UI Backend: Modificación en vista de Listas de Precios (Form/List) para previsualizar el impacto del recargo financiero y seleccionar la regla.

## Fase 5: Homologación con Nave
> Plan detallado: `tasks/plan_homologacion_nave.md` (matriz de casos, evidencias y preguntas abiertas).

### Bloqueantes previos (no se puede homologar sin esto)
- [x] **B11** 🔴🔴 *(fix aplicado 2026-09-21, pendiente de verificación contra sandbox — casos S2/S3)* El POS consulta `GET /api/payment_requests/{id}` (estados de la **intención**: `SUCCESS_PROCESSED`, `FAILURE_PROCESSED`, `EXPIRED`…) pero el JS evalúa estados del **pago** (`APPROVED`, `REJECTED`). `APPROVED` nunca aparece en ese endpoint → **el camino feliz del Smart Point es inalcanzable** y el polling gira para siempre. Prioridad máxima, antes que B4.
  - Aplicado: catálogo `NAVE_STATUS` con los 7 estados de intención documentados + los del pago como alias tolerado; manejo explícito de `EXPIRED`, `DISABLED` y `BLOCKED`; estado desconocido se registra en consola y sigue esperando en vez de cortar.
  - Aplicado también **B4**: watchdog de 5 min atado al `duration_time`, tolerancia de 3 fallos de transporte seguidos antes de cortar, y distinción entre `silentCall` devolviendo `false` (error de servidor) y una respuesta válida de Nave.
  - Aplicado `close()`: al salir de la pantalla de pago se corta el temporizador, que antes quedaba vivo consultando a Nave.
  - **Sigue abierto B3**: `line.transaction_id` guarda el id de la intención. Para traer el `payment_id` real hace falta conocer la forma de la respuesta de la intención — se agregó un `_logger.debug` del payload crudo para averiguarla en la primera corrida (S3).
- [ ] **B1** El wizard de link de pago no crea `payment.transaction` → el webhook no concilia nunca.
- [ ] **B2** Reembolso POS manda `"REFUND-CIEGO"` hardcodeado: falla siempre.
- [ ] **B3** El POS guarda el id de la *intención* en `transaction_id`, no el `payment_id` del pago.
- [x] **B4** *(resuelto junto con B11)* Polling del POS sin timeout ni manejo de `EXPIRED`/`DISABLED` → loop infinito; única salida "Force done".
- [ ] **B5** SSRF: `payment_check_url` del webhook se usa sin validar el host → se puede forzar un pago aprobado.
- [ ] **B6** 🔴 El ciclo de devolución no cierra en **ningún** flujo (confirmado en alcance, D5): botón invisible en backend, `amount_to_refund` ignorado, `_set_canceled` sobre el registro equivocado, y el webhook `REFUNDED`/`CANCELLED` no modifica una tx en `done`. Además `nave_qr` declara `support_refund='partial'` y **Nave confirmó que es `full_only` (N10)**: corregir `data/payment_method_data.xml:33` + script de migración (el archivo es `noupdate="1"`) y declarar `full_only` en `_compute_feature_support_fields`.
- [ ] **B7** En el checkout sólo se ve el método QR (falta `_get_default_payment_method_codes`).
- [ ] **B8** QR interoperable presencial: **no implementado y CONFIRMADO EN ALCANCE (D4, 2026-09-21)**. Es desarrollo nuevo: endpoint `/api/payment_request/static_qr`, campo `qr_amount: "close"`, `pos_id` propio por QR físico. Homologable sin hardware vía el endpoint de simulación de sandbox (`doc_qr.md` §10).
- [ ] **B9** Sin `ir.cron` de respaldo si se pierde el webhook.
- [ ] **B10** Suite de `pos_nave` desalineada con el código (4 de 5 tests apuntan a endpoints viejos).

### Riesgo de go-live (no bloquea la homologación)
- [ ] **B12** El ambiente se deriva del `state` del provider y la URL base se recalcula en cada llamada, nunca se guarda en la transacción. Al pasar de `test` a `enabled`: se rompen las devoluciones de pagos de homologación, el token cacheado de sandbox **no se invalida** (hasta 24 h mandando token de sandbox a producción) y las credenciales son un único par de campos. Ver `plan_homologacion_nave.md` §3.7 y el checklist de cutover.

### Corrección de documentación interna
- [ ] `tasks/todo.md` Fase 2 tilda "validación estricta de firma/hash" — **Nave no firma sus webhooks**: no está implementado ni es implementable con el contrato actual. La defensa real es el GET de verificación server-side.
- [ ] Los diagramas de `docs/Modulo Nave - *.md` usan endpoints inexistentes (`/api/v1/checkouts`, `/api/integrations/payment`). El contrato real está en `tasks/doc_*.md`.

### Documentación oficial actualizada (2026-09-22)
Relevada del DevPortal de Nave. Detalle en `tasks/plan_homologacion_nave.md` y `tasks/doc_actualizada_2026-09-22.md`.
- [x] **B11 confirmado por la fuente**: la doc publica las dos tablas de estados por separado. El fix de `81c02c7` queda validado.
- [ ] 🔴 **B3 destrabado**: la respuesta de la intención trae `payment_attempts.payments[].payment_id`. Ya se puede traer el pago real, guardar el `payment_id` para devoluciones y poblar el ticket (marca, últimos 4, cupón, plan de cuotas).
- [ ] 🔴 **Host equivocado para Nave Point**: sandbox de Nave Point es `https://e3-api.ranty.io`, no `api-sandbox.ranty.io`. `_nave_get_api_url()` devuelve uno solo para los cuatro flujos. El test `test_pos_nave_payment.py:67` tenía razón; el commit `ffb524b` fue en la dirección equivocada.
- [ ] 🔴 **N12: el endpoint de devolución desapareció de la doc**. `DELETE /api/payments/{payment_id}` no aparece en ninguna de las cuatro páginas. Preguntar a Nave antes de invertir en B6.
- [ ] 🟠 **Cancelar intención puede no aplicar a `smart_pos`**: el error de baja lista sólo `payment_link, dynamic_qr, static_qr`. Verificar el caso C4.
- [ ] 🟠 **`buyer` es opcional**: dejar de mandar `'00000000'` / `'correo@temporal.com'` / `'S/D'` cuando el partner está incompleto.
- [ ] 🟢 **Simulador PCT para QR**: `PUT /qrtools/transfer_payment/simulation/payment` paga *nuestra propia* intención. Permite homologar QR end-to-end sin hardware.
- [ ] Bajar de **Nave > Integraciones > Sistema de gestión** el archivo con los IDs de puntos de venta.

### Bloqueo operativo con Nave (2026-09-21)
- [ ] 🔴🔴 **Conseguir acceso al comercio/local de prueba.** La terminal `L40000978` se identifica como dispositivo TEST y pide vincularse a un local "test" que no existe en nuestro Espacio Nave. El QR que se pudo descargar es de **producción** (`Be onlyone Jujuy - QR 1`) y **no debe usarse para pruebas**: son cobros reales. Bloquea los bloques C y H completos. Ver `plan_homologacion_nave.md` §3.10.

### Ejecución
- [ ] E0 — Correr suites, flake8 y bandit (línea de base).
- [ ] E1 — Cerrar bloqueantes B1-B6.
- [ ] E2 — Preparar entorno (base de homologación, terminal física, notification_url registrada).
- [ ] E3 — Ejecutar la matriz de casos (bloques A a G).
- [ ] E4 — Empaquetar evidencias y demo a Nave.

## Pendientes / Mejoras a Futuro
- [ ] Analizar y definir el flujo/duración de los links de pago de Nave para facturas recurrentes de suscripción (evitando la expiración de 24 horas del enlace si el cliente demora en pagar).
  - **Fuente encontrada (2026-09-21):** el panel de Nave ofrece vencimiento de **24 h, 48 h o 7 días**. No es un límite de la API (`duration_time` en segundos, default 1 semana), es la opción por defecto del panel. Poner tope de 168 h y validación en el wizard.
