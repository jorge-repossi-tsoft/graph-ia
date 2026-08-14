# Enforcement — por qué esta carpeta existe

> **Nota (instalación vía plugin):** si GRAPH se instaló con el plugin
> `graph-ia` de Claude Code, los tres hooks de abajo se registran solos al
> instalar el plugin — no hace falta tocar `.claude/settings.json` a mano ni
> copiar los `.sh` acá. Las instrucciones de registro manual que siguen
> abajo quedan como referencia para integrar el mismo contrato con otra
> herramienta que no soporte plugins.

`circuit-breaker.yml` declara la intención (iteration cap, umbral de estancamiento,
quién puede editar el archivo). Pero un YAML no bloquea nada por sí solo — necesita
una capa externa que efectivamente lo haga cumplir, o el circuit breaker es una
promesa que el propio agente se hace a sí mismo, que es justo el anti-patrón que
GRAPH.md describe.

## El límite honesto sobre A (Agnostic)

El resto de GRAPH es agnóstico de herramienta por diseño. **Esta pieza puntual no
puede serlo del todo**: bloquear una acción antes de que ocurra requiere que la
herramienta que ejecuta al agente exponga algún mecanismo de intercepción (hooks,
middlewares, wrappers de proceso). No todas las herramientas lo exponen igual, y
algunas no lo exponen en absoluto.

Por eso `enforcement/` funciona como carpeta de **adaptadores**: un archivo por
herramienta, cada uno implementando el mismo contrato (leer `circuit-breaker.yml`,
contar iteraciones, bloquear si se excede, escribir el evento en
`history/circuit-breaker-events.jsonl`), pero con el mecanismo específico de esa
herramienta. Si tu herramienta no tiene un adaptador acá todavía, el circuit
breaker queda en estado "declarativo únicamente" — hay que asumir eso como un gap
real, no ignorarlo.

## Adaptadores incluidos

- `claude-code-hook.sh` (evento `PreToolUse`) — bloquea antes de que la
  herramienta se ejecute, con `exit 2`. Cuenta iteraciones y protege
  `circuit-breaker.yml`/`policy.yml` de edición sin gate.
- `session-reset-hook.sh` (evento `UserPromptSubmit`) — resetea el contador
  al inicio de cada turno del humano, **salvo que el breaker esté disparado**
  (marcador `.circuit-breaker-tripped`), en cuyo caso no resetea nada hasta
  que un humano lo revise a mano.
- `stagnation-hook.sh` (evento `PostToolUse`) — implementa `no_progress_detection`
  usando el hash del diff de git como señal universal de progreso: si el
  working tree no cambió en N acciones consecutivas (`no_progress_threshold`
  en `circuit-breaker.yml`), dispara el mismo mecanismo de corte que
  iteration_cap. Es agnóstica de stack porque usa git, no una suite de tests
  ni logs de error específicos de una herramienta — cualquier proyecto
  versionado en git puede usar esta señal tal cual. Si tu proyecto tiene una
  suite de tests rápida, se puede extender con una señal adicional de
  `tests_passing_delta`, pero eso ya no sería agnóstico y no viene por
  default.

Los tres hooks van juntos — registrar solo uno o dos deja partes de Circuit
Breaker sin aplicación real, aunque `circuit-breaker.yml` los declare.

## Cómo agregar un adaptador para otra herramienta

Cualquier adaptador nuevo tiene que cumplir el mismo contrato mínimo:

1. Interceptar la acción *antes* de que se ejecute (no después — post-hoc no es
   circuit breaker, es log).
2. Leer `iteration_cap.max_iterations` y `stagnation_detection` de
   `circuit-breaker.yml`.
3. Mantener un contador de estado que sobreviva entre llamadas (un archivo, no
   una variable en memoria del propio agente — si el estado vive en el agente,
   el agente puede "olvidarlo").
4. **Resetear el contador por tramo autónomo (ej. por turno de usuario), no
   por sesión completa** — de lo contrario, acciones de solo lectura o de
   supervisión activa del humano cuentan contra el mismo límite pensado para
   frenar loops sin nadie mirando, y el cap se agota con trabajo normal.
5. Excluir del conteo las acciones de severidad `low` en `gates/policy.yml`
   (leer, consultar el grafo) — el cap existe para acciones que cambian
   estado, no para que el agente consulte antes de actuar (eso es G, y
   penalizarlo desalienta justo lo que G pide).
6. Al disparar el corte: bloquear la acción, escribir el evento en
   `history/circuit-breaker-events.jsonl`, dejar un marcador persistente de
   "disparado" que sobreviva resets normales, y no reiniciar solo (ver
   `restart_policy` en `circuit-breaker.yml`).
7. Bloquear también la edición de `circuit-breaker.yml` y `policy.yml` salvo que
   venga acompañada de una aprobación de severidad `high` en `gates/approved/`.

Si tu herramienta no soporta interceptar acciones antes de que ocurran, no hay
forma de cumplir Circuit Breaker de verdad con esa herramienta — documentalo como
limitación conocida en `sessions/progress.md`, no lo des por resuelto.
