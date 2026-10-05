# Design

## Context

Estado observado en `oracle-vps:/home/ubuntu/do-onlyone` el 2026-09-26 (motivación en proposal.md):

- **El stack es un proyecto doodba** (copier `v9.6.1`), desplegado como stack de Swarm `do-onlyone` con dos servicios, `odoo` y `db`. `stack.yaml` es la salida generada a partir de `prod.yaml` y está **sin versionar**, pero en disco contiene secretos en claro.
- **Ya está configurado como prod:** `DOODBA_ENVIRONMENT: prod`, router traefik `odoo-prod` para `www.onlyone.ar || onlyone.ar` y certresolver Let's Encrypt. En cuanto a infraestructura, la "promoción" es sobre todo cambiar datos y endurecer el stack.
- **Problemas de seguridad:**
  - `odoo/custom/src/repos.yaml` embebe un token de GitHub en las URLs de `enterprise` y `nave`, y ese token está en el **historial commiteado** de `martinllanos/do-onlyone`.
  - `ADMIN_PASSWORD` figura en claro en `stack.yaml`.
  - Postgres usa `odoo/odoo`.
  - `LIST_DB: true`.
  - `DB_FILTER: ^www.onlyone.ar` no está anclado al final y el punto no está escapado.
- **No hay backups:** `backup_dst: ""` en `.copier-answers.yml` y no hay servicio de backup en el stack.
- **El working tree de do-onlyone tiene cambios sin commitear** en `prod.yaml` y `repos.yaml`.
- **El servidor comparte recursos con otros stacks** (`evocrm`, `portainer` y `traefik`). Tiene 23 GB de RAM, 143 GB libres y 4 CPU, así que alcanza para tener dos bases conviviendo durante la transición.
- **Desde este repo no se pudo inventariar la base de homologación** (módulos instalados, compañías, tamaño): el acceso de lectura a la base remota se denegó. Queda como la primera tarea del apply.

## Goals / Non-Goals

**Goals:**

- La transición tiene una sola ventana de corte, reversible hasta el último paso destructivo, que es borrar la base de homologación.
- El nombre de base, el dominio y la `notification_url` no cambian, así que ni doodba ni Nave necesitan reconfiguración de URLs.
- Los secretos quedan fuera del control de versiones sin introducir infraestructura nueva de gestión de secretos.

**Non-Goals:**

- Arreglar B2, B6 y B12 en el código de los módulos. Tienen changes propios.
- Montar un entorno de homologación nuevo, ni local ni remoto.
- Alta disponibilidad, réplicas o monitoreo y alertas. Son candidatos a un change posterior.
- Migrar datos de negocio de homologación a producción. Por decisión explícita, la base arranca limpia.

## Decisions

### D1. Mantener el nombre de base `www.onlyone.ar` y archivar la vieja renombrándola

La base vieja se renombra (`ALTER DATABASE ... RENAME TO homologacion_archivo_<fecha>`) y su directorio de filestore se mueve al nombre nuevo. Después se crea una base limpia con el nombre original.

- **Por qué:** `PGDATABASE`, `POSTGRES_DB`, `DB_FILTER`, `.copier-answers.yml` y `domains_prod` ya usan ese nombre, así que no hay que tocar config de doodba ni regenerar con copier. Renombrar en lugar de borrar deja la base vieja **intacta y restaurable en segundos** hasta que el backup externo esté verificado (requirement "Datos de homologación archivados").
- **Por qué mover el filestore:** Odoo guarda los adjuntos en `filestore/<nombre_de_base>`. Si el directorio no se mueve, la base nueva hereda miles de archivos huérfanos de homologación.
- **Alternativa descartada: una base con nombre nuevo (ej. `onlyone_prod`).** Obliga a cambiar cinco puntos de configuración y a regenerar desde copier, sin beneficio funcional.
- **Alternativa descartada: `dropdb` después del dump.** Elimina la vuelta atrás rápida antes de haber verificado el backup.

### D2. Base nueva creada por Odoo con `--without-demo`, en `es_AR`

Se crea con `odoo -d www.onlyone.ar -i <módulos> --without-demo=all --load-language=es_AR --stop-after-init` en un contenedor one-shot del mismo stack. La lista de módulos sale del inventario de la base de homologación (tarea 1.1), filtrada a lo que usa el negocio.

- `sale_nave_simulator` **no** se instala: su motor predictivo está incompleto (`tasks/todo.md` fase 3).
- **Alternativa descartada: crearla desde el gestor web.** Exige tener `LIST_DB` activo justo en el momento en que se lo quiere cerrar.

### D3. Secretos en `.docker/*.env` (ignorados por git) y token por variable de entorno

- `ADMIN_PASSWORD` va a `.docker/odoo.env` y `PGPASSWORD`/`POSTGRES_PASSWORD` a `.docker/db-access.env` y `db-creation.env`. Son los archivos que doodba ya carga y que `.gitignore` ya excluye.
- `repos.yaml` referencia el token como `$GITHUB_TOKEN`, porque git-aggregator expande variables de entorno. El token entra al build como variable del entorno de build, no queda en ninguna capa final y no se commitea.
- `stack.yaml` se agrega a `.gitignore` y queda con permisos `600`, porque `docker compose config` expande los secretos dentro de él.
- **Token:** se usa un PAT nuevo de mínimo privilegio, solo lectura de contenido sobre `odoo/enterprise` y `martinllanos/nave`. El viejo se **revoca**. Una vez revocado, reescribir el historial de `do-onlyone` es opcional: queda como higiene y no como requisito.
- **Alternativa descartada: Docker Swarm secrets.** doodba no los consume de forma nativa y habría que envolver el entrypoint. Demasiado costo para un solo nodo.

### D4. `LIST_DB=false` y `DB_FILTER=^www\.onlyone\.ar$`

Esto cierra el gestor de bases y hace que la base archivada (D1) sea inalcanzable por HTTP durante la convivencia. Hay que cambiarlo en `prod.yaml` y en `.copier-answers.yml` (`odoo_listdb: false`, `odoo_dbfilter`), para que un futuro `copier update` no lo revierta.

### D5. Backups con el servicio de backup de doodba (duplicity) a OCI Object Storage

El template de doodba ya incluye un servicio `backup` basado en `tecnativa/docker-duplicity-postgres-s3`, que hace un dump diario de la base y el filestore, con retención configurable. Se activa definiendo `backup_dst` en copier. El destino es un bucket S3-compatible de **OCI Object Storage** en la misma tenancy de Oracle: está fuera del servidor, no agrega proveedor y cuenta con capa gratuita.

- La retención es de **30 días** (`backup_deletion` / `REMOVE_OLDER_THAN`).
- El backup se cifra con una passphrase guardada en `.docker/backup.env`, con copia fuera del servidor en el gestor de contraseñas del usuario.
- **Alternativa descartada: un `pg_dump` por cron del host a disco local.** No es "fuera del servidor", que es justamente lo que el requirement exige.
- **Si no hubiera tenancy OCI disponible**, cualquier bucket S3-compatible sirve con el mismo servicio. Solo cambian la URL y las credenciales, no las tareas.

### D6. Archivo de homologación: dump + tar, copiados a la máquina local y al bucket

El archivo de homologación se genera como `pg_dump -Fc` más un `tar` del filestore, con un checksum SHA-256, y se copia a dos lugares: la máquina local del usuario y el bucket de D5, bajo un prefijo `archivo/`. La verificación consiste en restaurarlo en el Odoo local (`/home/martin/server/18/odoo`) y abrir un adjunto.

### D7. `18.0` = producción, `18.0-dev` = integración

doodba ya consume `$ODOO_VERSION` = `18.0`, así que el cambio no toca infraestructura: es de proceso y documentación. Hay que actualizar `CLAUDE.md` (la frase "es la que consume doodba para construir la imagen del entorno de homologación") y dejar constancia en `tasks/`. El deploy es manual y queda documentado en el runbook: `git pull` del proyecto → `invoke img-build` o `docker compose -f prod.yaml build` → regenerar `stack.yaml` → `docker stack deploy`.

### D8. Orden de corte

```
 [1 inventario] -> [2 hardening sin corte] -> [3 ventana de corte] -> [4 base limpia + Nave prod]
                                                   |                          |
                                        cerrar POS, sin pending tx        [5 backups]
                                        dump + tar + verificar             |
                                        renombrar base vieja           [6 retiro base vieja]
                                                                          (solo si 3 verificado)
```

El hardening (secretos, `LIST_DB`, `DB_FILTER`) se hace **antes** de la ventana de corte y sobre la base de homologación. Así se valida que el stack endurecido levanta sin mezclar dos fuentes de falla.

## Risks / Trade-offs

- **[Riesgo] No hay sandbox utilizable.** El sandbox de Nave solo opera de 10:00 a 18:00 (mail de soporte del 2026-09-24), fuera del horario de trabajo del proyecto. → Los casos pendientes de la matriz (C2, C3, C12) se ejecutan directamente sobre la base de producción, con la terminal de producción `L40037644` (ya vinculada) y los topes de §3.11. No hay plan B en sandbox: si el corte se demora, esos casos corren sobre la base de homologación, que también opera en modo producción.
- **[Riesgo] Los rechazos no se pueden provocar a voluntad con plástico real.** → Se prueban con **tarjeta vencida o CVV incorrecto** (decisión del usuario, 2026-09-26).
- **[Riesgo] Hay un `pos_id` por tipo de pago y el módulo usa uno solo para checkout y links.** Si el tipo no coincide, Nave devuelve `409 INVALID_POS`. `payment_transaction.py:68` y `nave_link_wizard.py:186` mandan ambos `provider.nave_pos_id`, pero producción tiene `pos_id` distintos para ECOMMERCE y para LINK DE PAGO. → En la tarea 4.4 se carga el `pos_id` del ecommerce, y los links de pago quedan **fuera de servicio** hasta que un change aparte agregue el campo para links. El runbook lo documenta.
- **[Riesgo] Los `pos_id` de producción se resuelven por prueba y rotación** (decisión del usuario, 2026-09-26), no con una fuente confirmada. Un id de otra tienda del mismo comercio puede aceptar el cobro y acreditarlo bajo otro local. → Cada intento se hace por el importe mínimo y se registra la respuesta de Nave (tarea 1.5). Un cobro aceptado se verifica también en el Espacio Nave, para ver bajo qué local quedó. Los ids de sandbox (`f71ba756-…`, `b1c04ade-…`) nunca se prueban. Ninguno de los ids actuales es de tipo Nave Point, así que el de `L40037644` probablemente no salga de la rotación: si todos devuelven `INVALID_POS` o cuelgan, se pide a Nave o se baja de nuevo *Sistema de gestión*.
- **[Riesgo] Las devoluciones (B6) y el reembolso POS (B2) no funcionan.** → En producción, cualquier devolución a un cliente real hay que hacerla desde el Espacio Nave a mano y registrarla en Odoo. El runbook lo documenta. La apertura comercial plena queda condicionada a B6, y eso queda fuera de este change.
- **[Riesgo] Los cobros reales del modo acotado quedan solo en la base archivada, no en la contable de producción.** → Están en el archivo verificado (D6). Si hacen falta en los libros, se cargan como saldos iniciales en la base nueva.
- **[Riesgo] El token filtrado sigue vigente hasta el 2026-10-03**, fecha que eligió el usuario para rotarlo. Durante ese lapso, cualquiera con acceso de lectura a `martinllanos/do-onlyone` puede leer `odoo/enterprise` y `nave`. → Mientras tanto, verificar que el repo sea privado y revisar quién tiene acceso. La spec ("Secretos fuera del control de versiones") recién se cumple después de la tarea 2.2.
- **[Riesgo] Revocar el token rompe cualquier otro uso del mismo token** (otros proyectos, CI). → Antes de revocar, se busca el token en los otros proyectos del servidor (`evo-crm-enterprise`) y en la máquina local.
- **[Riesgo] Cambiar la contraseña de Postgres con el servicio corriendo corta la conexión de Odoo.** → Se hace en la ventana de hardening con un `docker stack deploy` inmediato. El rollback es volver a la contraseña anterior con `ALTER ROLE`.
- **[Trade-off] Sin homologación remota, todo cambio de código se prueba solo en local antes de llegar a producción.** → Es una decisión explícita del usuario. El webhook no se puede probar en local sin túnel, y eso queda anotado en el runbook.
- **[Riesgo] Un `copier update` futuro podría reintroducir la configuración vieja.** → D4 actualiza también `.copier-answers.yml`.

## Migration Plan

1. **Rollback antes del corte (grupos 1 y 2):** revertir el commit de `do-onlyone` y volver a desplegar.
2. **Rollback durante o después del corte, antes de borrar la base vieja:**
   1. Parar Odoo.
   2. Renombrar la base nueva a `www.onlyone.ar_fallida` y la archivada de vuelta a `www.onlyone.ar`.
   3. Mover de vuelta el filestore.
   4. Volver a desplegar.
   
   El rollback tarda minutos.
3. **Después de borrar la base vieja (grupo 6):** la única vuelta atrás es restaurar el archivo de D6.

## Open Questions

- **Qué compañías y qué datos fiscales carga producción.** Homologación trabajaba sobre la compañía 4, `(AR) Monotributista`. No cambia las tareas: hay que confirmar los datos antes de la tarea 4.2.
- **Servidor SMTP de salida** para facturas y notificaciones. Hoy `EMAIL_FROM` está vacío. El proveedor se decide en la tarea 4.3, sin afectar el resto.
