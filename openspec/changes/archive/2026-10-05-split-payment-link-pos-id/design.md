# Design

## Context

Ver `proposal.md` — Why.

El módulo ya resuelve **otra** dimensión que depende del medio de cobro: el host de la API.
`payment_provider._nave_get_api_url(payment_type=None)` devuelve el host de sandbox que corresponde
a cada medio, porque Nave Point se sirve desde `e3-api.ranty.io` y el resto desde
`api-sandbox.ranty.io`. Los llamadores le pasan el `payment_type` con el vocabulario de Nave
(`smart_pos`, `static_qr`, `ecommerce`, `payment_link`).

El `pos_id` es la segunda dimensión con la misma forma: depende del medio, lo define Nave, y los
puntos de uso ya saben a qué medio pertenecen porque eligen el endpoint.

## Goals / Non-Goals

**Goals:**

- Que el medio de cobro sea el único dato que un punto de uso necesita conocer para obtener su
  `pos_id`, igual que ya ocurre con el host.
- Que agregar el próximo medio sea agregar un campo y una entrada, no otra rama en cada llamador.

**Non-Goals:**

- Unificar `pos_nave` bajo el mismo mecanismo. Ahí el `pos_id` es del **dispositivo**, vive en
  `pos.payment.method.nave_terminal_id` y puede haber varios por medio; es una relación distinta.
- Validar contra Nave que un `pos_id` corresponda al medio declarado. No hay endpoint para eso: el
  único modo de saberlo es el `409 INVALID_POS` al intentar cobrar.

## Decisions

### Resolver el `pos_id` con la misma firma que el host

Un método en `payment.provider` que reciba el `payment_type` de Nave y devuelva el `pos_id`, en
lugar de que cada llamador lea el campo que le toca.

**Por qué**: deja los dos datos que dependen del medio —host e identidad— resueltos por el mismo
criterio y con el mismo vocabulario. Un punto de uso pide ambos pasando el mismo `payment_type`, que
ya conoce porque determina el endpoint. Si mañana Nave agrega un medio, se toca el proveedor y nada
más.

**Alternativa descartada**: que cada llamador lea el campo directamente
(`provider.nave_payment_link_pos_id` en el wizard). Es menos código ahora, pero reparte en cada
llamador la regla de qué campo corresponde a qué medio, y el fallback habría que repetirlo o
olvidarlo. Es lo que produjo este bug: dos llamadores leyendo el mismo campo sin que nadie decidiera
si eso era correcto.

### El fallback vive en la resolución, no en el llamador

Si el campo del medio está vacío, el método devuelve `nave_pos_id`.

**Por qué**: es la regla de compatibilidad del spec, y en un solo lugar no se puede olvidar en un
llamador nuevo. Además hace que el campo nuevo sea opcional sin que ningún punto de uso se entere.

**Alternativa descartada**: hacer el campo requerido y migrar copiando `nave_pos_id`. Deja a todas
las instalaciones con un valor que parece verificado y no lo está: el `pos_id` de e-commerce no es
el de link de pago salvo que Nave lo haya dicho.

### El checkout también pasa por la resolución

Aunque obtiene el mismo valor que hoy, se lo pide por el mismo camino declarando `ecommerce`.

**Por qué**: si queda leyendo el campo directo, el día que e-commerce necesite su propia variante
vuelve a aparecer el mismo bug. Y deja los dos llamadores simétricos, que es lo que hace evidente la
regla al leer el código.

## Risks / Trade-offs

- **El fallback enmascara una configuración incompleta**: un comercio con los dos medios activos y
  sólo un `pos_id` cargado no ve ningún error hasta que Nave rechaza un link con `409`. → El spec
  pide registrar medio e identificador ante ese rechazo, que es lo que permite diagnosticarlo en un
  renglón. La alternativa —fallar al generar el link— rompería instalaciones que hoy funcionan.
- **Dos campos con el mismo formato invitan a cruzarlos**: son dos UUID indistinguibles a simple
  vista. → Etiquetas por medio y ayuda que indica de dónde sale cada uno, según el spec.

## Migration Plan

El campo nace vacío y el fallback cubre ese estado, así que la actualización del módulo no requiere
intervención: las instalaciones existentes siguen comportándose igual.

En la instalación de producción, cargar el `pos_id` de LINK DE PAGO en el campo nuevo es lo que pasa
el link de pago de roto a operativo. No hay paso de datos que revertir: vaciar el campo devuelve el
comportamiento anterior.
