# template-ia — instalación

Plugin que instala el patrón **GRAPH** en cualquier proyecto. Este
documento es solo sobre cómo instalarlo: la explicación de qué es GRAPH
está en el [README](./README.md), y una vez instalado en
`.agents/graph/README.md`.

GRAPH no está atado a una sola herramienta de IA. Hay tres formas de
instalarlo: elegí la que corresponda a lo que usás.

## Opción 1 — Universal (funciona con cualquier LLM/agente, sin plugin system)

```bash
git clone https://gitlab-ee.agil.movistar.com.ar/cloudersdesarrollos/investigacion/ia/template-ia.git /tmp/template-ia
cd /tu/proyecto
python3 /tmp/template-ia/scripts/template-ia.py . --mode=greenfield
# o, si el proyecto ya tiene código:
python3 /tmp/template-ia/scripts/template-ia.py . --mode=brownfield --migrate
```

Esto arma toda la estructura `.agents/` y el bridge `AGENTS.md`/`CLAUDE.md`
usando solo Python 3: nada de plugins, nada específico de una
herramienta. Cualquier agente que lea `AGENTS.md` (Claude Code, Codex CLI,
Cursor, lo que sea) va a encontrar el contexto igual.

**Limitación honesta:** el circuit breaker (freno de mano que *bloquea* de
verdad acciones del agente) necesita que tu herramienta tenga un sistema de
hooks compatible. Instalado así, `circuit-breaker.yml` queda como contrato
documentado que el agente puede leer y respetar, pero no hay enforcement
forzado. Para eso, ver la Opción 2 o la 3.

## Opción 2 — Plugin de Claude Code (agrega enforcement real del circuit breaker)

Requisitos: Claude Code (o Antigravity) instalado, Python 3.

### 1. Agregar el marketplace

```
/plugin marketplace add cloudersdesarrollos/template-ia
```

### 2. Instalar el plugin

```
/plugin install template-ia@template-ia
```

### 3. Recargar

```
/reload-plugins
```

(o reiniciá la sesión de Claude Code/Antigravity si ese comando no está
disponible en tu versión)

### 4. Confirmar que quedó instalado

Escribí `/template-ia:` en el chat: te tiene que aparecer
`/template-ia:template-ia` en la lista de comandos disponibles. Si no
aparece, el reload no tomó el plugin. Repetí el paso 3.

### 5. Correrlo en tu proyecto

Parado en la raíz de tu proyecto (donde está tu `.git`):

```
/template-ia:template-ia --mode=greenfield
```

o, si el proyecto ya tiene código o historia:

```
/template-ia:template-ia --mode=brownfield --migrate
```

## Opción 3 — Plugin de Codex CLI (agrega enforcement real del circuit breaker en Codex)

Requisitos: Codex CLI, Python 3.

### 0. Si no tenés Codex CLI instalado

```bash
npm install -g @openai/codex
codex --version
```

(el paquete correcto es `@openai/codex`, no `codex` a secas; ese último
es un proyecto viejo sin relación con OpenAI)

### 1. Agregar el marketplace

```bash
codex plugin marketplace add cloudersdesarrollos/template-ia
```

### 2. Instalar el plugin

```bash
codex plugin add template-ia@template-ia
```

### 3. Iniciar una sesión nueva

Las skills que trae el plugin quedan disponibles recién al arrancar una
sesión nueva de Codex. Cerrá la actual si estaba abierta.

### 4. Correrlo en tu proyecto

Codex no tiene comandos slash tipo `/template-ia:template-ia`: la lógica
quedó empaquetada como una skill. Parado en la raíz de tu proyecto,
pedíselo en lenguaje natural:

> "Instalá el patrón GRAPH acá, en modo brownfield, con migrate"

Codex debería reconocer y usar la skill `template-ia` sola.

**Comandos confirmados contra Codex CLI 0.142.0** (con `codex plugin
marketplace add --help` / `codex plugin add --help`). Si tu versión da
error de "subcomando no reconocido", corré esos mismos `--help` para
confirmar la sintaxis de tu versión puntual.

### 5. Comando de terminal `graph` (se instala solo)

El plugin trae un CLI corto, `graph`, que **se registra solo en tu PATH de
usuario** la primera vez que usás el plugin (lo hace un hook, tanto en
Claude Code como en Codex; la instalación universal con `install.sh` también
lo registra). No hay que agregar nada al PATH a mano — solo abrir una
terminal nueva después de la primera vez, porque los cambios de PATH no
aplican a terminales que ya estaban abiertas.

Los wrappers viven en `bin/` del checkout del plugin:

- `bin/graph.ps1` + `bin/graph.cmd` (Windows)
- `bin/graph` (Linux/macOS)

Buscan `template-ia.py` en este orden:

1. `TEMPLATE_IA_SCRIPT`
2. `TEMPLATE_IA_ROOT\scripts\template-ia.py`
3. el checkout local del repo del plugin
4. la instalación activa de Codex vía `codex plugin list`

Uso, desde cualquier terminal, parado en la raíz de tu proyecto:

```bash
graph --reindex
graph --update-docs
graph --mode=greenfield
graph --mode=brownfield --migrate
```

Si no encuentra `template-ia.py`, falla con un mensaje claro para que puedas
instalar el plugin o apuntar el checkout correcto sin tocar rutas fijas.

## Qué hace, en una línea

Arma `.agents/graph/` (spec, config del circuit breaker, gates de
aprobación y conocimiento del proyecto indexado automáticamente) y
`.agents/roles/` (planner/executor/reviewer). En modo `brownfield`, además,
indexa el código real del repo (con un indexador propio del plugin, sin
depender de nada externo) y reconcilia el historial de git.

Nunca pisa archivos que ya existan: si algo ya está, lo salta y te avisa.

Nota de empaquetado: este repositorio mantiene la fuente del plugin (`scripts/`, `templates/`, `skills/`, `hooks/`, `commands/`, `tests/`). Todo `.agents/` que aparezca en la raíz es salida de una instalación o prueba local y no forma parte del payload del plugin.

## Si algo no anda

- El comando o la skill no aparece: el reload o la sesión nueva no tomó el plugin. Repetí el paso correspondiente.
- Los hooks no parecen estar activos: confirmá que la instalación del plugin terminó sin errores; los 3 hooks (`claude-code-hook.sh`, `session-reset-hook.sh`, `stagnation-hook.sh`) se registran solos, no hace falta tocar `settings.json` o `config.toml` a mano.
- Codex: si `codex plugin marketplace add` o `codex plugin add` dan "unrecognized subcommand", tu versión tiene otra estructura. Corré `codex plugin --help` para ver los subcomandos reales disponibles.

## Release Package

For a clean publish bundle, run:

```bash
python3 scripts/build-release.py
```

This generates `dist/template-ia-release/` and `dist/template-ia-release.zip`
with source files only. It excludes `.agents/`, caches, temp folders, and
local test artifacts.

The release script also supports `--versioned`, which emits a sibling bundle named with the plugin version (for example `template-ia-release-v3.1.0`) and validates that both plugin manifests share the same semver first.

For the release and publishing checklist, see [RELEASE.md](./RELEASE.md).
