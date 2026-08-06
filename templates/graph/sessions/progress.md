# Progress

> Este archivo es la memoria persistente entre sesiones (principio P).
> Cada sesión de trabajo debe actualizar esto antes de cerrar — no confiar
> en que el contexto de la conversación sobreviva.

## Estado actual
- Instalación: <greenfield | brownfield> — completada el <fecha>
- Indexación inicial: <pendiente | completa>
- Reconciliación de historial (solo brownfield): <n/a | importado vía git log | omitido>
- Backlog activo: <número de tareas pendientes>
- Última ejecución de `#run`: <fecha o n/a>

## Última sesión
- Fecha:
- Qué se hizo:
- Tareas completadas:
  - [x] <tarea 1> — nota breve
  - [x] <tarea 2> — nota breve
- Tareas pendientes que siguen en `tasks.md`:
  - [ ] <tarea 3>
- Por qué (si algo se cortó por circuit breaker, referenciar el evento en `graph/history/circuit-breaker-events.jsonl`):
  - <detalle>

## Próxima sesión debería
- <qué se espera avanzar a continuación>

## Notas adicionales
- <observaciones relevantes, decisiones, riesgos, bloqueos>
