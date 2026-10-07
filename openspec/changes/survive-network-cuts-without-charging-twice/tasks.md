# Tasks

## 1. Ninguna consulta espera sin límite

- [x] 1.1 Poner un tope de tiempo a la consulta de estado (10 s) y a la creación de la intención
      (45 s); una llamada que no responde a tiempo cuenta como falta de respuesta. Verificar: en el
      arnés de Node, una consulta colgada deja pasar la vuelta siguiente del polling y el plazo se
      respeta.
- [x] 1.2 Si la creación de la intención no responde a tiempo, avisar que el cobro pudo llegar a la
      terminal y que se verifique antes de reintentar. Verificar: en el arnés, la línea queda para
      reintentar con ese aviso.

## 2. Un corte no termina el cobro

- [x] 2.1 Quitar el corte por fallos de transporte: el cobro sólo termina por un desenlace de Nave,
      por el plazo o por el cajero. Verificar: en el arnés, con consultas que fallan al instante
      durante más de 9 s, el cobro sigue en curso y, si después llega la aprobación, la línea queda
      cobrada.
- [x] 2.2 Mostrar una notificación persistente al tercer fallo seguido y cerrarla con la primera
      respuesta. Verificar: en el arnés, se muestra una sola vez por corte y se cierra al volver la
      conexión.
- [x] 2.3 Reescribir el aviso de tiempo agotado para que recomiende reintentar. Verificar: el aviso
      no manda a revisar la terminal como único camino.

## 3. Reintentar no cobra dos veces

- [x] 3.1 Antes de crear una intención en una línea con `transaction_id`, consultarla y resolver
      según la tabla de `design.md`: aprobada → cobrada; en curso o desconocida → retomar la espera;
      rechazada, dada de baja o vencida → intención nueva; sin respuesta → aviso, sin intención nueva.
      Las devoluciones quedan fuera. Verificar: el arnés cubre los cuatro casos y en ninguno se crea
      un cobro nuevo salvo el tercero.
- [x] 3.2 Revisar que *Forzar terminación* y la cancelación sigan funcionando con estos cambios.
      Verificar: los escenarios del arnés de `confirm-force-done-with-nave` siguen pasando.

## 4. Cierre

- [x] 4.1 Subir la versión de `pos_nave`. Verificar: el manifiesto declara la versión nueva.
- [x] 4.2 Correr las suites de `payment_nave` y `pos_nave`, más flake8 y bandit según
      `.agent/rules.md` §6. Verificar: 0 fallos, 0 errores de lint y 0 hallazgos de severidad media o
      superior.
- [x] 4.3 Desplegar y, antes de tocar nada, confirmar desde la consola del navegador que la línea del
      pedido 104 conserva el identificador de la intención. Después reintentarlo. Verificar: la línea
      queda cobrada con los datos de la tarjeta de los $150 aprobados y no aparece un cobro nuevo en
      la terminal ni en el log.
- [x] 4.4 Repetir con la terminal la corrida 3 de C8 (navegador sin conexión, pago real) y la corrida
      2 (cable desenchufado, sin pagar). Verificar: en la 3 el punto de venta registra el pago al
      volver la conexión; en la 2 avisa la falta de conexión y termina al vencer el plazo, sin quedar
      colgado. Registrar los resultados en el plan de homologación como reprueba de C8.
