# template-ia â€” instalaciÃ³n

Plugin que instala el patrÃ³n **GRAPH** en cualquier proyecto. Este
documento es solo sobre cÃ³mo instalarlo â€” la explicaciÃ³n de quÃ© es GRAPH
estÃ¡ en el [README](./README.md), y una vez instalado en
`.agents/graph/README.md`.

GRAPH no estÃ¡ atado a una sola herramienta de IA. Hay tres formas de
instalarlo â€” elegÃ­ la que corresponda a lo que usÃ¡s:

## OpciÃ³n 1 â€” Universal (funciona con cualquier LLM/agente, sin plugin system)

```bash
git clone https://gitlab-ee.agil.movistar.com.ar/cloudersdesarrollos/investigacion/ia/template-ia.git /tmp/template-ia
cd /tu/proyecto
python3 /tmp/template-ia/scripts/template-ia.py . --mode=greenfield
# o, si el proyecto ya tiene cÃ³digo:
python3 /tmp/template-ia/scripts/template-ia.py . --mode=brownfield --migrate
```

Esto arma toda la estructura `.agents/` y el bridge `AGENTS.md`/`CLAUDE.md`
usando solo Python 3 â€” nada de plugins, nada especÃ­fico de una
herramienta. Cualquier agente que lea `AGENTS.md` (Claude Code, Codex CLI,
Cursor, lo que sea) va a encontrar el contexto igual.

**LimitaciÃ³n honesta:** el circuit breaker (freno de mano que *bloquea* de
verdad acciones del agente) necesita que tu herramienta tenga un sistema de
hooks compatible. Instalado asÃ­, `circuit-breaker.yml` queda como contrato
documentado que el agente puede leer y respetar, pero no hay enforcement
forzado â€” para eso, ver la OpciÃ³n 2 o la 3.

## OpciÃ³n 2 â€” Plugin de Claude Code (agrega enforcement real del circuit breaker)

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

(o reiniciÃ¡ la sesiÃ³n de Claude Code/Antigravity si ese comando no estÃ¡
disponible en tu versiÃ³n)

### 4. Confirmar que quedÃ³ instalado

EscribÃ­ `/template-ia:` en el chat â€” te tiene que aparecer
`/template-ia:template-ia` en la lista de comandos disponibles. Si no
aparece, el reload no tomÃ³ el plugin â€” repetÃ­ el paso 3.

### 5. Correrlo en tu proyecto

Parado en la raÃ­z de tu proyecto (donde estÃ¡ tu `.git`):

```
/template-ia:template-ia --mode=greenfield
```

o, si el proyecto ya tiene cÃ³digo/historia:

```
/template-ia:template-ia --mode=brownfield --migrate
```

## OpciÃ³n 3 â€” Plugin de Codex CLI (agrega enforcement real del circuit breaker en Codex)

Requisitos: Codex CLI, Python 3.

### 0. Si no tenÃ©s Codex CLI instalado

```bash
npm install -g @openai/codex
codex --version
```

(el paquete correcto es `@openai/codex`, no `codex` a secas â€” ese Ãºltimo
es un proyecto viejo sin relaciÃ³n con OpenAI)

### 1. Agregar el marketplace

```bash
codex plugin marketplace add cloudersdesarrollos/template-ia
```

### 2. Instalar el plugin

```bash
codex plugin add template-ia@template-ia
```

### 3. Iniciar una sesiÃ³n nueva

Las skills que trae el plugin quedan disponibles reciÃ©n al arrancar una
sesiÃ³n nueva de Codex â€” cerrÃ¡ la actual si estaba abierta.

### 4. Correrlo en tu proyecto

Codex no tiene comandos slash tipo `/template-ia:template-ia` â€” la lÃ³gica
quedÃ³ empaquetada como una Skill. Parado en la raÃ­z de tu proyecto,
pedÃ­selo en lenguaje natural:

> "InstalÃ¡ el patrÃ³n GRAPH acÃ¡ â€” modo brownfield, con migrate"

Codex deberÃ­a reconocer y usar la skill `template-ia` sola.

**Comandos confirmados contra Codex CLI 0.142.0** (con `codex plugin
marketplace add --help` / `codex plugin add --help`) â€” si tu versiÃ³n da
error de "subcomando no reconocido", corrÃ© esos mismos `--help` para
confirmar la sintaxis de tu versiÃ³n puntual.

## QuÃ© hace, en una lÃ­nea

Arma `.agents/graph/` (spec, config del circuit breaker, gates de
aprobaciÃ³n, conocimiento del proyecto indexado automÃ¡ticamente) y
`.agents/roles/` (planner/executor/reviewer). En modo `brownfield` ademÃ¡s
indexa el cÃ³digo real del repo (con un indexador propio del plugin, sin
depender de nada externo) y reconcilia el historial de git.

Nunca pisa archivos que ya existan â€” si algo ya está, lo salta y te avisa.

Nota de empaquetado: este repositorio mantiene la fuente del plugin (`scripts/`, `templates/`, `skills/`, `hooks/`, `commands/`, tests). Todo `.agents/` que aparezca en la raíz es salida de una instalación o prueba local y no forma parte del payload del plugin.

## Si algo no anda

- El comando/skill no aparece â†’ el reload/sesiÃ³n nueva no tomÃ³ el plugin,
  repetÃ­ el paso correspondiente.
- Los hooks no parecen estar activos â†’ confirmÃ¡ que la instalaciÃ³n del
  plugin terminÃ³ sin errores; los 3 hooks (`claude-code-hook.sh`,
  `session-reset-hook.sh`, `stagnation-hook.sh`) se registran solos, no
  hace falta tocar `settings.json`/`config.toml` a mano.
- Codex: si `codex plugin marketplace add` o `codex plugin add` dan
  "unrecognized subcommand", tu versiÃ³n tiene otra estructura â€” corrÃ©
  `codex plugin --help` para ver los subcomandos reales disponibles.


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
