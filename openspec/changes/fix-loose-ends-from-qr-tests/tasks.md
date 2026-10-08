# Tasks

## 1. Lo que ve el cajero

- [ ] 1.1 Agregar a `pos_nave/static/src/app/` una plantilla que extienda
      `point_of_sale.PaymentScreenPaymentLines` y, en el estado `waitingCard`, muestre *"Esperando el
      escaneo del QR"* cuando el método es `nave_qr`, y el texto del core en los demás casos.
      Verificar: con el POS cargado, la plantilla compila sin errores en la consola. La prueba en el POS
      (3.3) muestra el texto nuevo con *Nave QR* y el de siempre con *Nave Point*.

## 2. Token, logs y comentario

- [ ] 2.1 Bajar el margen de `_nave_get_access_token` a 30 s, con la explicación de por qué en el
      código. Verificar: un test comprueba que un token al que le quedan 2 minutos se reusa sin
      pedir otro, y otro que uno al que le quedan 10 s se renueva.
- [ ] 2.2 Nombrar en el log del envío el destino según el tipo, terminal o QR, y corregir el
      comentario de `close()`. Verificar: un test comprueba el texto del log para `static_qr`. El
      comentario ya no dice que `close()` se llama al salir de la pantalla.
- [ ] 2.3 Registrar el JSON roto del webhook como advertencia. Verificar: una prueba HTTP nueva con JSON roto
      responde 400 y no deja registros de nivel error.

## 3. Cierre

- [ ] 3.1 Subir `payment_nave` a `18.0.1.12.3` y `pos_nave` a `18.0.1.11.2`. Verificar: los
      manifiestos declaran las versiones nuevas.
- [ ] 3.2 Correr las suites de `payment_nave` y `pos_nave`, más flake8 y bandit según
      `.agent/rules.md` §6. Verificar: 0 fallos, 0 errores de lint y 0 hallazgos de severidad media o
      superior.
- [ ] 3.3 Desplegar, verificar versiones y hashes en el contenedor, y probar en el POS:
      - con *Nave QR*, la línea dice *"Esperando el escaneo del QR"*;
      - con *Nave Point*, sigue diciendo *"Esperando la tarjeta"*.
      Se cancelan los dos cobros, sin pagar. Registrar el resultado en el plan (§3.40).
