# Tasks

## 1. La baja que Nave acepta

- [x] 1.1 Declarar el motivo de baja en una constante, con la explicación de por qué el texto es
      fijo, y mandarlo en `nave_cancel_payment_intent`. Verificar: un test comprueba que el `DELETE`
      lleva exactamente `{"reason": {"code": "disabled_from_saas", "description": "disabled from
      SAAS"}}`.
- [x] 1.2 Si Nave responde 400 con `Invalid input reason`, repetir la baja una vez sin cuerpo.
      Verificar: un test comprueba el segundo `DELETE` sin cuerpo y el éxito; otro, que un 400 por
      otra causa no se reintenta.
- [x] 1.3 Registrar en el log el código HTTP y el cuerpo de la respuesta cuando la baja falla.
      Verificar: un test comprueba que el registro trae el mensaje de Nave.

## 2. Lo que el código afirmaba

- [x] 2.1 Corregir el comentario de `pos_payment_method.py`, el de `send_payment_cancel` en
      `payment_nave.js` y el docstring de `test_18`, que afirman que Nave no permite dar de baja una
      intención de terminal. Verificar: ninguno de los tres lo afirma.

## 3. Cierre

- [x] 3.1 Subir la versión de `pos_nave`. Verificar: el manifiesto declara la versión nueva.
- [x] 3.2 Correr las suites de `payment_nave` y `pos_nave`, más flake8 y bandit según
      `.agent/rules.md` §6. Verificar: 0 fallos, 0 errores de lint y 0 hallazgos de severidad media o
      superior.
- [x] 3.3 Desplegar y probar con la terminal, sin pagar: A, cancelar con la terminal pidiendo la
      tarjeta; B, cancelar con el cliente en *"Elegí la cantidad de cuotas"*; C, tocar *volver* en
      la terminal y cancelar. Verificar: en A la terminal vuelve a reposo y no hay aviso; en B y C
      queda registrado qué respondió Nave. Registrar los resultados en el plan como reprueba de C4.
