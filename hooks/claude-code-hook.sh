#!/usr/bin/env bash
# claude-code-hook.sh — adaptador de enforcement real para Claude Code.
#
# IMPORTANTE: este hook necesita registrarse JUNTO CON session-reset-hook.sh
# (ver ese archivo). Sin el reset por turno, el contador se acumula durante
# TODA la sesión (incluyendo turnos donde vos estás presente supervisando),
# y termina bloqueando trabajo normal en vez de cortar loops autónomos reales.
# El iteration_cap tiene sentido para "cuántas acciones seguidas sin que un
# humano vuelva a intervenir", no para "cuántas herramientas se usaron hoy".
#
# Registrar en .claude/settings.json:
#
#   {
#     "hooks": {
#       "UserPromptSubmit": [
#         {
#           "hooks": [
#             { "type": "command", "command": "bash .agents/graph/enforcement/session-reset-hook.sh" }
#           ]
#         }
#       ],
#       "PreToolUse": [
#         {
#           "matcher": "Edit|MultiEdit|Write|NotebookEdit|Bash",
#           "hooks": [
#             { "type": "command", "command": "bash .agents/graph/enforcement/claude-code-hook.sh" }
#           ]
#         }
#       ]
#     }
#   }
#
# El matcher NO incluye Read, Grep, Glob, WebFetch, WebSearch ni Task — esas
# son acciones de severidad "low" en gates/policy.yml (consultar el grafo,
# leer código) y contarlas contra el iteration_cap penalizaría exactamente
# el comportamiento que G pide (consultar antes de actuar). Bash queda
# incluido pese a que también sirve para comandos de solo lectura (ls, cat) —
# es un trade-off consciente: separar "Bash de lectura" de "Bash que cambia
# estado" requeriría parsear el comando, que queda fuera de este adaptador.
#
# Este hook recibe JSON por stdin en cada llamada a herramienta, ANTES de que
# se ejecute. Exit 2 = bloqueado. Exit 0 = permitido. Esto es aplicación real:
# no depende de que el modelo decida respetar la regla (ver enforcement/README.md).

set -euo pipefail

AGENTS_DIR=".agents"
CB_CONFIG="$AGENTS_DIR/graph/circuit-breaker.yml"
STATE_FILE="$AGENTS_DIR/graph/history/.circuit-breaker-state.json"
TRIPPED_MARKER="$AGENTS_DIR/graph/history/.circuit-breaker-tripped"
AUDIT_LOG="$AGENTS_DIR/graph/history/circuit-breaker-events.jsonl"

# Si el breaker ya está disparado y esperando revisión humana, bloquear TODO
# sin importar el contador — un corte no se limpia solo con el siguiente turno.
# Se limpia solo si un humano borra $TRIPPED_MARKER a mano (o vía gate aprobado).
if [[ -e "$TRIPPED_MARKER" ]]; then
  echo "Bloqueado: el circuit breaker sigue disparado desde un corte previo (ver $TRIPPED_MARKER). Requiere revisión humana antes de continuar — no se resetea solo entre turnos." >&2
  exit 2
fi

# Leer input de la herramienta (JSON por stdin)
INPUT="$(cat)"
TOOL_NAME="$(echo "$INPUT" | grep -o '"tool_name"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/' || echo "unknown")"
FILE_PATH="$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/' || echo "")"

# --- 1. Protección de los archivos de gobernanza (nadie edita circuit-breaker.yml
#        ni policy.yml sin pasar por un gate humano de severidad "high") ---
if [[ "$FILE_PATH" == *"circuit-breaker.yml"* || "$FILE_PATH" == *"gates/policy.yml"* ]]; then
  # BUG HISTÓRICO (encontrado por test real, no dar por sentado que esto es trivial):
  # `grep -c` sale con status 1 cuando cuenta 0 matches, aunque imprime "0".
  # Combinado con `|| echo "0"`, el fallback se disparaba SIEMPRE que había 0
  # aprobaciones, agregando una segunda línea "0" — el resultado quedaba "0\n0"
  # en vez de un entero. `[[ "0\n0" -eq 0 ]]` falla como comparación inválida,
  # y como las condiciones de `if` están exentas de `set -e`, bash trataba eso
  # como "falso" sin abortar — el bloque de bloqueo nunca se ejecutaba. Esto es
  # fail-open (deja pasar) en un mecanismo que tiene que ser fail-closed
  # (bloquear por default ante cualquier duda). El fix: `|| true` en vez de
  # `|| echo "0"` — así el fallback nunca agrega una línea extra al resultado.
  APPROVED_EDIT="$(ls "$AGENTS_DIR/graph/gates/approved/" 2>/dev/null | grep -c "config-edit" || true)"
  APPROVED_EDIT="${APPROVED_EDIT:-0}"
  if [[ "$APPROVED_EDIT" -eq 0 ]]; then
    echo "Bloqueado: editar $FILE_PATH requiere una aprobación de severidad 'high' en gates/approved/. Ver policy.yml." >&2
    exit 2
  fi
fi

# --- 2. Iteration cap ---
if [[ ! -f "$CB_CONFIG" ]]; then
  exit 0   # no hay config, no hay nada que aplicar
fi

MAX_ITER=$(grep "max_iterations:" "$CB_CONFIG" | head -1 | grep -o '[0-9]\+' || echo "25")
STAGNATION_THRESHOLD=$(grep "no_progress_threshold:" "$CB_CONFIG" | head -1 | grep -o '[0-9]\+' || echo "3")

mkdir -p "$(dirname "$STATE_FILE")"
if [[ ! -f "$STATE_FILE" ]]; then
  echo '{"iteration_count": 0, "consecutive_no_progress": 0, "last_state_hash": ""}' > "$STATE_FILE"
fi

CURRENT_COUNT=$(grep -o '"iteration_count"[[:space:]]*:[[:space:]]*[0-9]\+' "$STATE_FILE" | grep -o '[0-9]\+' || echo "0")
NEW_COUNT=$((CURRENT_COUNT + 1))

if [[ "$NEW_COUNT" -gt "$MAX_ITER" ]]; then
  TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  mkdir -p "$(dirname "$AUDIT_LOG")"
  echo "{\"timestamp\": \"$TIMESTAMP\", \"trigger_reason\": \"iteration_cap\", \"iterations_elapsed\": $NEW_COUNT, \"tool_attempted\": \"$TOOL_NAME\"}" >> "$AUDIT_LOG"
  echo "{\"tripped_at\": \"$TIMESTAMP\", \"reason\": \"iteration_cap\", \"iterations_elapsed\": $NEW_COUNT}" > "$TRIPPED_MARKER"
  echo "Bloqueado: se alcanzó el iteration_cap ($MAX_ITER) definido en circuit-breaker.yml. Corte registrado en history/circuit-breaker-events.jsonl y marcado en $TRIPPED_MARKER. Requiere revisión humana antes de continuar (restart_policy.auto_restart: false) — un humano debe borrar ese archivo a mano para retomar." >&2
  exit 2
fi

# Actualizar contador SOLO del campo que este script posee (iteration_count).
# consecutive_no_progress y last_state_hash pertenecen a stagnation-hook.sh
# (PostToolUse) — pisarlos acá con 0/"" borra su trabajo en cada llamada,
# porque este hook corre ANTES (PreToolUse) y stagnation-hook.sh corre
# DESPUÉS (PostToolUse) de la MISMA acción. Si este script resetea esos
# campos antes de que stagnation-hook.sh los lea en la próxima vuelta, la
# comparación de hash siempre ve "" como valor previo y nunca detecta
# estancamiento real — el contador de progreso queda permanentemente inerte.
# Por eso: leer los valores actuales primero, y escribir solo lo propio.
CURRENT_NO_PROGRESS=$(grep -o '"consecutive_no_progress"[[:space:]]*:[[:space:]]*[0-9]\+' "$STATE_FILE" | grep -o '[0-9]\+' || true)
CURRENT_NO_PROGRESS="${CURRENT_NO_PROGRESS:-0}"
CURRENT_HASH=$(grep -o '"last_state_hash"[[:space:]]*:[[:space:]]*"[^"]*"' "$STATE_FILE" | sed 's/.*"\([^"]*\)"$/\1/' || true)

echo "{\"iteration_count\": $NEW_COUNT, \"consecutive_no_progress\": $CURRENT_NO_PROGRESS, \"last_state_hash\": \"$CURRENT_HASH\"}" > "$STATE_FILE"

exit 0

# NOTA sobre stagnation_detection: la implementa stagnation-hook.sh (evento
# PostToolUse) usando el hash del diff de git como señal de progreso. Este
# script (claude-code-hook.sh) SOLO posee iteration_count — nunca debe escribir
# consecutive_no_progress ni last_state_hash con valores propios, son de
# stagnation-hook.sh (ver el fix arriba, encontrado en integración real).
