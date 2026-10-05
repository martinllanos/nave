# Spec Delta

## ADDED Requirements

### Requirement: El cliente llega a la pantalla de pago con su intención cargada

Al enviar al cliente a pagar, la redirección DEBE conservar todos los parámetros con los que Nave
identifica la intención en la URL del checkout que devolvió.

Los parámetros DEBEN tomarse de esa URL, sin suponer cuáles son ni cuántos, porque los decide Nave y
no están documentados.

#### Scenario: El cliente paga desde la tienda

- **WHEN** el cliente confirma el pago de un pedido del e-commerce
- **THEN** llega a la pantalla de pago de Nave con la intención que se creó para ese pedido
- **AND** ve el importe y el detalle de su compra

#### Scenario: La URL del checkout trae varios parámetros

- **WHEN** Nave devuelve una URL de checkout con más de un parámetro
- **THEN** la redirección los conserva todos

#### Scenario: La URL del checkout no trae parámetros

- **WHEN** Nave devuelve una URL de checkout sin parámetros
- **THEN** la redirección lleva al cliente a esa URL tal como vino
