# GRAPH

**Un patrón de diseño para arquitecturas agénticas — análogo a SOLID, pero
para cómo se comporta un agente de IA autónomo, no para cómo se escribe una
clase.**

Si le das autonomía a un agente de IA sobre tu proyecto, en algún momento va
a: inventar contexto que no tiene, aplicar cambios grandes sin que nadie los
revise, quedarse en un loop repitiendo lo mismo, u olvidarse todo entre una
sesión y la otra. GRAPH es un conjunto de 5 reglas + un mecanismo de freno
para que eso no pase — instalable en cualquier proyecto en un comando.

## Instalación

Ver [INSTALL.md](./INSTALL.md).

## Las 5 letras

- **G — Grounded**: el agente consulta el conocimiento real del proyecto
  antes de actuar, no inventa ni asume.
- **R — Reviewable**: los cambios que importan quedan esperando tu
  aprobación explícita antes de aplicarse.
- **A — Agnostic**: no depende de una sola herramienta — funciona igual en
  Claude Code, Cursor, Antigravity, o lo que uses.
- **P — Persistent**: el contexto sobrevive entre sesiones, no se repite
  desde cero cada vez.
- **H — Hierarchical**: el conocimiento del proyecto se organiza por
  comunidades/nodos, con su historial pegado al lado.

Más un extra que no entra en la sigla: **Circuit Breaker** — el freno de
mano que corta si el agente encadena demasiadas acciones seguidas o se
queda repitiendo lo mismo sin avanzar.

Spec completa (una vez instalado): `.agents/graph/GRAPH.md`.
Explicación en criollo: `.agents/graph/README.md`.

## Qué instala

```
.agents/
├── graph/
│   ├── GRAPH.md              → spec completa del patrón
│   ├── README.md             → explicación simple
│   ├── circuit-breaker.yml   → config del freno de mano (protegida por gate)
│   ├── knowledge/            → grafo real del código, indexado automáticamente
│   ├── gates/
│   │   ├── policy.yml        → severidades de acciones (low/medium/high/critical)
│   │   ├── pending/          → propuestas esperando aprobación humana
│   │   └── approved/         → lo ya aprobado
│   ├── sessions/
│   │   ├── progress.md       → qué se hizo, sesión por sesión
│   │   └── tasks.md          → qué falta
│   └── enforcement/          → hooks que hacen cumplir el circuit breaker de verdad
└── roles/                    → planner / executor / reviewer
```

Cuando un usuario escribe `#task` en su prompt, esa tarea debe agregarse
como una entrada nueva en `.agents/graph/sessions/tasks.md`. No basta con
mencionarlo en la conversación: el backlog real se escribe en este archivo.

El prompt `#run` ordena la ejecución de tareas pendientes en `.agents/graph/sessions/tasks.md`, y
el resultado debe quedar registrado en `.agents/graph/sessions/progress.md`.


## Convenciones de uso de `#task` y `#run`

- `#task` agrega una nueva tarea al backlog real en `.agents/graph/sessions/tasks.md`.
- La metadata de la tarea puede ir en el mismo prompt como pares `key:value`.
- Cuando la tarea trae metadata, el script la guarda como un bloque indentado debajo de la linea de la tarea.
- `#run` marca la siguiente tarea pendiente, o la que indiques con `#run 2` / `#run all`, y actualiza `.agents/graph/sessions/progress.md`.

Ejemplos:

```text
#task Crear page path:app/pages/home.tsx type:page priority:high
#task Revisar hook file:hooks/stagnation-hook.sh type:service priority:medium
#run
#run 2: listo para integrar
```

## Por qué esto y no otra cosa

Ninguna pieza individual es nueva — grounding vía knowledge graphs,
human-in-the-loop, circuit breakers para agentes, y el propio `AGENTS.md`
(que es un estándar real, mantenido por la Linux Foundation) ya existen por
separado en la industria. GRAPH es la curaduría de esas piezas en un solo
patrón instalable, con un checklist de auto-auditoría de 6 puntos para
saber si tu proyecto realmente lo cumple — no solo si lo tiene declarado en
un YAML.

## Indexador propio, sin dependencias de terceros

El indexado de código (`knowledge/nodes/`, `knowledge/communities/`) lo
hace un script propio del plugin, usando solo la librería estándar de
Python — nada de instalar ni depender de ninguna herramienta externa. Eso
es lo que hace posible el principio **A (Agnostic)**: cualquiera lo corre,
en cualquier proyecto, sin pedirle nada más que tener Python 3.

## Contribuir

Es un patrón pensado para ser colaborativo — si mejorás el indexador, los
hooks, o encontrás un bug real (probado, no teórico), un PR es bienvenido.

## Licencia

MIT — ver [LICENSE](./LICENSE).


## Release Package

To build a clean bundle for publishing, run `python3 scripts/build-release.py`.
The output is source-only and excludes runtime artifacts like `.agents/` and
local test output.

The release script also supports `--versioned`, which emits a sibling bundle named with the plugin version (for example `template-ia-release-v3.1.0`) and validates that both plugin manifests share the same semver first.

For the end-to-end publishing checklist, see [RELEASE.md](./RELEASE.md).
