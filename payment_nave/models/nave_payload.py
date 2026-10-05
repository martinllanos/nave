# -*- coding: utf-8 -*-
""" Construcción del detalle de productos que viaja en una intención de pago de Nave.

Vive acá, y no en cada modelo, porque el mismo detalle lo arman tres lugares distintos —el checkout
del e-commerce, el link de pago sobre una factura y el link sobre un pedido— y el defecto que motivó
este módulo estaba escrito cuatro veces: cada rama truncaba la cantidad con `int(qty) or 1` por su
cuenta.
"""

from odoo.tools import formatLang

NAVE_NAME_MAX_LENGTH = 100
NAVE_DESCRIPTION_MAX_LENGTH = 150


def nave_product_entry(env, name, description, quantity, line_total, uom_name=None):
    """ Devuelve una entrada del detalle cuyo importe se corresponde con lo que se cobra.

    `line_total` es lo que esa línea le cuesta al cliente, impuestos incluidos, porque es con eso
    con lo que tiene que cuadrar el detalle: la intención se cobra por un importe con IVA, así que
    un detalle sin IVA suma menos de lo que el cliente paga.

    La cantidad se informa sólo cuando es un entero positivo. Nave no acepta cantidades
    fraccionarias —con `quantity: 0.15` la API responde 502— y tampoco valida que el detalle cuadre
    con el importe, así que truncarla no rompía el cobro, que sale por `amount`, pero hacía que el
    cliente leyera otra cosa en el checkout y en su comprobante: una línea de 0,15 kg a $800 el kilo
    se informaba como 1 × $800 mientras se cobraban $120.

    Por eso, cuando la cantidad no es un entero positivo se informa una unidad por el total de la
    línea, y la cantidad real se antepone al nombre. Va en el nombre y no en la descripción porque
    Nave muestra del detalle sólo `{cantidad}x {nombre}` y el importe: la descripción no se renderiza
    en ninguna de sus pantallas, así que ahí el dato no le llega a nadie. Se conserva igual en la
    descripción por si Nave la muestra en el comprobante o en su panel, que no pudimos inspeccionar.
    """
    if float(quantity).is_integer() and quantity >= 1:
        cantidad_enviada = int(quantity)
        precio_enviado = line_total / cantidad_enviada
    else:
        # Una unidad por el total de la línea: es la única forma de que el detalle cuadre sin
        # mandarle a Nave un decimal que rechaza.
        cantidad_enviada = 1
        precio_enviado = line_total
        cantidad_real = _cantidad_legible(env, quantity, uom_name)
        # El cliente leerá "1x 0,15 kg Granel por kilo". El "1x" lo antepone Nave y no se puede
        # suprimir; es redundante, pero sin la cantidad real leería "1x Granel por kilo" y se
        # quedaría pensando que compró una unidad.
        name = f"{cantidad_real} {name}" if name else cantidad_real
        description = f"{cantidad_real} — {description}" if description else cantidad_real

    return {
        'name': (name or 'Ítem')[:NAVE_NAME_MAX_LENGTH],
        'description': (description or '')[:NAVE_DESCRIPTION_MAX_LENGTH],
        'quantity': cantidad_enviada,
        'unit_price': {
            'currency': 'ARS',
            'value': f"{precio_enviado:.2f}",
        },
    }


def _cantidad_legible(env, quantity, uom_name):
    """ Devuelve la cantidad tal como la lee el cliente, por ejemplo `0,15 kg`. """
    cantidad = formatLang(env, quantity)
    return f"{cantidad} {uom_name}" if uom_name else cantidad
