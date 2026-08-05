#!/usr/bin/env bash
# stagnation-hook.sh — implementa no_progress_detection de circuit-breaker.yml
# via evento PostToolUse (corre DESPUÉS de cada acción que cambia estado).
#
# Señal de progreso elegida: hash del diff de git. Es la única señal que es
# universal entre stacks — no depende de si el proyecto tiene tests, de qué
# lenguaje usa, ni de parsear salidas de error específicas de una herramienta.
# Si el working tree no cambió entre una acción y la siguiente, no hubo
# progreso real, sin importar qué "intentó" hacer el agente.
#
# Registrar en .claude/settings.json:
#
#   {
#     "hooks": {
#       "PostToolUse": [
#         {
#           "matcher": "Edit|MultiEdit|Write|NotebookEdit|Bash",
#           "hooks": [
#             { "type": "command", "command": "bash .agents/graph/enforcement/stagnation-hook.sh" }
#           ]
#         }
#       ]
#     }
#   }
#
# Limitación conocida: esto detecta "el código no cambió", no "el agente está
# repitiendo el mismo error". Si tu proyecto tiene una suite de tests rápida,
# podés extender este script agregando una señal de tests_passing_delta
# (correr los tests, comparar cuántos pasan contra la corrida anterior) — eso
# es más preciso pero ya no es agnóstico de stack, por eso no viene por
# default acá.

set -euo pipefail

AGENTS_DIR=".agents"
CB_CONFIG="$AGENTS_DIR/graph/circuit-breaker.yml"
STATE_FILE="$AGENTS_DIR/graph/history/.circuit-breaker-state.json"
TRIPPED_MARKER="$AGENTS_DIR/graph/history/.circuit-breaker-tripped"
AUDIT_LOG="$AGENTS_DIR/graph/history/circuit-breaker-events.jsonl"

# Si no es un repo git, esta señal no aplica — salir sin bloquear nada.
if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
  exit 0
fi

# Si ya está disparado, no hacer nada más (el PreToolUse ya está bloqueando).
if [[ -e "$TRIPPED_MARKER" ]]; then
  exit 0
fi

if [[ ! -f "$CB_CONFIG" ]]; then
  exit 0
fi

STAGNATION_THRESHOLD="$(grep "no_progress_threshold:" "$CB_CONFIG" | head -1 | grep -o '[0-9]\+' || true)"
STAGNATION_THRESHOLD="${STAGNATION_THRESHOLD:-3}"

mkdir -p "$(dirname "$STATE_FILE")"
if [[ ! -f "$STATE_FILE" ]]; then
  echo '{"iteration_count": 0, "consecutive_no_progress": 0, "last_state_hash": ""}' > "$STATE_FILE"
fi

# Hash del estado actual: diff completo (staged + unstaged) contra HEAD.
CURRENT_HASH="$(git diff HEAD 2>/dev/null | git hash-object --stdin 2>/dev/null || echo "no-git-diff")"

LAST_HASH="$(grep -o '"last_state_hash"[[:space:]]*:[[:space:]]*"[^"]*"' "$STATE_FILE" | sed 's/.*"\([^"]*\)"$/\1/' || true)"
CONSECUTIVE="$(grep -o '"consecutive_no_progress"[[:space:]]*:[[:space:]]*[0-9]\+' "$STATE_FILE" | grep -o '[0-9]\+' || true)"
CONSECUTIVE="${CONSECUTIVE:-0}"
ITER_COUNT="$(grep -o '"iteration_count"[[:space:]]*:[[:space:]]*[0-9]\+' "$STATE_FILE" | grep -o '[0-9]\+' || true)"
ITER_COUNT="${ITER_COUNT:-0}"

if [[ -n "$LAST_HASH" && "$CURRENT_HASH" == "$LAST_HASH" ]]; then
  NEW_CONSECUTIVE=$((CONSECUTIVE + 1))
else
  NEW_CONSECUTIVE=0
fi

if [[ "$NEW_CONSECUTIVE" -ge "$STAGNATION_THRESHOLD" ]]; then
  TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  mkdir -p "$(dirname "$AUDIT_LOG")"
  echo "{\"timestamp\": \"$TIMESTAMP\", \"trigger_reason\": \"stagnation\", \"consecutive_no_progress\": $NEW_CONSECUTIVE, \"signal\": \"git_diff_hash_unchanged\"}" >> "$AUDIT_LOG"
  echo "{\"tripped_at\": \"$TIMESTAMP\", \"reason\": \"stagnation\", \"consecutive_no_progress\": $NEW_CONSECUTIVE}" > "$TRIPPED_MARKER"
  echo "Circuit breaker disparado por estancamiento: el diff de git no cambió en $NEW_CONSECUTIVE acciones consecutivas (umbral: $STAGNATION_THRESHOLD). Corte registrado. Requiere revisión humana." >&2
  # No podemos bloquear la acción que ya ocurrió (esto es PostToolUse), pero
  # el marker deja que el próximo PreToolUse bloquee la siguiente.
fi

echo "{\"iteration_count\": $ITER_COUNT, \"consecutive_no_progress\": $NEW_CONSECUTIVE, \"last_state_hash\": \"$CURRENT_HASH\"}" > "$STATE_FILE"

exit 0
