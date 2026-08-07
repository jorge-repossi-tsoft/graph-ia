# GRAPH — en criollo

GRAPH es una forma de organizar cómo un agente de IA (Claude Code, Cursor,
Antigravity, el que sea) trabaja en tu proyecto, para que no actúe "a lo
loco" y siempre quede algo de vos en el medio antes de que pase algo
importante.

No es una librería ni un framework. Es más parecido a una checklist de
buenas prácticas — como SOLID para el código, pero para cómo se comporta un
agente autónomo.

## La idea en una frase

> El agente no actúa por las suyas: primero consulta lo que ya sabe del
> proyecto, y las decisiones importantes pasan por vos antes de ejecutarse.

## Las 5 partes (GRAPH es la sigla)

**G — Grounded (con los pies en la tierra)**
El agente mira el estado real del proyecto antes de proponer algo, no
inventa ni "recuerda mal" de la conversación. Toda esa info vive en
`graph/knowledge/`.

**R — Reviewable (revisable)**
Los cambios que importan no se aplican solos. Quedan esperando en
`graph/gates/pending/` hasta que alguien (vos) los apruebe. Nada de "el
agente decidió y ya está".

**A — Agnostic (no depende de una sola herramienta)**
Si mañana cambiás de Claude Code a Cursor o a lo que sea, el proyecto sigue
funcionando igual. Todo vive en archivos de texto comunes, no en algo
propietario de una sola app.

**P — Persistent (no se olvida de una sesión a la otra)**
Lo que se habló y se decidió ayer, queda escrito en
`sessions/progress.md` y `sessions/tasks.md`. La próxima sesión arranca
sabiendo qué pasó, no repite todo de cero.

**H — Hierarchical (organizado, no todo tirado junto)**
El conocimiento del proyecto se agrupa en comunidades y nodos (como carpetas
temáticas dentro de `knowledge/`), y cada cambio queda con su historial
pegado — no en un log aparte que nadie mira.

## El plus que no entra en la sigla: Circuit Breaker

Es el freno de mano. Si el agente se pone a hacer 25 cosas seguidas sin
parar, o repite lo mismo una y otra vez sin avanzar, esto lo corta solo y
te avisa. No hace falta que vos estés mirando todo el tiempo para que se
frene un loop descontrolado.

Vive en `graph/circuit-breaker.yml` (la configuración) + tres scripts que
realmente lo hacen cumplir (`graph/enforcement/`, aunque si instalaste esto
como plugin, esos scripts ya vienen activos solos, no hace falta tocar
nada).

## ¿Qué carpeta hace qué?

```
.agents/
├── graph/
│   ├── GRAPH.md              → la spec completa, para leer con más calma
│   ├── circuit-breaker.yml   → configuración del freno de mano
│   ├── knowledge/            → lo que el agente sabe del proyecto
│   ├── gates/
│   │   ├── pending/          → propuestas esperando tu aprobación
│   │   └── approved/         → lo que ya aprobaste
│   ├── sessions/
│   │   ├── progress.md       → qué se hizo, sesión por sesión
│   │   └── tasks.md          → qué falta hacer
│   └── enforcement/          → los scripts que hacen cumplir el freno de mano
└── roles/                    → qué puede hacer cada "sombrero" (planner, executor, reviewer)
```

## ¿Cómo lo uso día a día?

En la práctica, casi todo pasa solo:

1. Le pedís algo al agente.
2. Si es algo chico (leer, proponer un plan), lo hace directo.
3. Si es algo que cambia código o config importante, te va a dejar una
   propuesta en `gates/pending/` en vez de aplicarla sola.
4. Vos la mirás, la aprobás o la rechazás.
5. Si en algún momento el agente se traba en un loop, el circuit breaker
   corta solo y te avisa — no sigue insistiendo para siempre.

### Tokens de control en el prompt
- `#task` agrega una nueva tarea al backlog en `graph/sessions/tasks.md`.
- `#run` ejecuta tareas pendientes de `graph/sessions/tasks.md`, una por vez.
- `#run-all` ejecuta todas las pendientes de una vez.
- `#done` marca una tarea como completada sin ejecutarla.
- `#skip` saltea una tarea, dejándola registrada con motivo y fecha.
- `#note` agrega una nota fechada a una tarea pendiente.
- Si una tarea se completa, debe cambiar su estado a `[x]` en `tasks.md` y
  dejar registro en `graph/sessions/progress.md`.

Eso es todo. El resto (`GRAPH.md`, `policy.yml`, `registry.yml`) es la letra
chica para cuando quieras ajustar algo puntual.


## Convenciones de uso de los comandos de backlog

- `#task` agrega una nueva tarea al backlog real en `.agents/graph/sessions/tasks.md`
  y le asigna un **ID estable** `T-YYYYMMDD-NNN` (contador por día), guardado
  como metadata (`- id: T-20260807-001`) — nunca lo pongas vos a mano, lo
  genera el gestor de backlog para garantizar que no se repita.
- La metadata adicional de la tarea puede ir en el mismo prompt como pares `key:value`.
- Cuando la tarea trae metadata, el script la guarda como un bloque indentado debajo de la linea de la tarea.
- `#run` marca la siguiente tarea pendiente, o la que indiques con `#run 2` / `#run T-20260807-002` / `#run all`, y actualiza `.agents/graph/sessions/progress.md`.
- `#run-all` es el alias directo de `#run all`: cierra todas las pendientes.
- `#done [N|ID]` marca una tarea como completada sin ejecutarla (útil si ya se resolvió por otro camino); registra el cierre en `progress.md`.
- `#skip [N|ID]: <motivo>` saca la tarea de pendientes y la mueve a `### Tareas salteadas (con motivo)` con motivo y fecha.
- `#note [N|ID]: <texto>` agrega una nota fechada debajo de la tarea, sin cambiar su estado.
- En `#run`/`#done`/`#skip`/`#note`, la referencia puede ser `N` (la posición
  dentro de las pendientes en este momento; si se omite, aplica sobre la
  primera) **o** el ID estable (`T-YYYYMMDD-NNN`) que te devolvió `#task`.
  Usá el ID cuando vayas a referenciar la misma tarea más adelante en la
  sesión o en otra sesión — la posición se corre si de por medio se
  completó, salteó o agregó otra tarea antes; el ID no cambia nunca.

Ejemplos:

```text
#task Crear page path:app/pages/home.tsx type:page priority:high
#task Revisar hook file:hooks/stagnation-hook.sh type:service priority:medium
#run
#run 2: listo para integrar
#run T-20260807-002: listo para integrar
#run-all: cierre de sprint
#done 2: ya estaba resuelta en otra rama
#done T-20260807-002: ya estaba resuelta en otra rama
#skip 3: fuera de alcance del sprint
#skip T-20260807-003: fuera de alcance del sprint
#note 1: falta definir el endpoint
#note T-20260807-001: falta definir el endpoint
```
