#!/usr/bin/env bash
# cli-install-hook.sh — provisiona el comando `graph` en el PATH del usuario
# la primera vez que hace falta, sin pasos manuales (evento UserPromptSubmit).
#
# Por qué existe: bin/graph(.cmd/.ps1) vive en el checkout del plugin, pero
# esa carpeta no está en el PATH del usuario por default. Sin este hook, cada
# persona que instala el plugin (Claude Code o Codex) tiene que agregar
# `bin/` al PATH a mano antes de poder usar `graph` desde cualquier lado —
# eso no es aceptable para un CLI que se instala solo. Este hook automatiza
# ese último paso, cubriendo TODOS los shells comunes en los que puede correr
# una terminal integrada de VS Code (o una externa): agrega la carpeta
# `bin/` de ESTE checkout del plugin al PATH persistente del usuario, y
# además al profile de cada shell detectado. No requiere permisos de
# administrador — todo queda a nivel de usuario.
#
# Por qué agregar bin/ del plugin en vez de copiar los shims a otro lado:
# graph.ps1 y bin/graph resuelven template-ia.py con una ruta relativa a su
# propia ubicación (../scripts/template-ia.py) como uno de los candidatos.
# Copiar los archivos a una carpeta separada (ej. ~/.template-ia/bin) rompe
# esa ruta relativa y además crea una segunda copia que se desactualiza en
# cuanto el plugin se actualiza. Apuntar el PATH directo a $PLUGIN_ROOT/bin
# evita ambos problemas: una sola fuente de verdad, siempre al día.
#
# Por qué también tocamos el profile de cada shell, no solo el PATH de
# usuario (registro de Windows / entorno de Unix): un editor como VS Code
# cachea el entorno con el que arrancó su PROPIO proceso. Si el hook corre
# después de abrir el editor, ninguna pestaña de terminal integrada ve el
# PATH nuevo por más que el registro/entorno ya esté actualizado — hasta
# que se cierra el editor del todo y se vuelve a abrir. Pero cada pestaña
# NUEVA de terminal lanza su propio proceso de shell, y ESE proceso sí lee
# su profile (.bashrc, $PROFILE) al arrancar — ahí es donde inyectamos el
# PATH, para que una pestaña nueva alcance sin reiniciar el editor entero.
#
# Por qué no setx en Windows: setx trunca el valor a 1024 caracteres y puede
# corromper un PATH de usuario ya largo (bug conocido de Windows, no de este
# script). [Environment]::SetEnvironmentVariable (via bin/ensure-path.ps1)
# no tiene ese límite.
#
# Limitación conocida, no evitable desde acá: una terminal/pestaña YA
# abierta ANTES de que este hook corra no ve el cambio. Hace falta una
# pestaña nueva (alcanza, no requiere reiniciar el editor completo salvo
# que el profile real de esa terminal sea uno distinto al que tocamos).
#
# Se registra en el mismo evento que session-reset-hook.sh (UserPromptSubmit)
# porque corre en cada turno tanto en Claude Code como en Codex — el chequeo
# de "¿`graph` ya existe?" es la primera línea y es barato, así que el costo
# en los turnos posteriores (ya instalado) es despreciable.

set -uo pipefail

# Caso ya-instalado: salir rápido, no hay nada que hacer.
if command -v graph >/dev/null 2>&1; then
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." 2>/dev/null && pwd)"
BIN_SRC="$PLUGIN_ROOT/bin"

# Sin bin/ (checkout roto o parcial) no hay nada que ofrecer al PATH.
[[ -d "$BIN_SRC" ]] || exit 0
{ [[ -f "$BIN_SRC/graph" ]] || [[ -f "$BIN_SRC/graph.cmd" ]]; } || exit 0

# add_path_to_rc RC_FILE DIR — agrega "export PATH=..." a RC_FILE si DIR
# todavía no aparece ahí. Idempotente. Común a Git Bash (Windows) y a
# Linux/macOS, así que vive una sola vez.
add_path_to_rc() {
  local rc_file="$1" dir="$2"
  if [[ -f "$rc_file" ]] && grep -qF "$dir" "$rc_file" 2>/dev/null; then
    return 1
  fi
  {
    echo ""
    echo "# template-ia: agregado automáticamente para el comando 'graph'"
    echo "export PATH=\"$dir:\$PATH\""
  } >> "$rc_file" 2>/dev/null
}

NOTIFY=""

case "$(uname -s 2>/dev/null || echo unknown)" in
  MINGW*|MSYS*|CYGWIN*)
    # 1. PATH de usuario (registro HKCU) + profile de PowerShell / pwsh —
    #    delegado a bin/ensure-path.ps1 (ver ese archivo para el detalle).
    BIN_SRC_WIN="$(cygpath -w "$BIN_SRC" 2>/dev/null || echo "$BIN_SRC")"
    HELPER_WIN="$(cygpath -w "$BIN_SRC/ensure-path.ps1" 2>/dev/null || echo "$BIN_SRC/ensure-path.ps1")"

    for ps_exe in powershell.exe pwsh.exe; do
      if command -v "$ps_exe" >/dev/null 2>&1; then
        RESULT="$("$ps_exe" -NoProfile -ExecutionPolicy Bypass -File "$HELPER_WIN" -TargetDir "$BIN_SRC_WIN" 2>/dev/null | tr -d '\r')"
        if [[ "$RESULT" == *PATH_UPDATED* || "$RESULT" == *PROFILE_UPDATED* ]]; then
          NOTIFY=1
        fi
      fi
    done

    # 2. .bashrc de Git Bash — para que una pestaña NUEVA de Git Bash en
    #    VS Code (o una consola externa) lo tenga sin reiniciar nada.
    if add_path_to_rc "$HOME/.bashrc" "$BIN_SRC"; then
      NOTIFY=1
    fi

    if [[ -n "$NOTIFY" ]]; then
      echo "GRAPH: agregué el comando 'graph' a tu PATH (usuario, PowerShell/pwsh y Git Bash) — no hace falta que hagas nada más. Alcanza con abrir una terminal o pestaña nueva; no aplica a las que ya estaban abiertas." >&2
    fi
    ;;
  *)
    # Unix (Linux/macOS): profile del shell activo, apuntando a bin/ del
    # checkout del plugin (no se copia nada).
    RC_FILE=""
    case "${SHELL:-}" in
      */zsh) RC_FILE="$HOME/.zshrc" ;;
      */bash) RC_FILE="$HOME/.bashrc" ;;
      *) RC_FILE="$HOME/.profile" ;;
    esac

    if [[ -n "$RC_FILE" ]] && add_path_to_rc "$RC_FILE" "$BIN_SRC"; then
      echo "GRAPH: agregué el comando 'graph' a tu PATH en $RC_FILE — no hace falta que hagas nada más. Abrí una terminal nueva, o corré 'source $RC_FILE', para poder usarlo." >&2
    fi
    ;;
esac

exit 0
