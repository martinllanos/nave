# Spec Delta

## ADDED Requirements

### Requirement: El método de pago indica de dónde sale su identificador

La configuración de un método de pago presencial de Nave DEBE indicar de dónde obtener el `pos_id`
del dispositivo y cómo reconocer su fila en el archivo de identificadores que entrega Nave, porque
cada terminal y cada QR tienen el suyo y un identificador cruzado hace que Nave rechace el cobro sin
decir cuál está mal.

#### Scenario: Administrador configura una terminal

- **WHEN** un administrador configura un método de pago con una terminal Nave Point
- **THEN** la ayuda del identificador indica de dónde descargar el archivo de identificadores de Nave
- **AND** indica que la fila es la de la terminal, reconocible por el número de serie impreso en el
  equipo

#### Scenario: Administrador configura un QR

- **WHEN** un administrador configura un método de pago con un QR
- **THEN** la ayuda indica que la fila es la del QR, reconocible por su nombre junto con el del local
  al que pertenece
