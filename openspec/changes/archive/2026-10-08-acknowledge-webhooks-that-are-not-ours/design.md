# Design

## Context

El webhook (`payment_nave/controllers/main.py`) valida el JSON y los campos obligatorios (400 si
faltan) y delega en `payment.transaction._handle_notification_data`. Cualquier excepción que salga de
ahí termina en un 500.

Dentro de ese procesamiento sólo hay dos caminos que fallan a propósito:

- **`_get_tx_from_notification_data`** lanza `ValidationError` si no encuentra la transacción. Los
  otros dos `ValidationError` del código, por `external_payment_id` o `payment_id` ausentes, no se
  alcanzan desde el webhook, porque el controlador responde 400 antes.
- **`_process_notification_data`** atrapa el `RequestException` de la consulta del pago, llama a
  `_set_error` y retorna normalmente. El controlador responde 200.

La conciliación periódica (`_cron_nave_poll_pending_transactions`) pasa por el mismo
`_process_notification_data`. Envuelve cada transacción en un savepoint y registra cualquier
excepción sin cortar el lote, y sólo revisa transacciones en `draft` o `pending`.

En Odoo, si el controlador atrapa la excepción y devuelve una respuesta, el cursor de la petición se
confirma igual. Lo que se haya escrito antes de la falla queda grabado.

## Goals / Non-Goals

**Goals:**

- El código HTTP le dice a Nave lo que corresponde: 200 si no tiene sentido reintentar y 500 si sí.
- Una falla de comunicación con Nave nunca cambia el estado de una transacción.

**Non-Goals:**

- Reconocer los avisos del punto de venta como tales. El POS no los usa.
- Firmar o autenticar el webhook (B5, E2c): sigue protegido por la verificación contra la API.
- El `_set_error` por un estado desconocido de Nave: es un desenlace informado por Nave, no una falla
  de comunicación.
- Los casos D5c y D6c (duplicados y avisos fuera de orden).

## Decisions

### Un `ValidationError` se acusa con 200

El controlador atrapa `ValidationError` aparte, la registra como información con la referencia y el
motivo, y responde 200. Las demás excepciones siguen respondiendo 500.

Es la convención del core (`payment_stripe/controllers/main.py:160`). Desde el webhook, hoy, la única
`ValidationError` posible es la de la transacción que no existe, y para ese caso ningún reintento
sirve.

Alternativas descartadas:

- **Reconocer la referencia del POS** (buscar un `pos.payment` con ese `uuid`) para registrarla
  distinto. Cuando llega la aprobación, la orden todavía no se sincronizó con el servidor, así que la
  búsqueda fallaría justo en el caso que interesa.
- **Una excepción propia para "transacción inexistente".** Distinguiría ese caso de otros
  `ValidationError` futuros, pero se aparta de cómo lo resuelven los demás proveedores de Odoo, y hoy
  no hay otro caso que distinguir.

### Una consulta fallida se propaga en lugar de cerrar la transacción

`_process_notification_data` deja de atrapar el `RequestException`. Registra el error con el pago y la
referencia, y vuelve a lanzar la excepción sin tocar la transacción. Con eso:

- desde el webhook, el controlador responde 500 y Nave reintenta;
- desde la conciliación, el savepoint descarta lo hecho, el lote sigue, y la transacción queda
  pendiente para la corrida siguiente.

Se incluyen los 4xx de la consulta, por ejemplo un `payment_id` que Nave no reconoce. Separarlos
obligaría a decidir qué 4xx son definitivos sin documentación de Nave que lo diga. Reintentar un aviso
falso cuesta, a lo sumo, cinco reintentos de Nave.

Alternativa descartada: **dejar la transacción en `pending`** con un mensaje y responder 500. Escribe
un estado que ningún desenlace de Nave produjo, y de todos modos el savepoint lo descartaría.

### El procesamiento del aviso va dentro de un savepoint

El controlador envuelve `_handle_notification_data` en `request.env.cr.savepoint()`. Si el
procesamiento lanza una excepción, se descarta todo lo que escribió antes de responder, sea 200 o 500.

Así se cumple el requisito de no dejar un aviso aplicado a medias, sin depender de en qué punto
falle. Hoy la consulta ocurre antes de cualquier escritura, pero el orden podría cambiar.

## Risks / Trade-offs

- **[Riesgo] Un aviso de una transacción online legítima que no se encuentre se acusa y se pierde.**
  → La transacción se crea antes de mandar al cliente al checkout, así que existe antes de cualquier
  pago. Y si igual pasara, la conciliación periódica la revisa a los 30 minutos, porque sigue
  pendiente.
- **[Trade-off] El aviso de cada venta presencial deja una línea de información en el log.** → Es
  una línea por venta en lugar de un error por cada reintento. Lleva la referencia, así que se puede
  cruzar con el log del POS.
- **[Riesgo] Una caída larga de la API de Nave agota los cinco reintentos.** → La transacción queda
  pendiente, no en error, y la recupera la conciliación periódica.

## Migration Plan

1. Subir `payment_nave` a `18.0.1.12.2`.
2. Desplegar con el procedimiento de siempre: push, build sin caché, `service update --force`,
   `-u payment_nave`. Después, verificar en el contenedor la versión y el hash del controlador.
3. Verificar en el servidor:
   - un `curl` al webhook con una referencia inventada responde 200 (D4c);
   - el aviso del próximo cobro presencial responde 200, y Nave no lo reintenta.
4. Para volver atrás, desplegar la imagen anterior. No hay cambios de datos.
