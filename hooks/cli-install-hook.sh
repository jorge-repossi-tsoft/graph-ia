#!/usr/bin/env bash
# cli-install-hook.sh — provisiona el comando `graph` en el PATH del usuario
# la primera vez que hace falta, sin pasos manuales (evento UserPromptSubmit).
#
# Por qué existe: bin/graph(.cmd/.ps1) vive en el checkout del plugin, pero
# esa carpeta no está en el PATH del usuario por default. Sin este hook, cada
# persona que instala el plugin (Claude Code o Codex) tiene que agregar
# `bin/` al PATH a mano antes de poder usar `graph` desde cualquier lado —
# eso no es aceptable para un CLI que se instala solo. Este hook automatiza
# ese último paso: detecta si `graph` ya resuelve, y si no, agrega la
# carpeta `bin/` de ESTE checkout del plugin al PATH persistente del
# usuario. No requiere permisos de administrador — todo queda a nivel de
# usuario (registro HKCU en Windows vía [Environment]::SetEnvironmentVariable,
# rc del shell en Unix).
#
# Por qué agregar bin/ del plugin en vez de copiar los shims a otro lado:
# graph.ps1 y bin/graph resuelven template-ia.py con una ruta relativa a su
# propia ubicación (../scripts/template-ia.py) como uno de los candidatos.
# Copiar los archivos a una carpeta separada (ej. ~/.template-ia/bin) rompe
# esa ruta relativa y además crea una segunda copia que se desactualiza en
# cuanto el plugin se actualiza. Apuntar el PATH directo a $PLUGIN_ROOT/bin
# evita ambos problemas: una sola fuente de verdad, siempre al día.
#
# Por qué no setx en Windows: setx trunca el valor a 1024 caracteres y puede
# corromper un PATH de usuario ya largo (bug conocido de Windows, no de este
# script). [Environment]::SetEnvironmentVariable no tiene ese límite.
#
# Limitación conocida, no evitable desde acá: los cambios de PATH no aplican
# a terminales YA abiertas. La primera vez, quien instale el plugin necesita
# abrir una terminal nueva (o hacer `source` del rc, en Unix).
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

case "$(uname -s 2>/dev/null || echo unknown)" in
  MINGW*|MSYS*|CYGWIN*)
    # Windows vía git-bash: persistir el PATH de usuario con PowerShell
    # (ver nota sobre setx arriba).
    if command -v powershell.exe >/dev/null 2>&1; then
      BIN_SRC_WIN="$(cygpath -w "$BIN_SRC" 2>/dev/null || echo "$BIN_SRC")"
      # Escapar comillas simples para el literal de PowerShell ('' = ' literal),
      # por si la ruta del checkout contiene alguna.
      BIN_SRC_PS="${BIN_SRC_WIN//\'/\'\'}"
      RESULT="$(powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "
        \$target = '$BIN_SRC_PS'
        \$current = [Environment]::GetEnvironmentVariable('Path','User')
        \$parts = @()
        if (\$current) { \$parts = \$current -split ';' | Where-Object { \$_ -ne '' } }
        if (\$parts -notcontains \$target) {
          \$new = if (\$current) { \"\$current;\$target\" } else { \$target }
          [Environment]::SetEnvironmentVariable('Path', \$new, 'User')
          Write-Output 'UPDATED'
        } else {
          Write-Output 'ALREADY_OK'
        }
      " 2>/dev/null | tr -d '\r')"

      if [[ "$RESULT" == *UPDATED* ]]; then
        echo "GRAPH: agregué el comando 'graph' a tu PATH de usuario — no hace falta que hagas nada más. Abrí una terminal nueva para poder usarlo (los cambios de PATH no aplican a las que ya estaban abiertas)." >&2
      fi
    fi
    ;;
  *)
    # Unix (Linux/macOS): export en el rc del shell activo, apuntando a
    # bin/ del checkout del plugin (no se copia nada).
    RC_FILE=""
    case "${SHELL:-}" in
      */zsh) RC_FILE="$HOME/.zshrc" ;;
      */bash) RC_FILE="$HOME/.bashrc" ;;
      *) RC_FILE="$HOME/.profile" ;;
    esac

    if [[ -n "$RC_FILE" ]] && { [[ ! -f "$RC_FILE" ]] || ! grep -qF "$BIN_SRC" "$RC_FILE" 2>/dev/null; }; then
      {
        echo ""
        echo "# template-ia: agregado automáticamente para el comando 'graph'"
        echo "export PATH=\"$BIN_SRC:\$PATH\""
      } >> "$RC_FILE" 2>/dev/null && \
        echo "GRAPH: agregué el comando 'graph' a tu PATH en $RC_FILE — no hace falta que hagas nada más. Abrí una terminal nueva, o corré 'source $RC_FILE', para poder usarlo." >&2
    fi
    ;;
esac

exit 0
