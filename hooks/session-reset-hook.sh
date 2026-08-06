#!/usr/bin/env bash
# session-reset-hook.sh — resetea el contador de circuit-breaker en cada turno
# nuevo del humano (evento UserPromptSubmit).
#
# Por qué existe: sin esto, claude-code-hook.sh cuenta llamadas a herramienta
# acumuladas de TODA la sesión, incluyendo turnos donde el humano está
# presente y activamente supervisando — eso no es lo que iteration_cap debería
# medir. El circuit breaker existe para cortar un TRAMO AUTÓNOMO sin que nadie
# esté mirando (ej. el agente encadenando 25+ acciones seguidas sin volver a
# preguntar). Resetear por turno hace que el cap mida exactamente eso: cuántas
# acciones seguidas hace el agente DENTRO de un mismo turno, no en la sesión
# completa.
#
# Registrar en .claude/settings.json bajo el evento UserPromptSubmit
# (ver el comentario de registro en claude-code-hook.sh).

set -euo pipefail

AGENTS_DIR=".agents"
STATE_FILE="$AGENTS_DIR/graph/history/.circuit-breaker-state.json"
TRIPPED_MARKER="$AGENTS_DIR/graph/history/.circuit-breaker-tripped"

# Si el breaker está disparado, NO resetear el contador — un corte real
# requiere que un humano lo revise y borre $TRIPPED_MARKER a mano. Si este
# script reseteara el contador en cada turno nuevo sin chequear esto, el
# corte se "auto-curaría" solo, y el circuit breaker dejaría de servir.
if [[ -e "$TRIPPED_MARKER" ]]; then
  echo "Circuit breaker sigue disparado — no se resetea el contador. Revisar $TRIPPED_MARKER y $AGENTS_DIR/graph/history/circuit-breaker-events.jsonl." >&2
  exit 0
fi

mkdir -p "$(dirname "$STATE_FILE")"
echo '{"iteration_count": 0, "consecutive_no_progress": 0, "last_state_hash": ""}' > "$STATE_FILE"

exit 0
