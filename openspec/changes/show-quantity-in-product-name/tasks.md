# Tasks

## 1. La cantidad real llega al cliente

- [x] 1.1 Anteponer la cantidad real al nombre del producto cuando la cantidad informada no sea la
      real, conservándola también en la descripción, y dejando el prefijo primero para que sobreviva
      al recorte de 100 caracteres. Verificar: una línea de 0,15 kg produce un nombre que empieza con
      `0,15 kg` y una entrada cuyo importe sigue siendo el de la línea.
- [x] 1.2 Ajustar los tests del detalle para que comprueben el nombre y no la descripción, que es
      donde el cliente lee la cantidad. Verificar: los tests fallan si la cantidad se quita del
      nombre, y pasan con el cambio.
- [x] 1.3 Comprobar con un nombre largo que el recorte no se come la cantidad. Verificar: con un
      producto de nombre extenso, el nombre informado sigue empezando por la cantidad y no supera los
      100 caracteres.

## 2. Una corrida roja significa que el código está mal

- [x] 2.1 Hacer que el test del cron juzgue sólo la transacción que él mismo creó, en lugar de
      afirmar que el cron no consultó a nadie. Verificar: el test pasa aunque la base tenga otra
      transacción Nave pendiente y vieja, y sigue fallando si el cron consulta la transacción
      reciente del test.
- [x] 2.2 Comprobar el escenario que lo rompió: con una transacción Nave pendiente de más de 30
      minutos en la base, la suite completa queda en verde. Verificar: se crea esa transacción, se
      corre la suite y no falla ningún test.

## 3. Cierre

- [x] 3.1 Subir la versión del módulo. Verificar: el manifiesto declara la versión nueva.
- [x] 3.2 Correr la suite de `payment_nave` y `pos_nave`, más flake8 y bandit según `.agent/rules.md`
      §6. Verificar: 0 fallos, 0 errores de lint y 0 hallazgos de severidad media o superior.
- [x] 3.3 Desplegar y abrir en el navegador el checkout de una compra con cantidad fraccionaria.
      Verificar: la pantalla de Nave muestra la cantidad real en la línea, y queda registrado en el
      plan de homologación con la captura.
