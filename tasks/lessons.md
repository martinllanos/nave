# Lessons Learned & Antigravity Rules

> [!TIP]
> Este archivo sirve para que yo (Antigravity) recuerde qué patrones seguir, qué errores evitar y cómo adaptarme mejor a tu stack tecnológico.

## 🛑 Patrones a Evitar (Anti-patterns)
*(Ejemplos: No reescribir archivos enteros si un diff es suficiente, no saltarse la verificación)*

- *(Vacío por ahora)*

## ✅ Patrones a Seguir (Best Practices)
*(Ejemplos: Usar subagentes para la lectura de logs pesados)*

- **Parametrización Dinámica:** Evitar el "hardcode" de tasas, comisiones o identificadores de endpoints. Siempre proveer vistas (Tree/Form) en Odoo para que los usuarios administradores (o usuarios de facturación) puedan actualizar las cambiantes tasas bancarias o financieras sin la intervención de un programador.
- **Soporte Multi-Compañía:** Dado que trabajamos en Odoo 18, siempre usar `self.with_company(...)` y propagar diligentemente el campo relacional `company_id`.
- **Elegancia en Front y Back:** En la planificación de SDD, siempre mantener mapeado tanto el comportamiento del backend (qué hace el código en ORM) como lo que se experimenta en UI.

## 🛠️ Notas de Configuración
*(Cualquier detalle sobre Docker, Odoo v18, Go o Postgres que deba recordar para optimizar el consumo de tokens y la efectividad)*
