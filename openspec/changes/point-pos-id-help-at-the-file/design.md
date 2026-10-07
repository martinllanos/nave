# Design

## Context

Ver `proposal.md` — Why. Lo que condiciona el enfoque:

- Las ayudas son el atributo `help` de tres campos: `nave_pos_id` y `nave_payment_link_pos_id`, en el
  proveedor de `payment_nave`, y `nave_terminal_id`, en el método de pago de `pos_nave`. Odoo las
  muestra al pasar el cursor sobre la etiqueta del campo.
- La ayuda del punto de venta es una sola para Nave Point y para QR, porque los dos usan el mismo
  campo.
- La estructura del archivo de identificadores y los valores de *Medio de cobro* (`ECOMMERCE`, `LDP`,
  `NAVE POINT`, `QR`) salen del archivo real del comercio de homologación, descargado el 2026-10-07.
  Nave no los documenta.
- El rechazo por identidad ya se reconoce sin depender del código HTTP
  (`_nave_log_invalid_pos`). Lo que cita `409` son textos: una ayuda, tres comentarios y la spec.

## Goals / Non-Goals

**Goals:**

- Que un comercio que configura Odoo por primera vez encuentre la fila correcta del archivo sin
  ayuda de nadie.

**Non-Goals:**

- Cambiar cómo se cargan los identificadores, por ejemplo importando el archivo. Sería útil, pero
  es una funcionalidad nueva.
- Traducir las ayudas. El texto fuente queda en castellano, como el resto de los textos del módulo.

## Decisions

### La ayuda dice qué fila copiar, no sólo dónde está el archivo

Cada ayuda nombra el archivo, dice de dónde se descarga y cómo reconocer la fila de ese medio de
cobro, con los nombres de columna tal como figuran en el archivo.

*Por qué los nombres literales*: el comercio tiene el archivo abierto mientras lee la ayuda. Citar
*Medio de cobro* `ECOMMERCE` le permite filtrar la columna sin traducir nada.

*Riesgo de atarse al formato del archivo*: si Nave cambia las columnas, la ayuda queda vieja. Se
acepta: es un texto, se corrige en una versión, y mientras tanto sigue orientando mejor que *"Nave >
Integraciones"*.

### Ningún dato real

Las ayudas describen las filas por sus columnas. No incluyen identificadores, nombres de tiendas,
números de serie ni códigos de vinculación del comercio de homologación.

### Redacción propuesta

**POS ID (Tienda)**, `nave_pos_id`:

> Identificador del medio de cobro de la tienda online, que usa el checkout del e-commerce.
> Se copia del archivo `POS_ID-<CUIT>.xlsx` que se descarga desde Nave › Integraciones › Sistema de
> gestión › Descargar archivo: es la fila con *Medio de cobro* `ECOMMERCE` cuyo *Nombre/N° de serie*
> es el nombre de la tienda dada de alta en Integraciones › Tienda online propia.

**POS ID (Link de pago)**, `nave_payment_link_pos_id`:

> Identificador del medio de cobro de link de pago, que usan los links generados desde facturas y
> pedidos.
> Se copia del mismo archivo `POS_ID-<CUIT>.xlsx`: es la fila con *Medio de cobro* `LDP`.
> Nave asigna un identificador distinto a cada medio de cobro: si acá se carga el de la tienda, Nave
> rechaza el link con `invalid_pos`.
> Si se deja vacío se usa el POS ID (Tienda), que es el comportamiento anterior.

**ID del punto de venta en Nave**, `nave_terminal_id`:

> Identificador del dispositivo con el que cobra este método: la terminal Nave Point o el QR físico.
> Se copia del archivo `POS_ID-<CUIT>.xlsx` que se descarga desde Nave › Integraciones › Sistema de
> gestión › Descargar archivo:
> - Nave Point: la fila con *Medio de cobro* `NAVE POINT` cuyo *Nombre/N° de serie* es el número de
>   serie impreso en la terminal.
> - QR: la fila con *Medio de cobro* `QR` del local que corresponda (*Nombre del local*), con el
>   nombre de ese QR.
> Cada identificador sirve para un solo medio de cobro: si se carga el de otro, Nave rechaza el cobro
> con `invalid_pos`.

### Cómo se prueba

Un test por campo lee la ayuda del modelo (`_fields[...].help`) y comprueba que nombra el archivo,
la sección del portal y el valor de *Medio de cobro* que le corresponde. Que ningún texto cite
`409` se verifica con una búsqueda en el código al cerrar el cambio, no con un test: un test que lee
el fuente vigila la forma del código, no su comportamiento.

*Por qué un test sobre un texto*: la spec exige que la ayuda indique la fila, y esto es lo que
comprueba ese requisito. Comprueba las marcas que el comercio necesita encontrar, no la redacción
completa, para no fallar por una coma.

## Risks / Trade-offs

- **[Riesgo] Nave cambia el formato del archivo** → La ayuda queda desactualizada hasta la versión
  siguiente. El test no lo detecta, porque no tiene el archivo. Conviene preguntarle a Nave si el
  formato es estable (está en las notas de la reunión técnica, §8b).
- **[Trade-off] Ayudas más largas** → Odoo las muestra en un globo que se adapta al texto. Son
  cuatro o cinco líneas, que se leen una sola vez al configurar.

## Migration Plan

Ninguna. Se despliegan los dos módulos y la ayuda nueva se ve al recargar la pantalla.
