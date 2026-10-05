# Design

## Context

Ver `proposal.md` — Why. Lo que condiciona el enfoque:

- `_get_specific_rendering_values` devuelve `{'api_url': checkout_url}` y el core de `payment`
  renderiza con eso la plantilla `redirect_form`, que hace `<form t-att-action="api_url"
  method="get">` sin campos.
- La URL del checkout la arma Nave y la devuelve en `checkout_url`. Hoy trae un solo parámetro,
  `payment_request_id`, pero eso no está documentado en ninguna de las cuatro páginas vigentes del
  DevPortal, así que no es un contrato del que podamos depender.
- El wizard del link de pago no usa esta plantilla: entrega la URL al usuario para que la abra o la
  mande. Queda fuera.

## Goals / Non-Goals

**Goals:**

- Que el tramo Odoo → Nave quede cubierto por una prueba que corra sin navegador.

**Non-Goals:**

- Cambiar el método del formulario a POST. Nave sirve el checkout como una aplicación de página
  única sobre una ruta GET; mandarle un POST es una suposición distinta y no probada sobre su
  servidor.
- Reconstruir la URL del checkout por nuestra cuenta a partir del `payment_request_id` que ya
  guardamos. Funcionaría hoy y nos dejaría dependiendo de que el host y la ruta no cambien, que es
  justamente lo que `checkout_url` existe para evitar.

## Decisions

### Los parámetros viajan como campos del formulario

La plantilla pasa a recibir dos valores en lugar de uno: la URL del checkout sin su query string, y
los parámetros como pares nombre/valor que se emiten como `<input type="hidden">`.

Así el envío GET reconstruye exactamente la misma URL: el navegador serializa los campos y los pone
como query string, que es la parte del algoritmo que hoy nos borra el parámetro.

*Por qué no dejarlo todo en la `action`*: es lo que está roto. Un formulario GET nunca conserva el
query string de su `action`.

*Por qué no suponer que el parámetro es `payment_request_id`*: el nombre y la cantidad los decide
Nave y no están documentados. Leerlos de la URL que nos devuelve cuesta lo mismo y no se rompe si
mañana agregan uno.

### `api_url` conserva su significado

El valor que la plantilla usa como `action` se sigue llamando `api_url` y sigue siendo una URL a la
que redirigir; lo único que cambia es que ya no lleva query string. Los parámetros van en una clave
nueva.

*Por qué*: `api_url` es el nombre que usa la plantilla y el que aparece en los registros. Renombrarlo
obligaría a tocar más de lo necesario para arreglar un defecto que bloquea cobros.

### La prueba verifica el formulario renderizado, no el payload

El defecto sólo se manifiesta cuando un navegador envía el formulario, así que ninguna prueba de las
que ya existen —todas miran el payload que se le manda a Nave— podía verlo. Lo que sí es verificable
sin navegador es el HTML que se renderiza: que el formulario lleve un campo por cada parámetro de la
URL del checkout.

Esa es la prueba que falta y la que se agrega: dado un `checkout_url` con parámetros, el formulario
renderizado los contiene como campos. Es exactamente la condición que, de haber existido, habría
hecho fallar la versión actual.

## Risks / Trade-offs

- **Un navegador podría reordenar los parámetros al serializarlos** → El orden de un query string no
  es significativo, y Nave los lee por nombre.
- **La prueba sigue sin ejercitar un navegador real** → Verifica la condición que falla, no el salto
  completo. El salto se verifica a mano recorriendo la tienda, que es como se encontró el defecto, y
  queda como paso de la matriz de homologación.

## Migration Plan

Ninguna: es una plantilla y los valores que la alimentan. Las intenciones ya creadas no se tocan; una
que haya quedado sin pagar se sigue pudiendo abrir por su `nave_checkout_url`, que siempre se guardó
completa.
