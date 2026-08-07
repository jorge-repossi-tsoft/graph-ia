# AGENTS.md
### Punto de entrada único — cualquier asistente (Claude Code, Antigravity, Cursor, Copilot) lee este archivo primero.

<!-- template-ia:bridge-block -->
Este proyecto sigue el patrón **GRAPH**. Antes de actuar:

1. Leé `.agents/graph/GRAPH.md` — la spec completa del patrón.
2. Consultá `.agents/graph/knowledge/` antes de proponer cualquier cambio (principio G). Si está vacío, es un proyecto greenfield recién iniciado — está bien, pero el mecanismo de consulta igual debe usarse desde la primera tarea.
3. Revisá `.agents/graph/sessions/progress.md` y `tasks.md` para saber qué pasó antes de esta sesión (principio P).
4. Identificá tu rol en `.agents/roles/registry.yml` — cada rol tiene permisos distintos sobre `graph/`.
5. Cualquier propuesta de cambio con severidad `medium` o superior (ver `.agents/graph/gates/policy.yml`) va a `.agents/graph/gates/pending/` — no se ejecuta directo.
6. Estás sujeto a `.agents/graph/circuit-breaker.yml` en todo momento. No podés desactivarlo desde tu propio contexto.
7. Si el usuario escribe un mensaje que empieza con `#task`, tratá eso como una tarea nueva y agregala a `.agents/graph/sessions/tasks.md` con formato `- [ ] ...`, sin pedirle un comando aparte ni redirigirlo a la terminal. Asignale un **ID estable** `T-YYYYMMDD-NNN` (contador por día, no se repite nunca) como metadata indentada debajo de la línea (`- id: T-20260807-001`) — ese ID es la referencia que no cambia aunque después se complete, saltee o agregue otra tarea antes. Cuando una tarea se completa, su estado debe cambiar de `[]` a `[x]` y la conclusión debe registrarse también en `.agents/graph/sessions/progress.md`.
8. Si el usuario escribe un mensaje que empieza con `#run`, ejecutá las tareas pendientes de `.agents/graph/sessions/tasks.md` en orden, una por vez. Podés referenciar una tarea puntual por su posición entre pendientes (`#run 2`) o por su ID estable (`#run T-20260807-002`) — preferí el ID cuando la tarea se mencionó en un turno anterior, porque la posición se corre si de por medio se completó o salteó otra. `#run-all` ejecuta todas las pendientes de una vez.
9. Si el usuario escribe `#done [N|ID]`, marcá esa tarea (o la primera pendiente si no hay número ni ID) como completada `[x]` sin ejecutarla, y registrá el cierre en `progress.md`. Si escribe `#skip [N|ID]: <motivo>`, sacala de pendientes y movela a `### Tareas salteadas (con motivo)` en `tasks.md`, con motivo y fecha, dejando también rastro en `progress.md`. Si escribe `#note [N|ID]: <texto>`, agregá la nota fechada como línea indentada debajo de la tarea, sin cambiar su estado. En los tres casos, `N` es la posición actual entre pendientes e `ID` es el `T-YYYYMMDD-NNN` que le asignaste al crearla — cualquiera de los dos formatos es válido.

<!-- template-ia:legacy-line -->
## Bridges específicos por herramienta
- `CLAUDE.md` — bridge para Claude Code, apunta acá.
- (agregar bridges equivalentes para otras herramientas según se sumen)

## Regla de oro
Si una acción no está clasificada en `.agents/graph/gates/policy.yml`, tratala como severidad `high` por defecto. Nunca asumas bajo riesgo por omisión.
<!-- /template-ia:bridge-block -->