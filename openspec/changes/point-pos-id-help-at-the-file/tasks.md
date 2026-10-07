# Tasks

## 1. Proveedor de pago

- [x] 1.1 Reescribir la ayuda de `nave_pos_id` y de `nave_payment_link_pos_id` según la redacción de
      `design.md`, citando `invalid_pos` en lugar de `409 INVALID_POS`. Verificar: un test lee la
      ayuda de cada campo del modelo y comprueba que nombra el archivo `POS_ID-`, la sección
      *Sistema de gestión* y el valor de *Medio de cobro* que le corresponde (`ECOMMERCE` o `LDP`).
- [x] 1.2 Corregir los comentarios que citan `409 INVALID_POS` en `payment_provider.py` y
      `payment_transaction.py`. Verificar: una búsqueda de `409` en `payment_nave/models/` no
      encuentra referencias al rechazo por identidad.

## 2. Punto de venta

- [x] 2.1 Reescribir la ayuda de `nave_terminal_id` según la redacción de `design.md`. Verificar: un
      test comprueba que la ayuda nombra el archivo `POS_ID-`, la sección *Sistema de gestión* y los
      valores `NAVE POINT` y `QR` de *Medio de cobro*.
- [x] 2.2 Alinear la descripción del manifiesto de `pos_nave` con la ayuda: que nombre el archivo y
      diga que cada dispositivo tiene su fila. Verificar: la descripción menciona `POS_ID-<CUIT>.xlsx`.

## 3. Cierre

- [x] 3.1 Subir las versiones de `payment_nave` y `pos_nave`. Verificar: los manifiestos declaran las
      versiones nuevas.
- [x] 3.2 Correr las suites de `payment_nave` y `pos_nave`, más flake8 y bandit según
      `.agent/rules.md` §6, y buscar en las ayudas cualquier identificador real. Verificar: 0 fallos,
      0 errores de lint, 0 hallazgos de severidad media o superior, y ningún UUID, número de serie
      ni código de vinculación en los textos nuevos.
- [ ] 3.3 Desplegar y ver las ayudas en la configuración del proveedor y del método de pago del
      punto de venta. Verificar: se leen completas al pasar el cursor sobre cada campo.
