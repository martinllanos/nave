# Tasks

## 1. El catálogo

- [x] 1.1 Agregar a `payment_nave/models/nave_reasons.py` `NAVE_INTENT_ERROR_MESSAGES` y
      `nave_intent_error(payload)`, con la normalización y los alias de `design.md`. Verificar: un
      test comprueba la clave para cada ejemplo documentado (forma del QR y de Nave Point), para la
      respuesta real de `invalid_pos`, y `''` para un código desconocido o un cuerpo vacío.

## 2. El aviso del POS

- [x] 2.1 Agregar `_nave_intent_error_message(exc)` en `pos_nave/models/pos_payment_method.py` y usarla
      en `nave_send_payment_intent`. Verificar con tests: la respuesta real de `invalid_pos` da el
      mensaje del catálogo, con *"Para soporte"*, el código y el HTTP; `NO_GATEWAYS_AVAILABLE` en la
      forma del QR da su mensaje; un código desconocido da el mensaje de Nave como hoy; un 503 sin
      JSON da la pista por HTTP como hoy.
- [x] 2.2 En el error de `nave_send_payment_intent`, registrar el cuerpo de la respuesta y llamar a
      `_nave_log_invalid_pos` con el medio y el `pos_id`. Verificar: un test comprueba que un
      `invalid_pos` deja en el log el medio (`static_qr` o `smart_pos`) y el `pos_id`.

## 3. Cierre

- [x] 3.1 Subir `payment_nave` a `18.0.1.12.4` y `pos_nave` a `18.0.1.11.3`. Verificar: los
      manifiestos declaran las versiones nuevas.
- [x] 3.2 Correr las suites de `payment_nave` y `pos_nave`, más flake8 y bandit según
      `.agent/rules.md` §6. Verificar: 0 fallos, 0 errores de lint y 0 hallazgos de severidad media o
      superior.
- [ ] 3.3 Desplegar, verificar versiones y hashes en el contenedor, y provocar `invalid_pos` en
      producción. Primero por shell, sin guardar nada: `nave_send_payment_intent` con el `pos_id` de
      la terminal en el método QR, revisando el mensaje devuelto y el log. Después, con el visto bueno
      del usuario, en el POS: el usuario pone el `pos_id` de la terminal en *Nave QR*, intenta un
      cobro, captura el aviso y restaura el valor. Registrar el resultado en el plan (§3.43 y fila
      H8).
