# Plan de Desarrollo Odoo 18 - Integración API Nave

## Fase 1: Planificación y Diseño (SDD)
- [x] Analizar funcionalidades de Cobros Online (Nave Checkout / Link)
- [x] Analizar funcionalidades de Pagos Presenciales (Nave Point / QR)
- [x] Absorber estándares Odoo 18 (OWL 2.0, Python ORM, Vistas XML)
- [x] Elaborar y aprobar el Implementation Plan (Spec Driven Development)

## Fase 2: Módulo `payment_nave` (Cobros Online)
- [ ] Configurar estructura del módulo y dependencias (`payment`).
- [ ] `payment.provider`: Campos para API Keys, ambiente (Sandbox/Prod), vistas de configuración.
- [ ] `payment.transaction`: Generación de payloads, firma de datos y llamadas a Nave API para crear Intención de Pago.
- [ ] Controladores (`controllers/main.py`): Manejar redirecciones de retorno y webhooks (S2S).
- [ ] Enlace de Pagos (Facturas / Pedidos): Validar flujo desde el backend a través del wizard "Generar Link de pago".
- [ ] Tests Funcionales: Tests de checkout exitoso, cancelado y webhook verificado.

## Fase 3: Módulo `pos_nave` (Pagos Presenciales)
- [ ] Configurar estructura del módulo y dependencias (`point_of_sale`).
- [ ] `pos.payment.method`: Añadir configuración de `nave_terminal_id` y claves de API.
- [ ] Cliente JS JS/OWL (`payment_nave.js`): Implementar `PaymentInterface`, métodos `send_payment_request`, `send_payment_cancel`.
- [ ] Lógica de Polling JS: Bucle (interval) para consultar el estado del pago a Nave Cloud (`in_progress`, `approved`, etc.).
- [ ] Flujo UI en Odoo POS: Vistas y mensajes de estado para el cajero (OWL).
- [ ] Conciliación Backend: Guardar `transaction_id` devuelto en el pago del POS.
- [ ] Tests Funcionales: Simulación de respuestas de la API de Nave para cobro exitoso, rechazo, y timeout.

## Fase 4: Módulo `sale_nave_simulator` (Simulador de Cuotas & Listas de Precios)
- [ ] Crear estructura del módulo dependiente de `sale` y `product`.
- [ ] `product.pricelist`: Añadir campos configurables para aplicar recargos basados en la parametrización de Nave (Medio de pago, Plazo, Cuotas).
- [ ] `nave.commission.rule`: Crear modelo intermedio para guardar las métricas.
- [ ] **[NUEVO]** Vistas ABM para `nave.commission.rule`: Crear interfaces (Tree/Form views y un menú accesible) que permitan a administradores mantener y actualizar dinámicamente las tasas de interés y comisiones sin tocar código.
- [ ] Motor predictivo: Script Python/ORM para calcular el precio final necesario para que el Payout (Neto) iguale el precio base del producto.
- [ ] Integración UI Backend: Modificación en vista de Listas de Precios (Form/List) para previsualizar el impacto del recargo financiero y seleccionar la regla.
