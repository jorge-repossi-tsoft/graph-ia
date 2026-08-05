# Tasks

> Estilo SDD (spec-driven development). Vive junto a `progress.md` pero con
> foco distinto: `progress.md` es "qué pasó", `tasks.md` es "qué falta y en qué orden".
>
> Si el usuario escribe `#task` en su prompt, la nueva tarea debe agregarse
> aquí para quedar registrada en el backlog versionado.
> Cada tarea completada debe dejar rastro en `graph/sessions/progress.md` y/o
> en `graph/history/`, no alcanza con tildarla solo aquí.

## Instalación del patrón (marcar al hacer template-ia)
- [ ] Modo detectado: greenfield | brownfield
- [ ] Árbol de carpetas creado
- [ ] (brownfield only) Indexación inicial completa — bloqueante, ningún agente opera antes de esto
- [ ] (brownfield only) Reconciliación de historial vía git log completada, commits marcados `origen: pre-graph`
- [ ] circuit-breaker.yml revisado y ajustado a este proyecto (los defaults son conservadores)
- [ ] policy.yml revisado — ¿las severidades por defecto tienen sentido para este proyecto?
- [ ] roles/registry.yml — ¿qué roles se activan en este proyecto? (no todos son obligatorios)

## Backlog del proyecto
### Tareas pendientes
- [ ] <tarea 1>
    - type: page
    - path: app/pages/home.tsx
- [ ] <tarea 2>
    - type: api
    - path: app/api/items/route.ts

### Tareas en curso
- [ ] <tarea en progreso si aplica>

### Tareas completadas (referenciar en `progress.md`)
- [x] <tarea completada> — detalle breve

## Convención
Cada tarea que un agente tome de acá debe, al completarse, dejar rastro en
`graph/sessions/progress.md` — no alcanza con tildarla acá.

## Metadata de tarea
Las tareas pueden llevar un bloque de metadata indentado debajo de la línea de
la tarea, para que los agentes y el gestor del backlog puedan leer campos como
`type`, `path`, `file`, `community`, `priority`, `description`, etc.
