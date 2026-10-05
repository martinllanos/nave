# Spec Delta

## Purpose

Define el entorno productivo de Odoo 18 de OnlyOne en `oracle-vps`: qué sirve, cómo protege el acceso y los secretos, desde qué código se construye, cómo se recupera ante pérdida de datos y en qué modo opera la pasarela Nave.

## ADDED Requirements

### Requirement: Dominio y base servidos

El entorno de producción SHALL servir `www.onlyone.ar` y `onlyone.ar` sobre HTTPS con un certificado válido, y SHALL resolver todas las peticiones contra una única base de producción. No SHALL ser posible seleccionar ni alcanzar otra base del cluster a través del dominio.

#### Scenario: Acceso público por HTTPS

- **WHEN** un cliente abre `https://www.onlyone.ar` o `https://onlyone.ar`
- **THEN** recibe el sitio de la base de producción con un certificado TLS válido

#### Scenario: Otra base en el mismo cluster

- **WHEN** existe en el cluster Postgres una base con otro nombre (por ejemplo, la base de homologación archivada durante la transición)
- **THEN** ninguna URL pública del dominio permite abrirla ni loguearse en ella

### Requirement: Gestor de bases no expuesto

El entorno de producción MUST NOT exponer públicamente el gestor de bases de Odoo (listado, creación, duplicado, backup, restauración o borrado de bases).

#### Scenario: Acceso al gestor de bases

- **WHEN** alguien pide `https://www.onlyone.ar/web/database/manager` o `/web/database/selector`
- **THEN** el servidor no muestra el listado de bases ni permite operar sobre ellas

### Requirement: Secretos fuera del control de versiones

Las credenciales del entorno (contraseña maestra de Odoo, contraseña de Postgres y tokens de acceso a repositorios) MUST NOT aparecer en archivos versionados del proyecto de despliegue. Toda credencial que haya estado alguna vez en el historial versionado MUST quedar revocada o rotada. La contraseña maestra y la de Postgres MUST NOT ser valores por defecto ni triviales.

#### Scenario: Revisión del repositorio de despliegue

- **WHEN** se busca en los archivos versionados y en el historial de `martinllanos/do-onlyone` cualquier token o contraseña en uso
- **THEN** no se encuentra ninguna credencial vigente

#### Scenario: Token filtrado previamente

- **WHEN** alguien intenta usar el token de GitHub que figuraba en el historial de `repos.yaml`
- **THEN** GitHub lo rechaza por revocado

### Requirement: Producción se construye desde la rama 18.0

La imagen de producción SHALL construirse con el código de los módulos Nave de la rama `18.0` del repo `martinllanos/nave`. El trabajo en curso SHALL integrarse en `18.0-dev` y MUST llegar a `18.0` solo cuando esté listo para producción.

#### Scenario: Build de la imagen

- **WHEN** se construye la imagen de producción
- **THEN** los módulos `payment_nave` y `pos_nave` coinciden con el último commit de `18.0` al momento del build

### Requirement: Backups de producción recuperables y fuera del servidor

El entorno SHALL respaldar diariamente la base de producción y su filestore en un destino fuera de `oracle-vps`, con retención de al menos 30 días. Un backup SHALL considerarse válido solo si se demostró que restaura en un Odoo funcional.

#### Scenario: Backup diario

- **WHEN** pasan 24 horas desde el último backup
- **THEN** existe en el destino externo un backup nuevo que contiene base y filestore

#### Scenario: Pérdida del servidor

- **WHEN** `oracle-vps` o sus volúmenes se pierden
- **THEN** la base y el filestore se pueden restaurar desde el destino externo con una pérdida de a lo sumo 24 horas de datos

#### Scenario: Prueba de restauración

- **WHEN** se restaura un backup en un entorno aparte
- **THEN** Odoo levanta, permite loguearse y los adjuntos del filestore se abren

### Requirement: Base de producción sin datos de homologación

La base de producción SHALL arrancar limpia: MUST NOT contener transacciones, pedidos, asientos, sesiones POS ni tokens provenientes de la base de homologación o del sandbox de Nave.

#### Scenario: Estado inicial de la base

- **WHEN** se inspecciona la base de producción recién creada, antes de la primera operación real
- **THEN** no hay transacciones de pago, pedidos, asientos contables ni sesiones POS, y el token cacheado de Nave está vacío

### Requirement: Nave opera en modo producción

En la base de producción, el proveedor Nave SHALL estar habilitado (no en modo prueba), SHALL usar credenciales de producción y SHALL tener cargado el `pos_id` de producción del punto de venta ECOMMERCE. El método de pago POS de Nave SHALL usar el `pos_id` de la terminal de producción. Los webhooks de Nave SHALL seguir llegando a `https://www.onlyone.ar/payment/nave/webhook`.

#### Scenario: Primer cobro online

- **WHEN** se paga un pedido web por el importe mínimo con el proveedor Nave
- **THEN** la intención se crea contra la API de producción de Nave, el webhook llega y la transacción queda `done` en Odoo

#### Scenario: Primer cobro presencial

- **WHEN** se cobra desde el POS con la terminal de producción por el importe mínimo
- **THEN** la terminal recibe la intención y el pago queda confirmado en la sesión POS

### Requirement: Datos de homologación archivados y recuperables

Antes de retirar la base de homologación, su contenido (base y filestore) SHALL quedar respaldado fuera del servidor, y SHALL haberse verificado que el respaldo restaura. Esto incluye los cobros reales hechos en el modo de producción acotada. La base de homologación MUST NOT borrarse del servidor hasta que ese respaldo esté verificado.

#### Scenario: Retiro de la base de homologación

- **WHEN** se borra la base de homologación del cluster de producción
- **THEN** existe un respaldo externo de esa base y su filestore que ya se restauró con éxito al menos una vez
