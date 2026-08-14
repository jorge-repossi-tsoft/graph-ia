#!/usr/bin/env bash
# install.sh — instalador universal de GRAPH.
#
# No depende de Claude Code, Codex CLI, Cursor ni de ningún otro agente en
# particular — es un script de bash + python3 que corrés vos, una vez, en
# la raíz de tu proyecto. Después, CUALQUIER agente que lea AGENTS.md (que
# es un estándar abierto, no de una sola empresa) va a encontrar el
# contexto igual. Esto es lo que hace posible el principio A (Agnostic) de
# verdad: no hay plugin de por medio que ate esto a una sola herramienta.
#
# Uso:
#   bash install.sh --mode=greenfield
#   bash install.sh --mode=brownfield [--migrate]
#
# Nota sobre el circuit breaker: los 3 hooks de enforcement (bloqueo real
# de acciones) SÍ dependen de que tu agente tenga un sistema de hooks
# compatible (hoy, eso es Claude Code). Si tu agente no tiene eso, GRAPH
# igual te da el resto del patrón (grounding, gates, persistencia,
# jerarquía) — el freno de mano queda como configuración documentada en
# circuit-breaker.yml, para cuando tu herramienta lo soporte.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(pwd)"
MODE=""
MIGRATE=false
UPDATE=false
ALLOW_SELF_INSTALL="${GRAPH_IA_ALLOW_SELF_INSTALL:-0}"

SCRIPT_DIR_REAL="$(cd "$SCRIPT_DIR" && pwd -P)"
REPO_ROOT_REAL="$(cd "$REPO_ROOT" && pwd -P)"

if [ "$ALLOW_SELF_INSTALL" != "1" ] && [ "$SCRIPT_DIR_REAL" = "$REPO_ROOT_REAL" ]; then
  echo "Este instalador no debe correrse sobre el repo fuente del plugin." >&2
  echo "Parate en el proyecto destino y volvelo a ejecutar ahí, o exportá GRAPH_IA_ALLOW_SELF_INSTALL=1 si realmente querés probar el self-install." >&2
  exit 1
fi

for arg in "$@"; do
  case "$arg" in
    --mode=greenfield) MODE="greenfield" ;;
    --mode=brownfield) MODE="brownfield" ;;
    --migrate) MIGRATE=true ;;
    --update) UPDATE=true ;;
    *)
      echo "Argumento desconocido: $arg" >&2
      echo "Uso: install.sh --mode=greenfield|brownfield [--migrate] | install.sh --update" >&2
      exit 1
      ;;
  esac
done

# --update corre solo, sobre un proyecto que ya tiene GRAPH instalado: no
# toca la instalación, solo resincroniza la documentación genérica del
# patrón y el bloque administrado de AGENTS.md/CLAUDE.md con la versión
# actual de este plugin (delegado a graph-ia.py, que es la única fuente
# de verdad de esa lógica — así no hay dos implementaciones divergiendo).
if [ "$UPDATE" = true ]; then
  if [ -n "$MODE" ]; then
    echo "--update no se combina con --mode. Corré uno u otro." >&2
    exit 1
  fi
  if ! [ -d "$REPO_ROOT/.agents/graph" ]; then
    echo "No hay .agents/graph/ en este repo — corré install.sh --mode=... primero." >&2
    exit 1
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    echo "No hay python3 disponible — --update depende de scripts/graph-ia.py para" >&2
    echo "resincronizar AGENTS.md/CLAUDE.md y la documentación del patrón sin duplicar" >&2
    echo "ni pisar contenido propio. Instalá Python 3 y volvé a correr install.sh --update." >&2
    exit 1
  fi
  python3 "$SCRIPT_DIR/scripts/graph-ia.py" "$REPO_ROOT" --update-docs
  exit $?
fi

if [ -z "$MODE" ]; then
  echo "Falta --mode=greenfield o --mode=brownfield. No lo adivino, elegilo vos." >&2
  exit 1
fi

echo "== GRAPH install — modo: $MODE (migrate: $MIGRATE) =="

# --- safe_copy: nunca pisa un archivo que ya existe ---
safe_copy() {
  local src="$1" dst="$2"
  if [ -e "$dst" ]; then
    echo "  [skip] ya existe: $dst"
  else
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    echo "  [ok]   creado: $dst"
  fi
}

# --- Paso 0: migración opcional ---
if [ "$MIGRATE" = true ]; then
  echo "-- Paso 0: migración de .agents/ previo --"
  today="$(date +%Y-%m-%d)"
  for pair in "progress.md:.agents/graph/sessions/progress.md" \
              "tasks.md:.agents/graph/sessions/tasks.md" \
              "system.md:.agents/graph/legacy-system.md"; do
    old_name="${pair%%:*}"
    new_path="${pair##*:}"
    old_path=".agents/$old_name"
    if [ -f "$old_path" ]; then
      if [ -e "$new_path" ]; then
        echo "  [skip] $old_path y $new_path existen los dos — no se toca ninguno, resolvelo a mano."
      else
        mkdir -p "$(dirname "$new_path")"
        {
          echo "<!-- Migrado automáticamente desde $old_path el $today -->"
          echo
          cat "$old_path"
        } > "$new_path"
        rm "$old_path"
        echo "  [ok]   migrado: $old_path -> $new_path"
      fi
    fi
  done
fi

# --- Paso 1: estructura de carpetas (siempre segura) ---
echo "-- Paso 1: estructura de carpetas --"
mkdir -p .agents/graph/knowledge/nodes
mkdir -p .agents/graph/knowledge/communities
mkdir -p .agents/graph/history
mkdir -p .agents/graph/gates/pending
mkdir -p .agents/graph/gates/approved
mkdir -p .agents/graph/sessions
mkdir -p .agents/graph/enforcement
mkdir -p .agents/roles
mkdir -p .agents/skills

# --- Paso 2: knowledge/index.json + indexado real si es brownfield ---
echo "-- Paso 2: knowledge/index.json --"
INDEX_FILE=".agents/graph/knowledge/index.json"
if [ -e "$INDEX_FILE" ]; then
  echo "  [skip] ya existe: $INDEX_FILE"
else
  if [ "$MODE" = "greenfield" ]; then
    cat > "$INDEX_FILE" << 'EOF'
{"status": "empty", "reason": "greenfield — se puebla en paralelo al código", "last_indexed": null}
EOF
    echo "  [ok]   greenfield: index.json vacío"
  else
    echo '{"status": "indexing", "reason": "brownfield — indexación inicial en curso", "last_indexed": null}' > "$INDEX_FILE"
    if command -v python3 >/dev/null 2>&1; then
      echo "  corriendo el indexador propio (sin dependencias de terceros)..."
      python3 "$SCRIPT_DIR/scripts/build-graph.py" "$REPO_ROOT"
      echo "  [ok]   indexado real generado en knowledge/nodes/ y knowledge/communities/"
    else
      echo "  [WARN] no hay python3 disponible — el indexado real NO se pudo correr."
      echo "         knowledge/index.json queda en estado 'indexing' (degradado)."
      echo "         Instalá Python 3 y corré: python3 scripts/build-graph.py . para completarlo."
    fi
  fi
fi

# --- Paso 3: copiar archivos base ---
echo "-- Paso 3: archivos base --"
safe_copy "$SCRIPT_DIR/templates/graph/GRAPH.md" ".agents/graph/GRAPH.md"
safe_copy "$SCRIPT_DIR/templates/graph/README.md" ".agents/graph/README.md"
safe_copy "$SCRIPT_DIR/templates/graph/circuit-breaker.yml" ".agents/graph/circuit-breaker.yml"
safe_copy "$SCRIPT_DIR/templates/graph/gates/policy.yml" ".agents/graph/gates/policy.yml"
safe_copy "$SCRIPT_DIR/templates/graph/enforcement/README.md" ".agents/graph/enforcement/README.md"
safe_copy "$SCRIPT_DIR/templates/roles/registry.yml" ".agents/roles/registry.yml"
safe_copy "$SCRIPT_DIR/templates/roles/planner.md" ".agents/roles/planner.md"
safe_copy "$SCRIPT_DIR/templates/roles/executor.md" ".agents/roles/executor.md"
safe_copy "$SCRIPT_DIR/templates/roles/reviewer.md" ".agents/roles/reviewer.md"

if [ ! -f ".agents/graph/sessions/progress.md" ]; then
  safe_copy "$SCRIPT_DIR/templates/graph/sessions/progress.md" ".agents/graph/sessions/progress.md"
fi
if [ ! -f ".agents/graph/sessions/tasks.md" ]; then
  safe_copy "$SCRIPT_DIR/templates/graph/sessions/tasks.md" ".agents/graph/sessions/tasks.md"
  # Paso 5 (adelantado): estampar el modo real detectado, solo si lo acabamos de crear
  if [ -f ".agents/graph/sessions/tasks.md" ]; then
    sed -i.bak "s/Modo detectado: greenfield | brownfield/Modo detectado: $MODE/" ".agents/graph/sessions/tasks.md" 2>/dev/null || true
    rm -f ".agents/graph/sessions/tasks.md.bak"
  fi
fi

# --- Paso 4: bridge AGENTS.md / CLAUDE.md en la raíz del repo ---
echo "-- Paso 4: bridge AGENTS.md / CLAUDE.md --"
# La lógica real (bloque administrado con marcador de inicio y cierre,
# reemplazo idempotente, prefijo .agents/ según dónde viva el archivo) vive
# en una sola fuente de verdad: scripts/graph-ia.py. Delegamos ahí en vez
# de reimplementar el mismo bloque en bash, para que no puedan desincronizarse
# dos versiones del texto del bridge.
if command -v python3 >/dev/null 2>&1; then
  python3 "$SCRIPT_DIR/scripts/graph-ia.py" "$REPO_ROOT" --update-docs
else
  echo "  [WARN] no hay python3 — usando un bridge mínimo degradado (sin los"
  echo "         comandos #task/#run/#done/#skip/#note documentados)."
  echo "         Instalá Python 3 y corré: python3 scripts/graph-ia.py . --update-docs"
  echo "         para completarlo con el bridge real del plugin."
  place_bridge() {
    local filename="$1"
    local root_path="./$filename"
    local nested_path=".agents/$filename"
    local target=""

    if [ -f "$root_path" ]; then
      target="$root_path"
    elif [ -f "$nested_path" ]; then
      target="$nested_path"
    fi

    if [ -n "$target" ]; then
      if grep -q "graph-ia:bridge-block" "$target" 2>/dev/null; then
        echo "  [skip] $target ya tiene el bridge block"
      else
        {
          echo ""
          echo "<!-- graph-ia:bridge-block -->"
          echo "## GRAPH"
          echo "Este proyecto usa el patrón GRAPH. Antes de actuar de forma autónoma,"
          echo "consultá:"
          echo "- \`.agents/graph/GRAPH.md\` (spec completa)"
          echo "- \`.agents/roles/registry.yml\` (qué rol puede hacer qué)"
          echo "- \`.agents/graph/gates/policy.yml\` (qué necesita aprobación humana)"
          echo "- \`.agents/graph/sessions/progress.md\` y \`tasks.md\` (estado actual)"
          if [ -f ".agents/graph/legacy-system.md" ]; then
            echo "- \`.agents/graph/legacy-system.md\` (doc previa migrada, referencia)"
          fi
          echo "<!-- /graph-ia:bridge-block -->"
        } >> "$target"
        echo "  [ok]   bridge agregado a $target (contenido existente intacto)"
      fi
    else
      safe_copy "$SCRIPT_DIR/templates/$filename" "./$filename"
      # El fallback sin python3 no resuelve el placeholder de la línea de
      # legacy-system.md (eso requiere el script) — lo sacamos siempre para
      # no dejar el comentario crudo en el archivo.
      if [ -f "./$filename" ]; then
        grep -v "graph-ia:legacy-line" "./$filename" > "./$filename.tmp" && mv "./$filename.tmp" "./$filename"
      fi
    fi
  }
  place_bridge "AGENTS.md"
  place_bridge "CLAUDE.md"
fi

# --- Paso 5: comando `graph` en el PATH del usuario ---
# La lógica vive en hooks/cli-install-hook.sh (la misma que corren los
# plugins de Claude Code y Codex en cada turno) — así Cursor o cualquier
# instalación universal obtiene el CLI igual, sin pasos manuales.
echo "-- Paso 5: comando 'graph' en el PATH --"
if [ -f "$SCRIPT_DIR/hooks/cli-install-hook.sh" ]; then
  bash "$SCRIPT_DIR/hooks/cli-install-hook.sh" || true
  if command -v graph >/dev/null 2>&1; then
    echo "  [ok]   'graph' ya estaba disponible en el PATH"
  else
    echo "  [ok]   'graph' registrado — abrí una terminal nueva para usarlo"
  fi
else
  echo "  [skip] no encontré hooks/cli-install-hook.sh en el checkout"
fi

echo ""
echo "== Listo =="
echo "Estructura de GRAPH instalada en .agents/. Nada existente fue sobreescrito."
if [ "$MODE" = "brownfield" ] && ! command -v python3 >/dev/null 2>&1; then
  echo ""
  echo "⚠️  RECORDATORIO: el indexado real quedó pendiente (no había python3)."
  echo "   Sin esto, el principio Grounded no está satisfecho todavía."
fi
echo ""
echo "Sobre el circuit breaker (freno de mano):"
echo "- Si usás Claude Code: instalá también el plugin de este mismo repo"
echo "  (/plugin marketplace add + /plugin install) para que los 3 hooks"
echo "  bloqueen de verdad, no solo como config declarada."
echo "- Con otro agente: circuit-breaker.yml y gates/policy.yml quedan como"
echo "  contrato documentado — el agente lo respeta si lo lee vía AGENTS.md,"
echo "  pero el bloqueo forzado depende de que esa herramienta tenga hooks."
