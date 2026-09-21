# Nave — Integración Odoo 18

Repo de dos módulos Odoo 18 para la pasarela de pagos Nave:

- `payment_nave` — cobros online (Nave Checkout / links de pago, webhooks, reembolsos).
- `pos_nave` — pagos presenciales (Nave Point / QR, integración POS con OWL 2.0).
- `sale_nave_simulator` — simulador de cuotas/costos en ventas.

Rama de trabajo: `18.0-dev`.

## Reglas del proyecto

Las reglas son compartidas entre agentes y viven en `.agent/` (fuente única, no duplicar acá):

@.agent/rules.md
@.agent/antigravity.md

## Estado y memoria del proyecto

- `tasks/todo.md` — plan de desarrollo por fases, con checkboxes. Mantenerlo actualizado.
- `tasks/lessons.md` — lecciones y correcciones del usuario. Leerlo al empezar y agregar patrones tras cada corrección.
- `tasks/nave_payment_implementation_plan.md` — spec de referencia (SDD).
- `docs/` — documentación funcional de Nave y el plugin WooCommerce de referencia.

## Comandos

Validación obligatoria antes de cada commit o push:

```bash
flake8 --config=setup.cfg payment_nave/ pos_nave/ sale_nave_simulator/
bandit -r payment_nave/ pos_nave/ sale_nave_simulator/ -c setup.cfg --exclude '*/demo,docs,tests' -ll
```

Levantar Odoo con este addons_path (base + enterprise + este repo):

```bash
/home/martin/server/18/odoo/odoo-bin -c odoo.conf
```

Actualizar un módulo sin levantar el server:

```bash
/home/martin/server/18/odoo/odoo-bin -c odoo.conf -d nave -u payment_nave --stop-after-init
```

Correr los tests de un módulo:

```bash
/home/martin/server/18/odoo/odoo-bin -c odoo.conf -d nave -u payment_nave --test-enable --stop-after-init
```
