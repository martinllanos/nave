# Datos y material necesarios para publicar los módulos en Odoo Apps

**Para:** Nave Negocios
**De:** Be onlyone
**Fecha:** 2026-10-06

Este documento reúne lo que necesitamos de ustedes para publicar los tres módulos de integración con
Odoo en **apps.odoo.com**. Está ordenado por tema y cada pedido indica para qué se usa, de modo que
puedan responderlo de una sola vez.

Los módulos son:

| Módulo | Qué hace |
|---|---|
| **Proveedor de Pago Nave** | Cobros online: checkout del e-commerce y links de pago sobre facturas |
| **Punto de Venta Nave** | Cobros presenciales: terminal Nave Point y QR interoperable |
| **Simulador Cuotas Nave** | Cálculo de recargos financieros y precios finales por cuotas |

---

## Lo que ya está acordado

No hace falta que respondan nada de esto; va listado para que quede constancia del encuadre.

- **Publican ustedes**, desde su cuenta de Odoo Apps.
- **Nave figura como autor** de los tres módulos.
- **Distribución gratuita.** Por lo tanto no aplica el precio mínimo que Odoo exige a las apps pagas
  ni la regla de que el precio allí no supere el de otros canales.
- **Soporte en niveles**: Nave atiende primer y segundo nivel; Be onlyone toma el tercero. Odoo no
  exige soporte para una app gratuita, así que esto es un acuerdo entre nosotros, pero define qué
  canal se publica en la ficha.

## Lo que ya cumple los requisitos de Odoo

Tampoco hace falta que lo revisen. Lo listamos para que vean que el pedido está acotado a lo que
realmente falta.

| Requisito de Odoo | Estado |
|---|---|
| El nombre de la app no supera los 25 caracteres | ✅ 22, 19 y 21 |
| La página de descripción está en inglés (obligatorio) | ✅ en los tres |
| La página de descripción no usa JavaScript (prohibido) | ✅ en los tres |
| Cada módulo tiene su icono | ✅ en los tres |
| La licencia está declarada | ✅ LGPL-3 en los tres |

---

## 1. Identidad

Estos datos aparecen **públicamente** en la ficha de cada módulo.

| Qué necesitamos | Para qué | Bloquea |
|---|---|---|
| **Nombre legal exacto** de la entidad, tal como quieren que figure | Es el autor que se muestra en la ficha | Sí |
| **Sitio web oficial** | Es el enlace del autor en la ficha | Sí |
| **Correo de contacto** | Figura como vía de contacto del autor | Sí |

> Hoy los módulos declaran a *Be onlyone* como autor, con nuestro sitio. Al publicar bajo su cuenta
> eso pasa a ser de ustedes, y por eso necesitamos el nombre tal cual quieran verlo escrito.

## 2. Marca

| Qué necesitamos | Para qué | Bloquea |
|---|---|---|
| **Icono oficial** en PNG, cuadrado, preferentemente 512×512 px o más, con fondo transparente | Es el icono de cada módulo en Odoo | Sí |
| **Logo oficial** en alta resolución, PNG o SVG | Se usa dentro de la página de descripción | Sí |
| **Guía de uso de marca**, si tienen una | Para respetar colores, márgenes y variantes del logo | No |

> Los iconos que hay hoy los generamos nosotros con un script, y del logo que está en el repositorio
> no tenemos constancia de que sea el oficial. Como la ficha va a ser pública y lleva su marca,
> preferimos reemplazarlos por el material suyo antes de publicar.

## 3. Material comercial

Todo este material es **público** y en **inglés**, que es un requisito de Odoo para la página de
descripción.

| Qué necesitamos | Para qué | Bloquea |
|---|---|---|
| **Imagen de portada** de cada módulo | Es la miniatura que se ve en el listado de Odoo Apps | Sí |
| **Capturas de pantalla** que muestren el módulo funcionando | Odoo las pide para la ficha | Sí |
| **Texto descriptivo aprobado** por ustedes, en inglés | Es el cuerpo de la ficha | Sí |
| **Resumen de una línea** por módulo, en inglés | Es el subtítulo que acompaña al nombre | Sí |

> Si prefieren, podemos redactar nosotros los textos y las capturas y enviárselos para aprobación.
> Avisen cuál de las dos formas les resulta más cómoda.

## 4. Soporte

| Qué necesitamos | Para qué | Bloquea |
|---|---|---|
| **Correo o canal de soporte de primer nivel** | Figura públicamente en la ficha; es a donde escribe un comercio con un problema | Sí |
| **Vía de escalamiento a tercer nivel** | Cómo nos llegan a nosotros los casos que requieren intervención sobre el código | No |
| **Horario de atención**, si quieren publicarlo | Para fijar expectativas de quien escribe | No |

> Al ser gratuitas, Odoo no obliga a dar soporte. Lo pedimos igual porque el canal que indiquen va a
> quedar publicado, y conviene que sea uno que puedan atender.

## 5. Publicación

| Qué necesitamos | Para qué | Bloquea |
|---|---|---|
| **Quién administra la cuenta** de Odoo Apps | Para coordinar con la persona correcta | Sí |
| **Cómo se suben las versiones nuevas** | El desarrollo es nuestro y la cuenta es suya: hay que acordar el circuito | Sí |
| **Confirmación de la licencia** | Ver el punto siguiente | Sí |

### Sobre la licencia

Hoy los tres módulos declaran **LGPL-3**, que es lo habitual para una app gratuita en Odoo. Conviene
que lo confirmen porque tiene una consecuencia concreta:

- **LGPL-3** permite que cualquiera tome el módulo, lo modifique y lo redistribuya, incluso un
  competidor. Es la licencia open source estándar del ecosistema Odoo.
- **OPL-1** es la licencia propietaria de Odoo y no permite redistribución, pero Odoo la reserva para
  las apps de pago.

Siendo gratuita, lo coherente es mantener LGPL-3. Si prefieren restringir la redistribución, habría
que revisar el esquema completo, porque afecta si la app puede seguir siendo gratuita.

---

## Estado actual de los módulos

Esta tabla muestra qué declara hoy cada módulo y qué pasaría a declarar con sus respuestas. Sirve
para ver el efecto concreto de cada dato que pedimos.

| Dato | Proveedor de Pago Nave | Punto de Venta Nave | Simulador Cuotas Nave |
|---|---|---|---|
| Autor | `Be onlyone` → **Nave** | `Be onlyone` → **Nave** | `Martin` → **Nave** |
| Sitio web | `onlyone.odoo.com` → **el de Nave** | `onlyone.odoo.com` → **el de Nave** | *no declarado* → **el de Nave** |
| Soporte | *no declarado* → **canal de Nave** | *no declarado* → **canal de Nave** | *no declarado* → **canal de Nave** |
| Licencia | `LGPL-3` (a confirmar) | `LGPL-3` (a confirmar) | `LGPL-3` (a confirmar) |
| Imagen de portada | *sólo el icono* → **portada propia** | *no declarada* → **portada propia** | *no declarada* → **portada propia** |

## Tareas nuestras, para su información

No requieren nada de ustedes; las resolvemos al integrar el material.

- Unificar el tamaño de los iconos: hoy son 512×512 y 1024×1024 según el módulo.
- Corregir el icono del Simulador, que es un archivo JPEG con extensión `.png`. Odoo espera un PNG, y
  el formato actual además no admite fondo transparente.
- Unificar el autor del Simulador, que quedó distinto al de los otros dos.
- Declarar la imagen de portada en los tres módulos.

---

## Cómo responder

Los pedidos marcados como **bloqueantes** son los que impiden publicar; los demás se pueden resolver
después. Cada bloque se puede responder por separado: no hace falta tener todo junto para empezar a
avanzar.

Ante cualquier duda sobre qué es exactamente lo que se pide o para qué se usa, escríbannos y lo
aclaramos.
