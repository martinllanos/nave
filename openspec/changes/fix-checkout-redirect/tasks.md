# Tasks

## 1. La redirección conserva los parámetros de la intención

- [x] 1.1 Separar la URL del checkout de sus parámetros al armar los valores de renderizado, de modo
      que la plantilla reciba la URL sin query string y los parámetros como pares nombre/valor
      leídos de esa misma URL. Verificar: con una URL con parámetros devuelve ambas partes, y con una
      URL sin parámetros devuelve la lista vacía.
- [x] 1.2 Emitir en la plantilla `redirect_form` un `<input type="hidden">` por cada parámetro.
      Verificar: el formulario renderizado para una intención real contiene un campo
      `payment_request_id` con el identificador de esa intención.
- [x] 1.3 Cubrir con un test el formulario renderizado, que es lo que falla: dado un `checkout_url`
      con parámetros, el HTML lleva un campo por cada uno y la `action` ya no depende del query
      string. Verificar: el test falla contra la plantilla anterior y pasa con la nueva.

## 2. Cierre

- [x] 2.1 Subir la versión del módulo. Verificar: el manifiesto declara la versión nueva.
- [x] 2.2 Correr la suite de `payment_nave` y `pos_nave`, más flake8 y bandit según `.agent/rules.md`
      §6. Verificar: 0 fallos, 0 errores de lint y 0 hallazgos de severidad media o superior.
- [x] 2.3 Desplegar y recorrer la tienda de homologación hasta la pantalla de pago de Nave.
      Verificar: el checkout muestra el importe y el detalle de la compra en lugar de una pantalla en
      blanco, y queda registrado como caso de la matriz para que el recorrido completo no vuelva a
      quedar sin probar.
