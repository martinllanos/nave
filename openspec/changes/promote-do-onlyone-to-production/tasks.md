# Tasks

> Todo lo que opera sobre `oracle-vps` se hace por SSH en `/home/ubuntu/do-onlyone`. Los pasos destructivos (renombrar o borrar bases, revocar el token) se confirman con el usuario en el momento de ejecutarlos.

## 1. Inventario y preparación

- [ ] 1.1 Inventariar la base de homologación: módulos instalados, compañías, tamaño de la base y del filestore, transacciones Nave por estado y sesiones POS abiertas. Verificar: la lista queda anotada en design.md (Context) y define los módulos de D2.
- [ ] 1.2 Commitear o descartar los cambios pendientes del working tree de `do-onlyone` (`prod.yaml`, `repos.yaml`) para partir de un estado limpio. Verificar: `git status` limpio y `git log` muestra el commit.
- [ ] 1.3 Buscar el token de GitHub actual en otros proyectos del servidor (`evo-crm-enterprise`) y en la máquina local, para saber qué se rompe al revocarlo. Verificar: la lista de usos queda anotada en esta tarea.
- [ ] 1.4 Crear el bucket de OCI Object Storage (D5) con sus credenciales S3-compatibles y una passphrase de cifrado. Verificar: un `aws s3 ls` (o equivalente) contra el bucket responde desde `oracle-vps`.
- [ ] 1.5 Confirmar que se tienen las credenciales productivas y resolver los `pos_id` de producción **por prueba y rotación**, usando los que ya hay en la tabla de `pos_id` (decisión del 2026-09-26). Se prueba un id por vez con un cobro por el importe mínimo y se anota qué respondió Nave: `409 INVALID_POS` significa tipo de pago equivocado; un cuelgue hasta el timeout significa un id válido sin dispositivo que lo atienda (§3.13); `done` significa el id correcto. Los ids de sandbox no entran en la rotación. Verificar: cada fila de producción de la tabla queda marcada como confirmada o descartada, con la respuesta observada.

## 2. Hardening del stack (sin corte, sobre la base de homologación)

- [ ] 2.1 Generar el PAT nuevo de mínimo privilegio y reemplazar el embebido en `repos.yaml` por `$GITHUB_TOKEN`, que se pasa en el entorno de build (D3). No depende de la revocación: se puede hacer con el token actual y cambiar sólo el valor de la variable el 2026-10-03. Verificar: un build de la imagen clona `enterprise` y `nave`, y `grep -r ghp_` sobre los archivos versionados no devuelve nada.
- [ ] 2.2 **El 2026-10-03** (fecha acordada), revocar el token viejo en GitHub y actualizar los otros usos detectados en 1.3. Verificar: `git ls-remote` con el token viejo falla por autenticación.
- [ ] 2.3 Mover `ADMIN_PASSWORD` a `.docker/odoo.env` con un valor nuevo fuerte, y agregar `stack.yaml` a `.gitignore` con permisos `600`. Verificar: `git grep ADMIN_PASSWORD` no muestra valores y el login al gestor con la contraseña vieja falla.
- [ ] 2.4 Cambiar la contraseña del rol `odoo` de Postgres (`ALTER ROLE`) y actualizar `.docker/db-access.env` y `db-creation.env`. Verificar: Odoo reconecta tras `docker stack deploy` y el sitio responde 200.
- [ ] 2.5 Poner `LIST_DB=false` y `DB_FILTER=^www\.onlyone\.ar$` en `prod.yaml` y en `.copier-answers.yml` (D4). Verificar: `/web/database/manager` y `/web/database/selector` ya no listan bases, y `https://www.onlyone.ar` sigue respondiendo 200.
- [ ] 2.6 Commitear y pushear el hardening en `do-onlyone`, regenerar `stack.yaml` y desplegar. Verificar: `docker service ls` muestra `do-onlyone_odoo` 1/1 y el webhook responde al preflight OPTIONS.

## 3. Ventana de corte: archivar homologación

- [ ] 3.1 Cerrar la sesión POS abierta y dejar sin transacciones Nave en `pending` (resolver o cancelar cada una). Verificar: una consulta SQL devuelve 0 sesiones abiertas y 0 transacciones `pending`.
- [ ] 3.2 Parar Odoo (`docker service scale do-onlyone_odoo=0`), generar `pg_dump -Fc` de la base y un `tar` del filestore, y calcular el SHA-256 de ambos (D6). Verificar: los archivos existen y sus checksums quedan anotados.
- [ ] 3.3 Copiar el archivo a la máquina local y al bucket, bajo `archivo/`. Verificar: los checksums coinciden en los tres lugares.
- [ ] 3.4 Restaurar el archivo en el Odoo local y abrir una transacción Nave y un adjunto. Verificar: login correcto, las 3 transacciones de agosto visibles y el adjunto abre.
- [ ] 3.5 Renombrar la base a `homologacion_archivo_<fecha>` y mover `filestore/www.onlyone.ar` al mismo nombre (D1). Verificar: `psql -l` muestra la base renombrada y `filestore/www.onlyone.ar` ya no existe.

## 4. Base de producción limpia y Nave en producción

- [ ] 4.1 Crear la base `www.onlyone.ar` con un contenedor one-shot: `--without-demo=all`, `es_AR`, los módulos de 1.1 más `payment_nave` y `pos_nave`, sin `sale_nave_simulator` (D2). Levantar Odoo. Verificar: el login de admin funciona, no hay datos demo y la tabla `payment_transaction` está vacía.
- [ ] 4.2 Configurar la compañía de producción (datos fiscales AR, plan contable, diarios, website y POS) con los datos que confirme el usuario. Verificar: una factura borrador se valida sin errores de localización.
- [ ] 4.3 Configurar el servidor de correo saliente y `EMAIL_FROM`. Verificar: "Probar conexión" en Odoo da OK y un email de prueba llega.
- [ ] 4.4 Configurar el proveedor Nave: credenciales de producción, `nave_pos_id` del ECOMMERCE de `www.onlyone.ar` según la tabla de `pos_id` (resuelta en 1.5) y estado Habilitado, siguiendo el checklist de §3.11 en orden. El `pos_id` de LINK DE PAGO **no** se carga: el módulo no tiene un campo para él, así que los links quedan fuera de servicio hasta el change que lo agregue. Verificar: `nave_access_token` vacío antes del primer cobro, un cobro web por el importe mínimo termina `done` con webhook recibido, y ningún `pos_id` de sandbox figura en la base.
- [ ] 4.5 Cerrar la sesión POS si hay alguna abierta (C16) y configurar el método de pago POS de Nave con el `pos_id` de la terminal `L40037644` según la tabla de `pos_id`. El número de serie no es el `pos_id`. Verificar: el log muestra `Enviando solicitud Smart POS a la terminal <uuid de L40037644>`, la intención aparece en el equipo y un cobro presencial por el importe mínimo queda confirmado en la sesión POS.
- [ ] 4.6 Documentar en el runbook el procedimiento manual de devolución (Espacio Nave + registro en Odoo) mientras B6 y B2 sigan abiertos. Verificar: la sección existe en `docs/` y la sigue alguien que no escribió el código.

## 5. Backups de producción

- [ ] 5.1 Activar el servicio de backup de doodba contra el bucket, con cifrado y retención de 30 días (D5). Desplegarlo. Verificar: tras forzar una corrida, aparece en el bucket un backup con base y filestore.
- [ ] 5.2 Restaurar ese backup en el Odoo local. Verificar: login correcto y la transacción de 4.4 visible con su adjunto, si lo tiene.
- [ ] 5.3 Documentar en el runbook la restauración desde el bucket. Verificar: el procedimiento documentado es el mismo que se usó en 5.2.

## 6. Retiro de homologación y documentación

- [ ] 6.1 Con 3.4 verificado, borrar la base `homologacion_archivo_<fecha>` y su filestore del servidor, previa confirmación del usuario. Verificar: `psql -l` ya no la lista y el archivo sigue en el bucket y en local.
- [ ] 6.2 Escribir el runbook `docs/despliegue_produccion.md`: build, deploy, rollback de imagen, dónde viven los secretos, backups y restauración (incluye lo de 4.6 y 5.3). Verificar: se puede hacer un redeploy siguiendo solo el documento.
- [ ] 6.3 Actualizar `CLAUDE.md` (`18.0` = producción, `18.0-dev` = integración) y `tasks/lessons.md` (el entorno de `oracle-vps` ahora es producción). Verificar: ninguna mención de "homologación" describe el entorno actual como tal.
- [ ] 6.4 Marcar en `tasks/plan_homologacion_nave.md` las secciones §3.1 y §3.11 como históricas y agregar el estado nuevo. Actualizar `tasks/todo.md` (E2 y el cutover). Verificar: `tasks/todo.md` refleja el corte hecho.
- [ ] 6.5 Chequeo integral contra la spec `production-environment`: recorrer cada scenario (HTTPS, gestor cerrado, sin secretos, build desde `18.0`, backup restaurado, base limpia, Nave en prod, archivo verificado). Verificar: todos los scenarios quedan marcados como comprobados en la revisión final de `tasks/todo.md`.

## Referencia: `pos_id` por ambiente

Hay un `pos_id` por local y por tipo de pago. Si el tipo no coincide, Nave responde `409 INVALID_POS`.

| `pos_id` | Local / medio de cobro | Ambiente | Uso en producción |
|---|---|---|---|
| `f71ba756-1d80-4ab3-9f43-5dc247fd6c4a` | Mail de credenciales sandbox (2026-06-18). Es también el UUID de ejemplo de la doc de Nave | Sandbox | **Nunca** |
| `b1c04ade-dec9-4ca0-9fd9-8464c9006764` | Terminal `L40000978` (DEBUG) | Sandbox | **Nunca** |
| `b4c94f29-0910-448e-9ad7-6dd2f791a957` | WOOCOMMERCE / ECOMMERCE, dispositivo "Be Onlyone" | Producción | `nave_pos_id` del proveedor, **solo si** 1.5 confirma que es el local de `www.onlyone.ar` y no el de `onlyone.aureofy.net` |
| `925a1b22-fc90-47b7-a92a-cf9f621139b5` | LINK DE PAGO / LDP | Producción | Pendiente del change del `pos_id` de links |
| (pendiente, 1.5) | Terminal Nave Point `L40037644`, ya vinculada | Producción | `nave_terminal_id` del método de pago POS |

