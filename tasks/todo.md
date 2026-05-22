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
