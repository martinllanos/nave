# Datos y material necesarios para publicar los módulos en Odoo Apps

**Para:** Nave Negocios
**De:** Be onlyone
**Fecha:** 2026-10-05 · **Actualizado:** 2026-10-07 (se agrega §6)

Este documento reúne lo que necesitamos de ustedes para publicar en **apps.odoo.com** los dos
módulos de integración con Odoo que les entregamos. Está ordenado por tema y cada pedido indica para qué se usa, de modo que puedan responderlo de una sola vez.

Los módulos son:

| Módulo                     | Qué hace                                                              |
| -------------------------- | --------------------------------------------------------------------- |
| **Proveedor de Pago Nave** | Cobros online: checkout del e-commerce y links de pago sobre facturas |
| **Punto de Venta Nave**    | Cobros presenciales: terminal Nave Point y QR interoperable           |

---

## Lo que nos resta por acordar

Este es el esquema que proponemos. Ninguno de los puntos está acordado todavía: les pedimos que nos
confirmen cada uno o nos digan qué cambiar, porque el resto del documento se apoya en ellos.

- **Publican ustedes**, desde su cuenta de Odoo Apps.
- **Nave figura como autor** de los dos módulos.
- **Distribución gratuita.** Así no aplica el precio mínimo que Odoo exige a las apps pagas ni la
  regla de que el precio allí no supere el de otros canales.
- **Soporte en niveles**: Nave atiende primer y segundo nivel, y Be onlyone toma el tercero. Odoo no
  exige soporte para una app gratuita, así que es un acuerdo entre nosotros, pero define qué canal se
  publica en la ficha.

## Lo que ya cumple los requisitos de Odoo

No hace falta que lo revisen. Lo listamos para que vean que el pedido está acotado a lo que
realmente falta.

| Requisito de Odoo                                      | Estado                     |
| ------------------------------------------------------ | -------------------------- |
| El nombre de la app no supera los 25 caracteres        | ✅ 22 y 19                  |
| La página de descripción está en inglés (obligatorio)  | ✅ en los dos               |
| La página de descripción no usa JavaScript (prohibido) | ✅ en los dos               |
| Cada módulo tiene su icono                             | ✅ en los dos, en PNG y SVG |
| La licencia está declarada                             | ✅ LGPL-3 en los dos        |

---

## 1. Identidad

Estos datos aparecen **públicamente** en la ficha de cada módulo.

| Qué necesitamos                                                    | Para qué                               | Bloquea |
| ------------------------------------------------------------------ | -------------------------------------- | ------- |
| **Nombre legal exacto** de la entidad, tal como quieren que figure | Es el autor que se muestra en la ficha | Sí      |
| **Sitio web oficial**                                              | Es el enlace del autor en la ficha     | Sí      |
| **Correo de contacto**                                             | Figura como vía de contacto del autor  | Sí      |

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

Hoy los dos módulos declaran **LGPL-3**, que es lo habitual para una app gratuita en Odoo. Conviene
que lo confirmen porque tiene una consecuencia concreta:

- **LGPL-3** permite que cualquiera tome el módulo, lo modifique y lo redistribuya, incluso un
  competidor. Es la licencia open source estándar del ecosistema Odoo.
- **OPL-1** es la licencia propietaria de Odoo y no permite redistribución, pero Odoo la reserva para
  las apps de pago.

Siendo gratuita, lo coherente es mantener LGPL-3. Si prefieren restringir la redistribución, habría
que revisar el esquema completo, porque afecta si la app puede seguir siendo gratuita.

## 6. Odoo en el portal de Nave

Publicar en Odoo Apps hace que el módulo se pueda encontrar desde Odoo. Esta sección es para el otro
lado: que un comercio que ya usa Nave sepa que puede cobrar desde Odoo y cómo empezar. Nada de esto
bloquea la publicación.

### Una entrada en Integraciones › Plataformas

Hoy el portal (**Integraciones › Plataformas**) muestra Tucan, Tiendanube, WooCommerce, Tienda
Negocio, Billowshop y Bistrosoft, entre otras, pero no Odoo. Proponemos sumar una entrada
**Odoo ERP** con la misma estructura que, por ejemplo, la de Tucan: una tarjeta con una descripción
breve y una página *"Cobrá con Nave en tu Odoo"* con los beneficios, los medios de pago aceptados y
el paso para vincularse.

| Qué necesitamos | Para qué | Bloquea |
|---|---|---|
| **Que evalúen sumar Odoo** a Integraciones › Plataformas | Es donde un comercio de Nave busca con qué puede cobrar | No |
| **Por qué circuito se vincula un comercio de Odoo** | Hoy lo hicimos por *Tienda online propia*, el circuito que se describe en el punto siguiente. ¿La entrada de Odoo usaría ese mismo circuito, o un botón propio como el *"Activar código de vinculación"* de Tucan? | No |
| **A dónde enlaza "Conocer más"** | Puede ir a la ficha en Odoo Apps, a la guía de alta del punto siguiente o a las dos | No |
| **Textos e icono de la tarjeta**, en castellano | Pueden ser los mismos de §2 y §3, traducidos | No |

> Si les sirve, redactamos nosotros el contenido de la página siguiendo la estructura de las otras
> plataformas, y se lo enviamos para que lo aprueben.

### Una guía de alta para quien integra con Odoo

Lo proponemos a partir de nuestra propia experiencia como primer integrador. La documentación para
desarrolladores es buena, pero el alta tuvo tres obstáculos que no son técnicos:

- **No sabíamos qué pedir para el ambiente de pruebas, ni cómo pedirlo.** La mesa de ayuda responde
  rápido cuando el pedido usa sus términos y es puntual; cuando no, hay repreguntas y el alta se
  demora.
- **Lo mismo pasó con producción**: qué datos solicitar y a quién.
- **Nos costó saber a qué tienda pertenecía cada `pos_id`.** Mientras probábamos creamos varias
  tiendas, y como la plataforma no permite borrarlas, se acumularon tiendas parecidas entre las que
  había que elegir al cargar un `pos_id` en Odoo.

**El circuito, tal como lo entendimos.** Les pedimos que nos confirmen que es el correcto:

1. En **Integraciones › Tienda online propia › Gestionar tiendas** se agrega la tienda, con un
   nombre y una URL. Cada tienda recibe un **código de vinculación**.
2. Para habilitar medios de cobro se escribe a `integraciones@navenegocios.com` con el CUIT, el
   código de vinculación y la lista de medios a habilitar: e-commerce, link de pago, Nave Point o QR.
3. Nave asigna un `pos_id` por cada medio y cada dispositivo.
4. Los `pos_id` se descargan desde **Integraciones › Sistema de gestión › Descargar archivo**, en un
   archivo `POS_ID-<CUIT>.xlsx` con cuatro columnas: *Nombre del local*, *Medio de cobro*,
   *Nombre/N° de serie* y *POS ID*.

**Dónde está la dificultad.** El archivo identifica cada `pos_id` por la columna *Nombre/N° de
serie*:

- **E-commerce:** es el **nombre de la tienda**, no su código de vinculación ni su URL. Si dos
  tiendas tienen nombres parecidos, como nos pasó, el archivo no permite distinguirlas por otro dato.
  En nuestro caso, dos tiendas tienen además la misma URL.
- **Nave Point:** es el **número de serie** de la terminal. Es inequívoco, porque está impreso en el
  equipo.
- **QR:** es un nombre como *"QR 1"* o *"QR 2"*, que se repite entre locales. Para saber cuál es cada
  QR físico hay que mirar también la columna *Nombre del local*.

Proponemos una guía breve, que podemos redactar nosotros y ustedes validan, con:

1. **Qué pedir para el ambiente de pruebas**, con un modelo de correo en los términos de la mesa de
   ayuda.
2. **Qué pedir para producción**, con su modelo de correo.
3. **El circuito de alta** de arriba, con una recomendación de nombres únicos para tiendas y QR.
4. **Cómo leer el archivo de `pos_id`**: qué fila corresponde a cada medio de cobro de Odoo.
5. **Qué hacer con una tienda creada por error.**

Para escribirla necesitamos:

| Qué necesitamos | Para qué | Bloquea |
|---|---|---|
| **La confirmación del circuito** de arriba, o sus correcciones | Que la guía describa el circuito real | No |
| **Los términos que usa la mesa de ayuda** para credenciales, `pos_id`, tienda, sucursal y medio de cobro | Que el modelo de correo se entienda a la primera, sin repreguntas | No |
| **Si el archivo de `pos_id` puede incluir el código de vinculación o la URL** de cada tienda | Distinguir tiendas de nombre parecido sin depender del nombre | No |
| **Si una tienda se puede dar de baja o archivar** | Que una tienda de prueba no quede para siempre entre las reales | No |
| **Cómo se identifica cada QR físico** con su fila del archivo | Que el comercio cargue cada QR en el medio de cobro correcto | No |
| **A quién se dirige un integrador nuevo**, para pruebas y para producción | Que la guía indique el canal correcto desde el primer contacto | No |

---

## Tareas nuestras, para su información

No requieren nada de ustedes; las resolvemos al integrar el material.

- Unificar el tamaño de los iconos: hoy son 512×512 en uno y 1024×1024 en el otro.
- Declarar la imagen de portada en los dos módulos.

---

## Cómo responder

Los pedidos marcados como **bloqueantes** son los que impiden publicar; los demás se pueden resolver
después. Cada bloque se puede responder por separado: no hace falta tener todo junto para empezar a avanzar.

Ante cualquier duda sobre qué es exactamente lo que se pide o para qué se usa, escríbannos y lo
aclaramos.

---

## Alcance de esta entrega

Este documento cubre **únicamente** los dos módulos listados al principio, que son los que les
entregamos y publican ustedes.


