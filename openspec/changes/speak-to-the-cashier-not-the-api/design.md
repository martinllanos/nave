# Design

## Context

Ver `proposal.md` — Why. Lo que condiciona el enfoque:

- El frontend clasifica el estado que informa Nave en seis categorías y cada una tiene su mensaje. El
  motivo sale de `status.reason_name || status.reason_code` y se interpola tal cual.
- Nave usa `BLOCKED` para rechazos corrientes. Verificado dos veces con tarjetas distintas sin fondos.
- Cuando una intención se da de baja, la API devuelve un error y el backend lo traduce a un estado
  sintético para que el POS cierre el cobro. Esa traducción es correcta; lo que sobra es que copie el
  nombre del error como motivo.
- Del checkout web sabemos que Nave sí manda motivos legibles en otros contextos: `no_amount_available`
  e `invalid_installment_plan` aparecieron en los rechazos online. Son códigos, no frases.

## Goals / Non-Goals

**Goals:**

- Que cada aviso diga qué pasó y qué hacer, en los términos de quien está en la caja.
- Que un código técnico no pueda llegar a la pantalla aunque aparezca uno nuevo que no conozcamos.

**Non-Goals:**

- Cambiar qué cobros se aceptan, cómo se registran o cuándo se corta la espera.
- Traducir el catálogo completo de códigos de Nave. No lo tenemos y adivinarlo produciría mensajes
  tan equivocados como el actual.

## Decisions

### `BLOCKED` se trata como un rechazo

Deja de tener rama propia con mensaje de seguridad y pasa a clasificarse junto a los rechazos.

*Por qué*: es lo que es. Dos tarjetas sin fondos devolvieron `BLOCKED`, y la terminal mostró en ambos
casos el texto de saldo insuficiente. Mantener una rama de fraude basada en el nombre del estado,
cuando la evidencia dice otra cosa, es preferir la etimología a los hechos.

*Qué se pierde*: si Nave efectivamente bloqueara una operación por fraude, el cajero lo leería como
un rechazo común. Es el intercambio correcto: un rechazo mal rotulado como fraude ocurre todos los
días y manda a llamar al proveedor sin motivo; un fraude rotulado como rechazo lleva a probar otra
tarjeta, que también es lo que corresponde hacer.

### El motivo se muestra sólo si es legible para una persona

Un motivo se considera legible cuando no parece un identificador: cuando lleva espacios o acentos,
propio de una frase, y no el `snake_case` de un código.

*Por qué por forma y no por lista*: una lista blanca de códigos conocidos cubre los que vimos y deja
pasar el próximo. Nave no publica su catálogo, así que cualquier lista nuestra está incompleta por
construcción. Juzgar la forma protege también de lo que no conocemos.

*Qué pasa con los códigos que sí conocemos*: `no_amount_available` describe exactamente lo que ya
dice el mensaje de un rechazo —la tarjeta no pudo pagar—, así que no agrega nada traducirlo. Si más
adelante aparece uno que aporte algo distinto, se agrega su traducción entonces, con el caso real
delante.

### El backend deja de inventar un motivo

Al traducir el error de una intención dada de baja, el backend informa el estado pero no un
`reason_code`.

*Por qué*: ese valor nunca fue un motivo de negocio, era el nombre de un error HTTP. Sacarlo de ahí
es más honesto que filtrarlo después en la pantalla, y hace que el frontend use el mensaje que ya
tenía escrito para cuando no hay motivo.

### El mensaje de baja no afirma la causa

Pasa a decir que el cobro ya no está disponible y que puede generarse uno nuevo, sin atribuirlo a la
terminal.

*Por qué*: hoy dice "dado de baja en la terminal", y puede haber sido un vencimiento o un fallo de
notificación de Nave. Afirmar la causa equivocada manda al cajero a buscar el problema donde no está.

## Risks / Trade-offs

- **Un fraude real se leería como un rechazo** → Discutido arriba: la acción que el cajero debe tomar
  es la misma, y el caso frecuente es el que hoy está mal.
- **La heurística de legibilidad podría ocultar un motivo útil mal formateado** → El aviso sigue
  diciendo qué pasó y qué hacer; lo que se pierde es un detalle, no la acción. Y el motivo completo
  queda en la consola del navegador para quien necesite diagnosticar.

## Migration Plan

Ninguna: afecta sólo a los textos que se muestran durante un cobro.
