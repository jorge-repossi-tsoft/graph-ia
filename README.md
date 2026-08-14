# GRAPH

**Un patrÃ³n de diseÃ±o para arquitecturas agÃ©nticas â€” anÃ¡logo a SOLID, pero
para cÃ³mo se comporta un agente de IA autÃ³nomo, no para cÃ³mo se escribe una
clase.**

Si le das autonomÃ­a a un agente de IA sobre tu proyecto, en algÃºn momento va
a: inventar contexto que no tiene, aplicar cambios grandes sin que nadie los
revise, quedarse en un loop repitiendo lo mismo, u olvidarse todo entre una
sesiÃ³n y la otra. GRAPH es un conjunto de 5 reglas + un mecanismo de freno
para que eso no pase â€” instalable en cualquier proyecto en un comando.

## InstalaciÃ³n

Ver [INSTALL.md](./INSTALL.md).

## Las 5 letras

- **G â€” Grounded**: el agente consulta el conocimiento real del proyecto
  antes de actuar, no inventa ni asume.
- **R â€” Reviewable**: los cambios que importan quedan esperando tu
  aprobaciÃ³n explÃ­cita antes de aplicarse.
- **A â€” Agnostic**: no depende de una sola herramienta â€” funciona igual en
  Claude Code, Cursor, Antigravity, o lo que uses.
- **P â€” Persistent**: el contexto sobrevive entre sesiones, no se repite
  desde cero cada vez.
- **H â€” Hierarchical**: el conocimiento del proyecto se organiza por
  comunidades/nodos, con su historial pegado al lado.

MÃ¡s un extra que no entra en la sigla: **Circuit Breaker** â€” el freno de
mano que corta si el agente encadena demasiadas acciones seguidas o se
queda repitiendo lo mismo sin avanzar.

Spec completa (una vez instalado): `.agents/graph/GRAPH.md`.
ExplicaciÃ³n en criollo: `.agents/graph/README.md`.

## QuÃ© instala

```text
.agents/
â”œâ”€â”€ graph/
â”‚   â”œâ”€â”€ GRAPH.md              â†’ spec completa del patrÃ³n
â”‚   â”œâ”€â”€ README.md             â†’ explicaciÃ³n simple
â”‚   â”œâ”€â”€ circuit-breaker.yml   â†’ config del freno de mano (protegida por gate)
â”‚   â”œâ”€â”€ knowledge/            â†’ grafo real del cÃ³digo, indexado automÃ¡ticamente
â”‚   â”œâ”€â”€ gates/
â”‚   â”‚   â”œâ”€â”€ policy.yml        â†’ severidades de acciones (low/medium/high/critical)
â”‚   â”‚   â”œâ”€â”€ pending/          â†’ propuestas esperando aprobaciÃ³n humana
â”‚   â”‚   â””â”€â”€ approved/         â†’ lo ya aprobado
â”‚   â”œâ”€â”€ sessions/
â”‚   â”‚   â”œâ”€â”€ progress.md       â†’ quÃ© se hizo, sesiÃ³n por sesiÃ³n
â”‚   â”‚   â””â”€â”€ tasks.md          â†’ quÃ© falta
â”‚   â””â”€â”€ enforcement/          â†’ hooks que hacen cumplir el circuit breaker de verdad
â””â”€â”€ roles/                    â†’ planner / executor / reviewer
```

Cuando un usuario escribe `#task` en su prompt, esa tarea debe agregarse
como una entrada nueva en `.agents/graph/sessions/tasks.md`. No basta con
mencionarlo en la conversaciÃ³n: el backlog real se escribe en este archivo.

Los prompts `#run` / `#run-all` ordenan la ejecuciÃ³n de tareas pendientes en
`.agents/graph/sessions/tasks.md`, `#done` y `#skip` cierran o saltean tareas
puntuales, y `#note` deja notas fechadas en una tarea. Toda operaciÃ³n que
cambie el estado del backlog debe quedar registrada en
`.agents/graph/sessions/progress.md`.

## Comandos de backlog (`#task`, `#run`, `#run-all`, `#done`, `#skip`, `#note`)

El backlog vive en `.agents/graph/sessions/tasks.md` y cada ejecuciÃ³n deja
rastro en `.agents/graph/sessions/progress.md`. El set mÃ­nimo de comandos:

- `#task <descripciÃ³n>` agrega una nueva tarea al backlog real. La metadata
  puede ir en el mismo prompt como pares `key:value`; el script la guarda
  como un bloque indentado debajo de la lÃ­nea de la tarea.
- `#run` ejecuta (marca completada) la siguiente tarea pendiente, o la que
  indiques con `#run 2`. Acepta una nota de cierre: `#run 2: listo para integrar`.
- `#run-all` ejecuta todas las tareas pendientes de una vez (alias de `#run all`).
- `#done [N]` marca una tarea como completada sin pasar por ejecuciÃ³n
  (por ejemplo, si ya estaba resuelta en otra rama).
- `#skip [N]` saltea una tarea: sale de pendientes y queda registrada en
  `### Tareas salteadas (con motivo)` con el motivo y la fecha.
- `#note [N]: <texto>` agrega una nota fechada debajo de una tarea
  pendiente, sin cambiar su estado.

En todos los casos `N` es la posiciÃ³n dentro de las pendientes; si se
omite, aplica sobre la primera.

Ejemplos:

```text
#task Crear page path:app/pages/home.tsx type:page priority:high
#task Revisar hook file:hooks/stagnation-hook.sh type:service priority:medium
#run
#run 2: listo para integrar
#run-all: cierre de sprint
#done 2: ya estaba resuelta en otra rama
#skip 3: fuera de alcance del sprint
#note 1: falta definir el endpoint
```

## Por quÃ© esto y no otra cosa

Ninguna pieza individual es nueva â€” grounding vÃ­a knowledge graphs,
human-in-the-loop, circuit breakers para agentes, y el propio `AGENTS.md`
(que es un estÃ¡ndar real, mantenido por la Linux Foundation) ya existen por
separado en la industria. GRAPH es la curadurÃ­a de esas piezas en un solo
patrÃ³n instalable, con un checklist de auto-auditorÃ­a de 6 puntos para
saber si tu proyecto realmente lo cumple â€” no solo si lo tiene declarado en
un YAML.

## Indexador propio, sin dependencias de terceros

El indexado de cÃ³digo (`knowledge/nodes/`, `knowledge/communities/`) lo
hace un script propio del plugin, usando solo la librerÃ­a estÃ¡ndar de
Python â€” nada de instalar ni depender de ninguna herramienta externa. Eso
es lo que hace posible el principio **A (Agnostic)**: cualquiera lo corre,
en cualquier proyecto, sin pedirle nada mÃ¡s que tener Python 3.

## `graph` CLI

Para no depender de rutas largas, el repo incluye un wrapper en `bin/`:

- `bin/graph.ps1` + `bin/graph.cmd` (Windows)
- `bin/graph` (Linux/macOS)

El comando se registra solo en tu PATH de usuario la primera vez que usÃ¡s
el plugin (vÃ­a hook en Claude Code/Codex, o al correr `install.sh`) â€” solo
hace falta abrir una terminal nueva esa primera vez.

El wrapper busca `graph-ia.py` en este orden:

1. `GRAPH_IA_SCRIPT`
2. `GRAPH_IA_ROOT\scripts\graph-ia.py`
3. el checkout local del repo del plugin
4. la instalaciÃ³n activa de Codex vÃ­a `codex plugin list`

Uso:

```bash
graph --reindex
graph --update-docs
graph --mode=greenfield
graph --mode=brownfield --migrate
```

`--migrate` copia `.agents/system.md` a `.agents/graph/legacy-system.md` y conserva el archivo original.

Si no encuentra `graph-ia.py`, falla con un mensaje claro para que puedas instalar el plugin o apuntar el checkout correcto sin tocar rutas fijas.

## Contribuir

Es un patrÃ³n pensado para ser colaborativo â€” si mejorÃ¡s el indexador, los
hooks, o encontrÃ¡s un bug real (probado, no teÃ³rico), un PR es bienvenido.

## Licencia

MIT â€” ver [LICENSE](./LICENSE).

## Release Package

To build a clean bundle for publishing, run `python3 scripts/build-release.py`.
The output is source-only and excludes runtime artifacts like `.agents/` and
local test output.

The release script also supports `--versioned`, which emits a sibling bundle named with the plugin version (for example `graph-ia-release-v3.1.0`) and validates that both plugin manifests share the same semver first.

For the end-to-end publishing checklist, see [RELEASE.md](./RELEASE.md).
