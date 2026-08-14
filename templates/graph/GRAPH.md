# GRAPH
### A Design Pattern for Agentic Architectures

**Categoría:** patrón de principios (no de stack) — análogo a SOLID, no a MEAN/MERN
**Alcance de este documento:** spec de referencia, agnóstica de proyecto. No nombra tecnologías, repos ni casos particulares — aplica igual a un proyecto que arranca de cero o a uno con años de historia.

---

## Definición

> **GRAPH es un patrón de diseño para sistemas agénticos en el que el conocimiento del sistema vive en un grafo versionado y jerárquico, y toda acción autónoma queda subordinada a ese grafo mediante puntos explícitos de revisión humana.**

Si un sistema agéntico no tiene un grafo de conocimiento gobernando sus decisiones, no es GRAPH — sin importar cuán sofisticado sea el modelo que corra por debajo.

---

## Los cinco principios

Las letras tienen dependencia entre sí: **G es la base** (sin grafo, no hay nada que jerarquizar ni nada contra qué revisar). **H depende de G**. **P depende de H**. **A es transversal** — la condición de que nada de esto dependa de una sola herramienta.

### G — Grounded
El agente actúa consultando el knowledge graph, no la memoria de contexto de la sesión.

- **Anti-patrón — Amnesia de contexto:** el agente re-explora o re-infiere lo que el grafo ya sabe, porque nunca lo consultó.
- **Anti-patrón — Colisión de identidad:** dos archivos distintos (ej. `layout.css` y `layout.tsx`) terminan generando el mismo node ID porque el slug se derivó solo del nombre base, sin extensión. El resultado es que un nodo se pisa a otro silenciosamente — el grafo queda incompleto sin que nada lo avise, que es una forma silenciosa de romper G.
- Se cumple con: indexación incremental, community detection — el principio no exige un motor específico.
- **Convención obligatoria de node ID:** el identificador de cada nodo debe incluir la ruta completa con extensión (ej. `app/layout.tsx`, no `layout`), o un hash del path completo si se prefiere un ID corto. Nunca derivar el ID solo del nombre base del archivo — cualquier proyecto con archivos homónimos de distinta extensión (patrón muy común: `Component.tsx` + `Component.css`, `schema.json` + `schema.ts`) va a colisionar si no se sigue esta regla.

**Convención obligatoria de aristas (edges):** un nodo sin referencias a otros nodos no es parte de un grafo — es un ítem de lista con metadata. Todo nodo en `knowledge/nodes/` debe incluir, como mínimo:

```json
{
  "id": "...",
  "community": "...",
  "references": ["<node_id>", "..."],      // qué otros nodos importa/usa este
  "referenced_by": ["<node_id>", "..."]     // qué otros nodos lo importan/usan a él
}
```

Un indexador que solo agrupa por carpeta y no resuelve imports/dependencias reales no cumple G, aunque tenga nodos y comunidades — cumple la mitad del principio. `referenced_by` puede derivarse automáticamente invirtiendo `references` una vez indexado todo el proyecto; no hace falta calcularlo dos veces.

### R — Reviewable
Ninguna acción autónoma relevante se aplica sin un punto de aprobación humana explícito.

- **Anti-patrón — Gate cosmético:** existe un botón de "aprobar", pero nadie lo revisa realmente.
- Se cumple con: approval gates graduados por riesgo (ver `gates/policy.yml`).

### A — Agnostic
El mismo patrón funciona igual sin importar el stack o el asistente que lo ejecute.

- **Anti-patrón — Vendor lock invisible:** el patrón depende de una API propietaria de una sola herramienta.
- Se cumple con: un documento fuente único (`AGENTS.md`) leído de forma equivalente por distintos asistentes.

### P — Persistent
El contexto sobrevive entre sesiones; el agente no arranca de cero cada vez.

- **Anti-patrón — Sesión huérfana:** cada conversación nueva repite exploración ya hecha.
- Se cumple con: `sessions/progress.md`, `sessions/tasks.md` versionados en disco.
- **Regla de backlog:** `sessions/tasks.md` se interpreta como grafo dirigido de tareas, no como lista visual. Una tarea con `depends_on`, `blocked_by`, `requires`, `parent` o `prerequisite` solo puede ejecutarse si toda su cadena de IDs esta completada; si algo esta pendiente, salteado, fallido o no validable, la ejecucion se detiene y queda registrada en `sessions/progress.md`.

### H — Hierarchical
El grafo se organiza en niveles (comunidades → subgrafos → nodos), y cada nivel arrastra su propio historial de cambios — la trazabilidad no es un log aparte, vive incorporada a la estructura misma.

- **Anti-patrón — Historial fantasma:** hay jerarquía, pero el registro de "por qué cambió esto" vive en un changelog separado que nadie consulta.
- Se cumple con: metadata de "cuándo y por qué" adjunta a cada nodo/comunidad en `history/`.

---

## Extensión: Circuit Breaker

GRAPH describe invariantes de estado. El **Circuit Breaker** es el mecanismo de control temporal que hace que R sea real en un sistema que corre de forma autónoma entre gates — no es una sexta letra, es un principio complementario, igual que "fail fast" convive con SOLID sin ser parte del acrónimo.

Componentes mínimos (ver `circuit-breaker.yml`):
- **Iteration cap** — límite duro de ciclos antes de detenerse y reportar estado.
- **No-progress detection** — corte automático si no hay progreso medible en N ciclos.
- **Enforcement externo** — el corte no puede ser evadido por el propio agente; vive en la capa de configuración, no en el prompt.
- **Auditoría del corte** — todo corte queda registrado: qué lo disparó, qué estaba haciendo el agente, cuántos pasos habían transcurrido.

**Límite honesto:** `circuit-breaker.yml` por sí solo es declarativo — expresa intención, no aplicación. "Enforcement externo" solo es real si hay un adaptador conectado en `enforcement/` que efectivamente intercepta y bloquea llamadas antes de que ocurran. Sin eso, el circuit breaker es una promesa que el agente se hace a sí mismo — el anti-patrón exacto que este mismo principio busca evitar. Ver `enforcement/README.md` para el estado de adaptadores disponibles y cómo agregar uno nuevo.

---

## Checklist de aplicación

- [ ] **G** — ¿Hay un grafo de conocimiento real, o texto plano disfrazado de contexto?
- [ ] **R** — ¿Hay al menos un gate humano que se usa de verdad, no cosmético?
- [ ] **A** — ¿El patrón sobrevive un cambio de asistente sin reescritura?
- [ ] **P** — ¿La sesión de mañana sabe lo que pasó hoy sin que se le repita?
- [ ] **H** — ¿Un nodo específico puede responder "por qué estoy así"?
- [ ] **Circuit Breaker** — ¿hay un adaptador en `enforcement/` REALMENTE conectado (no solo `circuit-breaker.yml` escrito), que bloquea antes de que la acción ocurra Y detecta estancamiento, no solo iteration cap?

Una respuesta "no" no es fracaso — es una señal concreta de qué falta implementar.

---

## Modo de instalación

Este documento asume que el árbol de `graph/` ya fue generado por `graph-ia`. Ver `sessions/tasks.md` para el estado de instalación de este proyecto puntual (greenfield o brownfield, con o sin reconciliación de historial).
