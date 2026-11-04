# Guía de etiquetado: reseñas de Rappi

Estas etiquetas miden la exactitud de P2.4. Etiqueta lo que dice el **texto**, no las estrellas.

## Sentimiento: elige uno

| Valor | Cuándo usarlo | Ejemplo inventado |
|---|---|---|
| `positivo` | Predomina la satisfacción o la recomendación | "Llegó rápido y muy bien empacado" |
| `negativo` | Predomina una queja, un problema o la frustración | "Pedí hace dos horas y nada que llega" |
| `neutro` | Es informativo, una pregunta o una sugerencia, o lo bueno y lo malo pesan igual | "¿Cómo cambio la dirección de un pedido?" |

- **Mezcla:** gana lo que más pesa. "Linda app, pero me cobraron doble" es `negativo`.
- **Sarcasmo:** vale la intención. "Excelente, solo tardó tres horas" es `negativo`.
- **Estrellas contradictorias:** 5 estrellas con una queja es `negativo`.

## Tema: elige el principal

| Valor | Trata sobre |
|---|---|
| `entregas` | Demoras, pedidos incompletos o equivocados, estado del pedido |
| `cobros_y_pagos` | Cobros dobles, reembolsos, tarjetas, RappiPay, medios de pago |
| `soporte` | Atención al cliente, chat, respuestas de la empresa |
| `precios` | Costo de productos, domicilio, propinas, promociones, Rappi Prime |
| `app` | Fallas, errores, lentitud, diseño, actualizaciones, inicio de sesión |
| `repartidores` | Trato o conducta del repartidor |
| `sin_tema` | Opinión general sin ninguno de los temas anteriores |

**Si hay varios temas**, elige el que motivó la reseña. Una demora es `entregas`; que nadie la resolviera es `soporte`. Un repartidor que no llegó es `entregas`; uno grosero es `repartidores`.

**Cómo trabajar:** Sara y Gabriel etiquetan por separado las primeras 20 filas y comparan; luego se reparten las 180 restantes. No usen un modelo para decidir. Al final, `validar_muestra.py` debe responder `PASA`.
