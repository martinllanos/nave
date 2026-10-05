# Proposal

## Why

`www.onlyone.ar` ya cobra plata real: es el "modo producción acotada" de `plan_homologacion_nave.md` §3.11. Pero lo hace sobre una base que mezcla datos de prueba, transacciones de sandbox y cobros reales, y en un stack que no está preparado para producción. Los secretos están en texto plano, y un token de GitHub con acceso a `odoo/enterprise` quedó commiteado en el historial de `martinllanos/do-onlyone`. El gestor de bases está expuesto (`LIST_DB: true`), el filtro de base no está anclado y no hay backups.

La terminal de producción llega el 2026-09-28 (§3.15). Es el momento de convertir `do-onlyone` en el entorno productivo real, con una base limpia, antes de que se acumulen más operaciones reales sobre la base de prueba.

## What Changes

- **El stack `do-onlyone` de `oracle-vps` pasa a ser producción.** Sigue sirviendo `www.onlyone.ar` y `onlyone.ar` con la misma `notification_url` de Nave, que no hay que re-registrar.
- **BREAKING. La base actual `www.onlyone.ar` (homologación) se archiva y se apaga.** Se respaldan base y filestore, se verifica que el respaldo restaure y el respaldo se guarda fuera del servidor. No queda entorno de homologación remoto.
- **Arranca una base de producción limpia** con el mismo nombre (`www.onlyone.ar`). Se instalan los módulos y se configuran desde cero la compañía, la localización argentina y Nave: credenciales de producción, `pos_id` del ECOMMERCE y de la terminal de producción, y proveedor `enabled`.
- **Hardening del stack:**
  - Se rota el token de GitHub y se lo saca de `repos.yaml`.
  - Se cambian la contraseña maestra de Odoo y la de Postgres, que salen de los archivos versionados.
  - `LIST_DB` pasa a `false` y `DB_FILTER` se ancla a la base exacta.
- **Backups diarios** de la base de producción y su filestore, guardados fuera del servidor, con retención y una restauración probada.
- **BREAKING (flujo de trabajo). `18.0` pasa a ser la rama de producción.** Todo lo que se mergea ahí llega a producción en el próximo build. El desarrollo se integra en `18.0-dev`. Se actualizan `CLAUDE.md` y la documentación de `tasks/`, que hoy describen `18.0` como homologación.
- **Runbook de despliegue y recuperación** en `docs/`: build, deploy, rollback de imagen y restauración de backup.

## Capabilities

### New Capabilities

- `production-environment`: el entorno productivo de Odoo en `oracle-vps`. Cubre qué dominio y qué base sirve, cómo protege el acceso administrativo y los secretos, desde qué rama se construye, qué backups garantiza y cómo se configura Nave en modo producción.

### Modified Capabilities

(ninguna: no hay specs previas en el proyecto)

## Impact

- **Servidor `oracle-vps`, proyecto `/home/ubuntu/do-onlyone`** (repo `martinllanos/do-onlyone`): `prod.yaml`, `odoo/custom/src/repos.yaml`, `.docker/*.env`, `.gitignore`, el `stack.yaml` generado, los volúmenes `do-onlyone_db` y `do-onlyone_filestore`, y un servicio de backup nuevo. Todo esto vive **fuera de este repo**: el apply opera por SSH.
- **GitHub:** rotar el token personal usado para clonar `odoo/enterprise` y `nave`.
- **Este repo:** `CLAUDE.md`, `tasks/todo.md`, `tasks/plan_homologacion_nave.md` (§3.1 y §3.11 quedan históricos) y un runbook nuevo en `docs/`. No se toca código de los módulos.
- **Nave:** hay que cargar credenciales y `pos_id` de producción en la base nueva. La `notification_url` no cambia.
- **Operación:** hay que cerrar la sesión POS abierta y no dejar transacciones pendientes antes del apagado. El resto de la matriz de homologación (E3) se ejecuta sobre producción con los topes de §3.11.
- **Riesgo funcional heredado:** las devoluciones (B6) y el reembolso POS (B2) siguen rotos. Este change no los arregla y no bloquea el entorno, pero sí la apertura comercial plena (ver design.md).
