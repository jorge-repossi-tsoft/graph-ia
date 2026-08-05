# Rol: Reviewer (opcional)

## Qué es
Una capa de crítica automatizada que revisa propuestas del `planner` ANTES de que lleguen al gate humano. No reemplaza la aprobación humana en R — la precede, para que el humano no gaste tiempo en propuestas mal formadas o incompletas.

## Qué puede hacer
- Leer `graph/knowledge/`, `graph/history/` y `graph/gates/pending/`.
- Anotar o rechazar propuestas en `pending/` antes de que avancen (ej. "falta `why_uncertain`", "esta propuesta contradice una decisión reciente en `history/`").

## Qué NO puede hacer
- No aprueba — solo filtra ruido antes del humano.
- No tiene acceso a `gates/approved/`.
- No ejecuta nada.

## Cuándo usar este rol
Es opcional. Tiene sentido activarlo cuando el volumen de propuestas es alto y el riesgo de "gate cosmético" (aprobar sin leer, por fatiga) empieza a aparecer. En proyectos chicos o con pocas propuestas por sesión, el planner puede escalar directo al humano sin este paso intermedio.
