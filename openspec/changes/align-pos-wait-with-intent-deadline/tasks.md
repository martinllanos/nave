# Tasks

## 1. El plazo se declara una vez y viaja al punto de venta

- [x] 1.1 Dejar el plazo de la intención presencial en una constante del módulo y usarla al construir
      el pedido a Nave, en lugar del número suelto que hay hoy. Verificar: el payload sigue llevando
      el mismo plazo que antes y la constante es el único lugar donde aparece.
- [x] 1.2 Devolver ese plazo al punto de venta junto con el identificador de la intención, sin
      alterar lo demás que ya devuelve. Verificar: un test comprueba que la respuesta lo incluye y
      que el identificador sigue llegando igual.

## 2. La espera se deriva del plazo

- [x] 2.1 Calcular el tope de espera a partir del plazo recibido más un margen proporcional con un
      piso, y conservar el valor actual como respaldo para el caso de que la respuesta no traiga el
      plazo. Verificar: con el plazo habitual el tope queda por encima de él, y sin plazo en la
      respuesta el cobro igual tiene tope.
- [x] 2.2 Comprobar que el mensaje de vencimiento le gana al del tope local. Verificar: con el plazo
      habitual, el margen alcanza para que una consulta de estado llegue y se procese antes de que
      dispare el tope.

## 3. Cierre

- [x] 3.1 Subir la versión del módulo. Verificar: el manifiesto declara la versión nueva.
- [x] 3.2 Correr la suite de `payment_nave` y `pos_nave`, más flake8 y bandit según `.agent/rules.md`
      §6. Verificar: 0 fallos, 0 errores de lint y 0 hallazgos de severidad media o superior.
- [ ] 3.3 Desplegar y ejecutar el caso C6 con la terminal: lanzar un cobro y no tocar nada hasta que
      venza. Verificar: el cajero recibe el aviso de que la intención expiró, no el de verificar la
      terminal, y la línea queda reintentable. Registrarlo en el plan de homologación.
