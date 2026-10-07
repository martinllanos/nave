# Design

## Context

Ver `proposal.md` — Why. Lo que condiciona el enfoque:

- Nave usa dos objetos y cada uno tiene su vocabulario: la **intención** de cobro y el **pago**, que
  es cada intento de pagarla. La intención informa su desenlace (`BLOCKED`, `DISABLED`, …) y el pago
  informa por qué se rechazó la tarjeta (`status.reason_code`). Está documentado y transcripto en
  `docs/nave_codigos_referencia.md`.
- El backend ya trae el pago en cada consulta de estado (`nave_payment`), porque lo necesita para
  imprimir los datos de la tarjeta. El motivo que importa ya llegaba al navegador; se leía el otro.
- Nave publica el catálogo de motivos de rechazo con tarjeta, de rechazo con dinero en cuenta y de
  baja de una intención, cada uno con un mensaje en castellano.
- `BLOCKED` es, según Nave, *"Intención bloqueada por fraude o intentos excedidos"*. En la reprueba
  de C3, una tarjeta sin fondos la dejó en `BLOCKED` con *"payment retries limit reached"*: los
  intentos excedidos.
- Cuando una intención se da de baja, consultarla devuelve `400 payment_request_is_disabled`. No
  está verificado si el cuerpo de esa respuesta trae el motivo de la baja.
- El aviso del POS (`AlertDialog`) respeta los saltos de línea del cuerpo.
- El POS no tiene infraestructura de tests de JavaScript.

## Goals / Non-Goals

**Goals:**

- Que cada aviso diga qué pasó y qué hacer, en los términos de quien está en la caja.
- Que el código que informa Nave quede visible para soporte, sin que se lea como la explicación.
- Que el desenlace de cada cobro quede registrado aunque el cajero cierre el aviso.

**Non-Goals:**

- Cambiar qué cobros se aceptan, cómo se registran o cuándo se corta la espera.
- Guardar los intentos rechazados en un modelo de Odoo. Serviría para consultarlos desde la
  interfaz, pero es una funcionalidad nueva.
- Usar el catálogo en los cobros online, que reciben los mismos códigos. Queda disponible para eso.

## Decisions

### `BLOCKED` se trata como un rechazo

Deja de tener rama propia con mensaje de seguridad y pasa a clasificarse junto a los rechazos.

*Por qué*: el estado de la intención no distingue entre fraude e intentos excedidos, y el caso
frecuente es el segundo. Lo que sí los distingue es el motivo del pago —`fraud_identification`,
`risky_payment` y `fraud_suspected` frente a `no_amount_available`—, y con la decisión siguiente
ese motivo llega al cajero. Un fraude se lee como fraude por lo que dice el pago, no por el nombre
del estado de la intención.

### El motivo sale del pago

El motivo se toma de `status.reason_code` del pago. Sólo si no hay pago se toma el de la
intención, que es donde Nave informa los motivos de baja.

La explicación sale siempre del catálogo, sea cual sea el origen del código. Por eso *"payment
retries limit reached"* nunca llega a la explicación aunque se use como respaldo: no está en el
catálogo. Llega al bloque de soporte y al log.

*Por qué*: es lo que documenta Nave, y lo que mostró la reprueba. El estado de la intención
describe a la intención, no a la tarjeta.

### El cajero lee el mensaje que publica Nave

El catálogo mapea cada código al mensaje que Nave publica para él. El aviso se arma con ese mensaje
y una acción que vale para todos los casos de su categoría: en un rechazo, *"Podés reintentar o
cobrar con otro medio."*; en una baja, *"Generá un cobro nuevo."*. Si el código no está en el
catálogo, el aviso dice sólo qué pasó y qué hacer, sin motivo.

*Por qué con el texto de Nave*: es el que Nave usa con sus propios clientes y el que la soporte de
primer nivel va a reconocer. Escribir uno propio sería adivinar, y adivinar fue lo que produjo el
aviso de seguridad.

*Por qué una acción genérica*: *"Probá con otra tarjeta"* no sirve siempre. Con `cvv2_failure`
alcanza con reintentar con la misma tarjeta.

*Qué queda afuera del catálogo*: los códigos cuyo mensaje usa jerga interna de Nave que no le dice
nada al cajero. Son `disabled_from_saas` (*"deshabilitada desde el SAAS"*), `not_specified` y los
rechazos de dinero en cuenta que hablan de COELSA o de *"Validaciones del Banco Débito"*. De dinero
en cuenta entra sólo `error_of_debit`, que describe la falta de saldo. Los que quedan afuera
producen el aviso genérico, y su código igual aparece en el bloque de soporte.

*Erratas*: se corrigen en los mensajes que ve el cajero (*"parainiciar"*, *"tomarla"*). La
transcripción de `docs/` las conserva, porque es una referencia de lo que publica Nave.

*Alternativa descartada — juzgar el motivo por su forma*: la primera implementación mostraba el
motivo cuando parecía una frase. Nave escribe frases en inglés técnico, así que pasaban el filtro,
y además el motivo leído era el de la intención. El supuesto que justificaba la heurística —que
Nave no publica su catálogo— era falso.

### El catálogo vive en el backend, en `payment_nave`

El backend resuelve el motivo y le agrega a la respuesta el código y el mensaje ya traducido. El
navegador sólo decide la acción y arma el aviso.

*Por qué*: con la resolución en Python se puede testear con los tests que ya existen. Y el catálogo
es vocabulario de Nave, no del POS, así que corresponde a `payment_nave`, donde los cobros online
lo pueden reusar. Sigue el patrón de `payment_mercado_pago/const.py`: un mapeo de código a mensaje
con traducción diferida (`LazyTranslate`).

### El código va rotulado para soporte

Debajo del aviso, separado por una línea en blanco, un bloque *"Para soporte"* con el código tal
como lo informa Nave y los identificadores del pago y de la intención. Se muestra en todos los
desenlaces que no son un cobro exitoso.

*Por qué*: el cajero tiene que poder dictárselo a la soporte de primer nivel. El rótulo dice para
qué está, así que un código ahí no se confunde con la explicación.

### El backend registra el desenlace

Cuando la intención llega a un estado final, el backend registra en el log el estado, el código y
el mensaje resueltos, y los identificadores de la intención y del pago. Con una baja, registra
también el cuerpo de la respuesta 400.

*Por qué*: es el único rastro que queda de un rechazo. Registrar el cuerpo del 400 sirve además
para averiguar si Nave informa ahí el motivo de la baja: si lo informa, el backend ya lo usa; si
no, el log lo muestra.

### El motivo de una baja se usa si llega, sin depender de él

Con el 400 de baja, el backend busca el motivo en el cuerpo (`reason.code` o `disabled_reason`). Si
lo encuentra, el aviso dice, por ejemplo, *"El pago fue cancelado por el usuario dentro de la
terminal."*. Si no, dice *"El cobro ya no está disponible."*, sin atribuir una causa.

*Por qué*: Nave documenta los motivos de baja, pero no está verificado dónde los informa. Así el
módulo aprovecha el motivo si llega y no afirma nada si no llega.

## Risks / Trade-offs

- **Nave cambia o amplía el catálogo** → Un código nuevo produce el aviso genérico y aparece igual
  en el bloque de soporte y en el log. Se agrega al catálogo cuando aparezca.
- **El mensaje de Nave y la acción genérica se superponen** → `denied` dice *"Inténtalo de nuevo."*
  y el aviso agrega *"Podés reintentar o cobrar con otro medio."*. Es redundante, pero no
  contradictorio, y es preferible a reescribir el texto de Nave.
- **El cuerpo del 400 podría traer datos que no queremos en el log** → Es la respuesta de una
  consulta sobre una intención propia, sin datos de tarjeta. Se recorta a 500 caracteres, como los
  demás cuerpos que ya se registran.

## Migration Plan

Ninguna: afecta a los textos que se muestran durante un cobro y a lo que se registra en el log.
