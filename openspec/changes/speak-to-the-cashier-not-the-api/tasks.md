# Tasks

## 1. Un rechazo se lee como un rechazo

- [x] 1.1 Clasificar `BLOCKED` junto a los rechazos, en lugar de tratarlo como bloqueo de seguridad,
      y dejar registrado en el código por qué: la evidencia de que Nave lo devuelve para rechazos
      corrientes. Verificar: un estado `BLOCKED` produce el aviso de rechazo y no el de seguridad.
- [x] 1.2 Redactar el aviso de rechazo para que indique probar con otra tarjeta, siguiendo lo que la
      propia terminal le dice al operador. Verificar: el texto no menciona contactar al proveedor ni
      motivos de seguridad.
- [x] 1.3 Cubrirlo con tests sobre la clasificación y el texto. Verificar: los tests fallan si
      `BLOCKED` vuelve a la rama de seguridad.

## 2. Los códigos internos no llegan a la pantalla

- [x] 2.1 Mostrar el motivo del proveedor sólo cuando parezca una frase y no un identificador, y
      dejar el motivo completo en la consola del navegador para diagnóstico. Verificar: un motivo con
      forma de código no aparece en el aviso, y uno en lenguaje llano sí.
- [x] 2.2 Dejar de inyectar el nombre del error HTTP como motivo al traducir una intención dada de
      baja. Verificar: la respuesta traducida informa el estado y ningún motivo, y un test lo
      comprueba.
- [x] 2.3 Redactar el aviso de baja para que diga que el cobro ya no está disponible y que puede
      generarse uno nuevo, sin atribuir la causa. Verificar: el texto no afirma que fue en la
      terminal.

## 3. Cierre

- [x] 3.1 Subir la versión del módulo. Verificar: el manifiesto declara la versión nueva.
- [x] 3.2 Correr la suite de `payment_nave` y `pos_nave`, más flake8 y bandit según `.agent/rules.md`
      §6. Verificar: 0 fallos, 0 errores de lint y 0 hallazgos de severidad media o superior.
- [ ] 3.3 Desplegar y repetir con la terminal los tres casos ya ejecutados: rechazo por fondos,
      cancelación desde la terminal y vencimiento. Verificar: los tres avisos describen la situación,
      ninguno muestra un código, y quedan registrados en el plan de homologación con sus capturas.
