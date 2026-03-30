# Odoo Universal Development Guidelines
**TARGET VERSION:** 18.0

You are an expert Odoo Developer specialized in the Target Version defined above.
You must generate code and links respecting the specific documentation for that version.

## 0. DYNAMIC DOCUMENTATION LINKS
Always refer to the documentation matching the Target Version:
- **Coding:** `https://www.odoo.com/documentation/{VERSION}/contributing/development/coding_guidelines.html`
- **Git:** `https://www.odoo.com/documentation/{VERSION}/contributing/development/git_guidelines.html`
- **Multi-Company:** `https://www.odoo.com/documentation/{VERSION}/developer/howtos/company.html`
- **Vendor Guidelines:** `https://apps.odoo.com/apps/vendor-guidelines`
## 1. GIT GUIDELINES (Standard across v17-v19)
- **Format:** `[TAG] module: description`
- **Tags:** `[ADD]`, `[FIX]`, `[IMP]`, `[REF]`, `[REM]`.
- **Rule:** Explain the *WHY*, not just the *WHAT*.

## 2. PYTHON & ORM (Modern Standard)
- **x2many:** STRICTLY use `Command` (e.g., `Command.create()`). The old `(0,0)` syntax is considered legacy code in v17+.
- **Safety:** No SQL Injection.
- **Computed Fields:** Always `@api.depends`.
- **Multi-Company (Crucial para Módulos de Nave):**
  - Todo proveedor de pago (`payment_nave`) y punto de venta (`pos_nave`) **debe** operar de forma multi-compañía sin conflictos.
  - Asegurar que las credenciales (`nave_client_id`, `pos_id`, etc.) estén correctamente ligadas al `company_id`.
  - Agregar `company_id` a los modelos de negocio y utilizar `check_company=True` en campos relacionales.
  - UTILIZAR `self.with_company(...)` cuando la lógica dependa de configuraciones específicas por compañía.

## 3. PERFORMANCE & CYTHON (Big Data Strategy)
**Condition:** If processing >100k records or complex math.
**Protocol:**
1. Create a `.pyx` file using Cython.
2. **ISOLATION:** Pass pure Python types (lists/dicts) to Cython. NEVER pass Odoo Recordsets.
3. **FALLBACK:** Always implement a pure Python fallback method.

## 4. JAVASCRIPT (OWL 2.0 & ES Modules)
- **Header:** Files must start with `/** @odoo-module */`.
- **Framework:** Use OWL 2.0 (`useState`, `useRef`, `onWillStart`).
- **Forbidden:** Do NOT use `odoo.define` (deprecated in v17, removed/discouraged in v18+).

## 5. XML & VIEWS
- **Attributes:** 
  - ❌ **NO:** `attrs="{'invisible': ...}"` (Removed/Deprecated in v17+).
  - ✅ **YES:** `invisible="state == 'done'"` (Direct python expression).

## 6. PRE-PUSH VALIDATION (Mandatory)
Before **every** commit or `git push`, you MUST run and pass auditor tools against the specific configuration file for the project (`/home/martin/server/18/nave/setup.cfg`):
1. **Flake8** (lint): `flake8 --config=/home/martin/server/18/nave/setup.cfg payment_nave/ pos_nave/`
2. **Bandit** (security): `bandit -r payment_nave/ pos_nave/ -c /home/martin/server/18/nave/setup.cfg --exclude '*/demo,docs,tests' -ll`

**Rules:**
- If either tool reports errors, fix them BEFORE pushing or completing the task.
- Linting config MUST respect the ignores defined in `/home/martin/server/18/nave/setup.cfg`.
- Do NOT push code or mark execution tasks as completed if they break lint or security checks.