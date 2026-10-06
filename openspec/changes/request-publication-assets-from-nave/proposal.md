# Proposal

## Why

`payment_nave` y `pos_nave` se van a publicar en Odoo Apps Store **bajo la cuenta de Nave Negocios y
con ellos como autor**, pero los manifiestos siguen declarando `'author': 'Be onlyone'` y un sitio
web que no es el de ellos. `sale_nave_simulator` queda fuera: es un producto propio de Be onlyone que
complementa a los otros dos, y lo publicamos nosotros. Hay material que sólo Nave puede aportar: su logo oficial, sus textos y el canal de
soporte que quieran publicar.

Nada de eso se puede resolver del lado del desarrollo, y sin eso la publicación no avanza. Pedirlo
de a pedazos, a medida que aparece, alarga el ida y vuelta: conviene un único documento que lo liste
completo, con lo que ya está resuelto separado de lo que falta, para que puedan responderlo de una
sola vez.

Publica Nave desde su propia cuenta, así que el uso de su marca en la ficha lo resuelven ellos. Lo
que sigue haciendo falta es el material en sí: hoy el repositorio lleva un logo del que no consta
origen y unos iconos generados con un script propio, y para una ficha pública conviene el material
oficial.

## What Changes

- Se agrega un **documento de requerimientos** dirigido a Nave, con los datos, el material y las
  decisiones que hacen falta para publicar, agrupados por tema y con el motivo de cada pedido.
- El documento incluye un **inventario del estado actual** de los dos manifiestos entregados, de modo
  que se vea qué queda como está y qué cambia con cada respuesta.
- Se deja constancia de lo ya verificado contra las reglas de Odoo, para no pedir lo que ya cumple.

No se modifica ningún módulo. Los manifiestos se actualizan cuando lleguen las respuestas, en un
cambio aparte.

## Capabilities

### New Capabilities

<!-- Ninguna: es documentación y no cambia el comportamiento de ningún módulo.
     El cambio declara skip_specs: true. -->

### Modified Capabilities

<!-- Ninguna. -->

## Impact

- Un documento nuevo bajo `docs/`.
- Sin impacto en `payment_nave` ni `pos_nave`: no se toca código, manifiestos ni assets.
- `sale_nave_simulator` queda fuera del alcance: no se entrega a Nave.

### Lo que ya cumple (verificado el 2026-10-06)

| Requisito de Odoo | Estado |
|---|---|
| Nombre de la app ≤ 25 caracteres | ✅ 22 y 19 |
| Página de descripción en inglés | ✅ las dos |
| Sin JavaScript en la página de descripción | ✅ las dos |
| Icono presente | ✅ `icon.png` y `icon.svg` en los dos |
| Licencia declarada | ✅ LGPL-3 en los dos |

### Lo que falta y sólo Nave puede dar

1. **Identidad** — nombre legal exacto para `author`, sitio oficial para `website`, correo de
   soporte.
2. **Marca** — logo e icono oficiales en calidad de publicación. Los iconos actuales se generaron
   con `payment_nave/static/img/generate_icons.py` y del `logo-nave.jpg` del repositorio no consta
   origen, así que conviene reemplazarlos por los suyos antes de que la ficha sea pública.
3. **Material comercial** — imagen de portada, capturas y textos aprobados, en inglés.
4. **Soporte** — el correo o canal de primer nivel que figurará en la ficha pública, y cómo se
   escala a Be onlyone lo que llegue a tercer nivel.
5. **Publicación** — quién sube cada versión y cómo se coordinan las actualizaciones, dado que la
   cuenta es de ellos y el desarrollo es nuestro.

### Lo que ya está decidido

- **Distribución gratuita.** No aplica el precio mínimo de Odoo ni la regla de paridad entre canales.
- **Soporte en niveles**: Nave atiende primer y segundo nivel, Be onlyone toma el tercero. Odoo no
  exige soporte para una app gratuita, así que esto es un compromiso propio, pero define qué canal
  se publica en la ficha.
- **Publica Nave** desde su cuenta de Apps Store.

Queda por confirmar un punto que depende de lo anterior: siendo gratuita, lo coherente es mantener
**LGPL-3**, pero conviene que Nave lo confirme porque determina si terceros pueden redistribuir y
modificar el módulo.
