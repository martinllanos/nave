# Lessons Learned & Antigravity Rules

> [!TIP]
> Este archivo sirve para que yo (Antigravity) recuerde qué patrones seguir, qué errores evitar y cómo adaptarme mejor a tu stack tecnológico.

## 🛑 Patrones a Evitar (Anti-patterns)
*(Ejemplos: No reescribir archivos enteros si un diff es suficiente, no saltarse la verificación)*

- **No inferir el propósito de un entorno por el naming de la infraestructura.** (2026-09-20) Deduje que `do-onlyone` era producción porque el router de traefik se llama `odoo-prod`, la base se llama `www.onlyone.ar` y sirve el sitio público con movimientos contables. Es el entorno de **homologación**. El naming heredado no describe el propósito: preguntar antes de construir recomendaciones encima de esa suposición (en este caso armé una recomendación entera de "levantar una base separada" que no hacía falta).

## ✅ Patrones a Seguir (Best Practices)
*(Ejemplos: Usar subagentes para la lectura de logs pesados)*

- **Parametrización Dinámica:** Evitar el "hardcode" de tasas, comisiones o identificadores de endpoints. Siempre proveer vistas (Tree/Form) en Odoo para que los usuarios administradores (o usuarios de facturación) puedan actualizar las cambiantes tasas bancarias o financieras sin la intervención de un programador.
- **Soporte Multi-Compañía:** Dado que trabajamos en Odoo 18, siempre usar `self.with_company(...)` y propagar diligentemente el campo relacional `company_id`.
- **Elegancia en Front y Back:** En la planificación de SDD, siempre mantener mapeado tanto el comportamiento del backend (qué hace el código en ORM) como lo que se experimenta en UI.

## 🛠️ Notas de Configuración
*(Cualquier detalle sobre Docker, Odoo v18, Go o Postgres que deba recordar para optimizar el consumo de tokens y la efectividad)*

- **Chequeos de pre-push:** `flake8` anda de fábrica. `bandit` se instala con `pipx install bandit` (el sistema es PEP 668, `pip install --user` está bloqueado). El comando que estaba en `.agent/rules.md` llevaba `-c setup.cfg` y **abortaba**: bandit espera YAML en `-c` y `setup.cfg` es INI. Ya corregido. El patrón `--exclude '*/demo,docs,tests'` sí funciona — no "corregirlo" a `*/tests`, que deja de excluir.
- **`setup.cfg` con `ignore = E501,W503`** reemplaza la lista por defecto de pycodestyle y con eso **habilita W504**, que es mutuamente excluyente con W503. Por eso el código que parte línea *después* del operador marca. La solución es partir *antes* del operador (estilo que el config espera), no tocar la config.
- **Entorno de homologación Nave:** `oracle-vps` (ssh host ya configurado) → proyecto doodba en `/home/ubuntu/do-onlyone`, stack de Docker Swarm. Base única `www.onlyone.ar` con **datos de homologación**. Servicios: `do-onlyone_odoo` y `do-onlyone_db`. El router de traefik se llama `odoo-prod` por herencia, **no** indica producción.
- **Compañía de trabajo en esa base:** la 4, `(AR) Monotributista`. Ahí viven el provider Nave (`id=18`, estado `test`, publicado), el POS "Nave Smart POS" y el website `https://www.onlyone.ar`.
- **Simulador de cobros presenciales de Nave:** `navenegocios.ar/home/developers`. Genera pagos presenciales sin hardware, con cuatro desenlaces (tarjeta aprobada/rechazada, QR aprobado/rechazado), monto y `external_payment_id` a elección, y URL de webhook configurable. Genera **su propia** intención: no valida el request que arma Odoo ni el ruteo por `pos_id`.
- **Transacciones Nave del 2026-08-11 en la base:** las 3 son de Nave, no de Mercado Pago. La aprobada (`S00043-2`) dice "Billetera utilizada: MERCADO PAGO" porque es el `wallet.name` que devuelve la API — la billetera con que el cliente escaneó el QR del checkout. El provider `mercado_pago` tiene cero transacciones. Sirven como prueba de que el checkout funcionó end-to-end una vez.
- **Terminal Smart Point de homologación:** serie `L40000978`. Ojo: en la base, `pos.payment.method.nave_terminal_id` y `payment_provider.nave_pos_id` tienen el **mismo UUID** (`f71ba756-…`), o sea el `pos_id` de e-commerce. Confirmar con Nave el `pos_id` real de la terminal antes de probar cobros presenciales.
- **Despliegue de los módulos:** doodba clona el repo `nave` en build time desde `repos.yaml` (rama `$ODOO_VERSION`); dentro del contenedor quedan en `/opt/odoo/custom/src/nave` sin `.git`. Para saber qué versión está corriendo, comparar hashes de archivos contra el working tree local, no buscar un commit.
