# Design

## Context

Ver `proposal.md` — Why.

Odoo ya tiene un lugar para la marca: `payment.method` modela las marcas como sub-métodos de `card`
(`primary_payment_method_id` / `brand_ids`), y `payment.transaction.payment_method_id` apunta al que
se usó. El provider de Mercado Pago del core resuelve la marca a partir de la respuesta y la escribe
ahí. El módulo ya vincula `card` y `naranja` al proveedor Nave.

Para el resto —últimos cuatro, cupón, lote, autorización, plan de cuotas— no hay campos en
`payment.transaction`. Los que existen en `pos.payment` (`card_brand`, `card_no`,
`payment_method_authcode`, `ticket`) pertenecen al Punto de Venta y no a este modelo.

## Goals / Non-Goals

**Goals:**

- Que la marca aparezca donde Odoo ya la muestra, sin un lugar paralelo.
- Que los datos sobrevivan al cobro: hoy sólo existen en el log, mientras el log dure.

**Non-Goals:**

- Alterar el monto de la transacción. Lo que factura el comercio son los $1.150 de la venta; el
  costo financiero lo paga el cliente al emisor y no es un ingreso del comercio.
- Unificar el registro con `pos_nave`. Ahí los datos van a `pos.payment`, que tiene sus propios
  campos y su propio ticket. Son dos modelos distintos de Odoo, no una duplicación nuestra.
- Tokenizar ni guardar nada que permita volver a cobrar. Los últimos cuatro dígitos y el `bin` que
  Nave devuelve identifican la operación, no habilitan a repetirla.

## Decisions

### La marca va al `payment_method_id`, el resto a campos propios

La marca se resuelve contra los `payment.method` de marca y se escribe en `payment_method_id`. Los
demás datos van a campos nuevos del módulo en `payment.transaction`.

**Por qué**: es el reparto que ya hace el core. La marca tiene un lugar canónico y usarlo hace que
aparezca en las vistas y los informes estándar sin trabajo extra. Lo demás no tiene lugar canónico,
y meterlo a la fuerza en campos que significan otra cosa sería peor que crear los propios.

**Alternativa descartada**: guardar el payload crudo en un campo de texto. Sobrevive a cualquier
cambio de la API y no sirve para nada más: no se puede filtrar, ni mostrar en una vista, ni leer sin
interpretarlo a mano. El valor de estos datos está justamente en poder consultarlos.

### Campos separados para la financiación, no un texto armado

Cuotas, interés, tasa, costo financiero e importe pagado van cada uno a su campo.

**Por qué**: el importe que pagó el cliente es un número que alguien va a querer comparar con el
monto de la venta —son $1.263,10 contra $1.150—, y la cantidad de cuotas es un dato por el que se
filtra. Un texto armado obliga a desarmarlo para cualquiera de las dos cosas.

### El resumen se arma según el medio, no con un molde fijo

El mensaje del chatter se compone con lo que corresponde al medio del cobro.

**Por qué**: el molde actual nombra siempre la billetera y produce *"Billetera utilizada: N/A"* en
todo pago con tarjeta. Un mensaje que afirma algo que no aplica es peor que uno que lo omite: quien
lo lee no sabe si el dato falta o si el pago fue raro.

### Los datos se extraen donde ya se verifica el pago

La extracción ocurre en el mismo lugar donde hoy se consulta el estado real del pago, sobre esa
misma respuesta.

**Por qué**: esa consulta ya se hace y ya trae todo. Cualquier otro momento implicaría una llamada
más a Nave para datos que ya tuvimos en la mano.

## Risks / Trade-offs

- **La marca informada puede no tener un `payment.method` equivalente**: Nave puede devolver una
  marca que el proveedor no tenga vinculada. → En ese caso se conserva el texto en el campo propio y
  se deja el `payment_method_id` como estaba; perder el dato sería peor que no poder clasificarlo.
- **El plan de cuotas lo elige el pagador, no la tarjeta**: en el caso A4, una tarjeta rotulada "6
  cuotas" terminó en un plan de 3. → Es una razón más para registrar lo que efectivamente ocurrió en
  lugar de deducirlo del medio.

## Migration Plan

Los campos nacen vacíos y se completan con los cobros nuevos. Las transacciones ya cerradas no se
reprocesan: el dato existe del lado de Nave y se puede consultar por `nave_payment_id` si alguna vez
hace falta reconstruirlo.
