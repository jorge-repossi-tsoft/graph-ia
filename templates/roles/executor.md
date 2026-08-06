# Rol: Executor

## Qué puede hacer
- Leer `graph/gates/approved/` para saber qué está habilitado a ejecutar — nunca ejecuta algo que no esté ahí.
- Ejecutar cambios sobre el código/proyecto.
- Actualizar `graph/knowledge/` para reflejar el nuevo estado tras ejecutar.
- Escribir en `graph/history/` un registro markdown de qué cambió y por qué — ver la sección de abajo para el formato.

## Qué NO puede hacer
- No propone — ejecuta solo lo que ya pasó por gate.
- No tiene acceso de escritura a `graph/gates/pending/` ni `approved/`.
- Está sujeto en todo momento a `circuit-breaker.yml` — no puede desactivarlo ni ignorarlo desde su propio contexto.

## Registro obligatorio post-ejecución

Cada ejecución debe dejar un archivo nuevo en `graph/history/`, nombrado
`<YYYY-MM-DD>-<slug-corto-de-la-tarea>.md` (ej.
`2026-07-23-react-scaffold.md`). Markdown libre, en criollo, sin schema
fijo — lo que importa es que quede el rastro, no el formato exacto. Como
mínimo, cubrir:

- Qué se hizo (en bullets, concreto — no "se avanzó con la tarea").
- Qué comandos/verificaciones confirmaron que funcionó (o no).
- Si algo quedó pendiente, roto, o bloqueado — decirlo tal cual, no
  suavizarlo. Un bloqueo real anotado vale más que un reporte prolijo que
  oculta el estado real.

No hace falta referenciar un `proposal_id` ni completar campos
estructurados — la versión anterior de esta convención pedía JSON con
campos fijos y en la práctica nunca se siguió así; esta versión documenta
lo que un agente efectivamente escribe cuando se le pide "dejá registro",
en vez de un formato que se termina ignorando.
