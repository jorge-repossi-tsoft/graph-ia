# graph-ia â€” instalaciÃ³n

Plugin que instala el patrÃ³n **GRAPH** en cualquier proyecto. Este
documento es solo sobre cÃ³mo instalarlo: la explicaciÃ³n de quÃ© es GRAPH
estÃ¡ en el [README](./README.md), y una vez instalado en
`.agents/graph/README.md`.

GRAPH no estÃ¡ atado a una sola herramienta de IA. Hay tres formas de
instalarlo: elegÃ­ la que corresponda a lo que usÃ¡s.

## OpciÃ³n 1 â€” Universal (funciona con cualquier LLM/agente, sin plugin system)

```bash
git clone https://github.com/jorge-repossi-tsoft/graph-ia.git /tmp/graph-ia
cd /tu/proyecto
python3 /tmp/graph-ia/scripts/graph-ia.py . --mode=greenfield
# o, si el proyecto ya tiene cÃ³digo:
python3 /tmp/graph-ia/scripts/graph-ia.py . --mode=brownfield --migrate
```

`--migrate` copia `.agents/system.md` a `.agents/graph/legacy-system.md` y preserva el archivo original.

Esto arma toda la estructura `.agents/` y el bridge `AGENTS.md`/`CLAUDE.md`
usando solo Python 3: nada de plugins, nada especÃ­fico de una
herramienta. Cualquier agente que lea `AGENTS.md` (Claude Code, Codex CLI,
Cursor, lo que sea) va a encontrar el contexto igual.

**LimitaciÃ³n honesta:** el circuit breaker (freno de mano que *bloquea* de
verdad acciones del agente) necesita que tu herramienta tenga un sistema de
hooks compatible. Instalado asÃ­, `circuit-breaker.yml` queda como contrato
documentado que el agente puede leer y respetar, pero no hay enforcement
forzado. Para eso, ver la OpciÃ³n 2 o la 3.

## OpciÃ³n 2 â€” Plugin de Claude Code (agrega enforcement real del circuit breaker)

Requisitos: Claude Code (o Antigravity) instalado, Python 3.

### 1. Agregar el marketplace

```
/plugin marketplace add cloudersdesarrollos/graph-ia
```

### 2. Instalar el plugin

```
/plugin install graph-ia@graph-ia
```

### 3. Recargar

```
/reload-plugins
```

(o reiniciÃ¡ la sesiÃ³n de Claude Code/Antigravity si ese comando no estÃ¡
disponible en tu versiÃ³n)

### 4. Confirmar que quedÃ³ instalado

EscribÃ­ `/graph-ia:` en el chat: te tiene que aparecer
`/graph-ia:graph-ia` en la lista de comandos disponibles. Si no
aparece, el reload no tomÃ³ el plugin. RepetÃ­ el paso 3.

### 5. Correrlo en tu proyecto

Parado en la raÃ­z de tu proyecto (donde estÃ¡ tu `.git`):

```
/graph-ia:graph-ia --mode=greenfield
```

o, si el proyecto ya tiene cÃ³digo o historia:

```
/graph-ia:graph-ia --mode=brownfield --migrate
```

## OpciÃ³n 3 â€” Plugin de Codex CLI (agrega enforcement real del circuit breaker en Codex)

Requisitos: Codex CLI, Python 3.

### 0. Si no tenÃ©s Codex CLI instalado

```bash
npm install -g @openai/codex
codex --version
```

(el paquete correcto es `@openai/codex`, no `codex` a secas; ese Ãºltimo
es un proyecto viejo sin relaciÃ³n con OpenAI)

### 1. Agregar el marketplace

```bash
codex plugin marketplace add cloudersdesarrollos/graph-ia
```

### 2. Instalar el plugin

```bash
codex plugin add graph-ia@graph-ia
```

### 3. Iniciar una sesiÃ³n nueva

Las skills que trae el plugin quedan disponibles reciÃ©n al arrancar una
sesiÃ³n nueva de Codex. CerrÃ¡ la actual si estaba abierta.

### 4. Correrlo en tu proyecto

Codex no tiene comandos slash tipo `/graph-ia:graph-ia`: la lÃ³gica
quedÃ³ empaquetada como una skill. Parado en la raÃ­z de tu proyecto,
pedÃ­selo en lenguaje natural:

> "InstalÃ¡ el patrÃ³n GRAPH acÃ¡, en modo brownfield, con migrate"

Codex deberÃ­a reconocer y usar la skill `graph-ia` sola.

**Comandos confirmados contra Codex CLI 0.142.0** (con `codex plugin
marketplace add --help` / `codex plugin add --help`). Si tu versiÃ³n da
error de "subcomando no reconocido", corrÃ© esos mismos `--help` para
confirmar la sintaxis de tu versiÃ³n puntual.

### 5. Comando de terminal `graph` (se instala solo)

El plugin trae un CLI corto, `graph`, que **se registra solo en tu PATH de
usuario** la primera vez que usÃ¡s el plugin (lo hace un hook, tanto en
Claude Code como en Codex; la instalaciÃ³n universal con `install.sh` tambiÃ©n
lo registra). No hay que agregar nada al PATH a mano â€” solo abrir una
terminal nueva despuÃ©s de la primera vez, porque los cambios de PATH no
aplican a terminales que ya estaban abiertas.

Los wrappers viven en `bin/` del checkout del plugin:

- `bin/graph.ps1` + `bin/graph.cmd` (Windows)
- `bin/graph` (Linux/macOS)

Buscan `graph-ia.py` en este orden:

1. `GRAPH_IA_SCRIPT`
2. `GRAPH_IA_ROOT\scripts\graph-ia.py`
3. el checkout local del repo del plugin
4. la instalaciÃ³n activa de Codex vÃ­a `codex plugin list`

Uso, desde cualquier terminal, parado en la raÃ­z de tu proyecto:

```bash
graph --reindex
graph --update-docs
graph --mode=greenfield
graph --mode=brownfield --migrate
```

Si no encuentra `graph-ia.py`, falla con un mensaje claro para que puedas
instalar el plugin o apuntar el checkout correcto sin tocar rutas fijas.

## QuÃ© hace, en una lÃ­nea

Arma `.agents/graph/` (spec, config del circuit breaker, gates de
aprobaciÃ³n y conocimiento del proyecto indexado automÃ¡ticamente) y
`.agents/roles/` (planner/executor/reviewer). En modo `brownfield`, ademÃ¡s,
indexa el cÃ³digo real del repo (con un indexador propio del plugin, sin
depender de nada externo) y reconcilia el historial de git.

Nunca pisa archivos que ya existan: si algo ya estÃ¡, lo salta y te avisa.

Nota de empaquetado: este repositorio mantiene la fuente del plugin (`scripts/`, `templates/`, `skills/`, `hooks/`, `commands/`, `tests/`). Todo `.agents/` que aparezca en la raÃ­z es salida de una instalaciÃ³n o prueba local y no forma parte del payload del plugin.

## Si algo no anda

- El comando o la skill no aparece: el reload o la sesiÃ³n nueva no tomÃ³ el plugin. RepetÃ­ el paso correspondiente.
- Los hooks no parecen estar activos: confirmÃ¡ que la instalaciÃ³n del plugin terminÃ³ sin errores; los 3 hooks (`claude-code-hook.sh`, `session-reset-hook.sh`, `stagnation-hook.sh`) se registran solos, no hace falta tocar `settings.json` o `config.toml` a mano.
- Codex: si `codex plugin marketplace add` o `codex plugin add` dan "unrecognized subcommand", tu versiÃ³n tiene otra estructura. CorrÃ© `codex plugin --help` para ver los subcomandos reales disponibles.
- `graph` funciona en una terminal externa pero no en la terminal integrada de VS Code (u otro editor): el hook que registra `graph` en el PATH corriÃ³ *despuÃ©s* de que el editor ya estaba abierto. El proceso del editor cachea el entorno con el que arrancÃ³, asÃ­ que el PATH nuevo no le llega hasta que se cierra del todo y se vuelve a abrir. Como paso previo a eso, probÃ¡ primero con una **pestaÃ±a de terminal nueva** (no reusar la actual): el hook tambiÃ©n agrega el PATH al profile de PowerShell/pwsh (`$PROFILE.CurrentUserAllHosts`) y a `~/.bashrc` (Git Bash) â€” una pestaÃ±a nueva lanza su propio proceso de shell y sÃ­ lee esos archivos al arrancar, sin necesitar reiniciar el editor completo. Si ni con pestaÃ±a nueva aparece, el editor estÃ¡ usando un profile distinto al que tocamos (por ejemplo `$PROFILE.CurrentUserCurrentHost` en vez de `CurrentUserAllHosts`, o un `.bash_profile` que no hace `source` de `.bashrc`) â€” en ese caso, agregÃ¡ `bin/` del checkout del plugin a mano en ese archivo puntual.

## Release Package

For a clean publish bundle, run:

```bash
python3 scripts/build-release.py
```

This generates `dist/graph-ia-release/` and `dist/graph-ia-release.zip`
with source files only. It excludes `.agents/`, caches, temp folders, and
local test artifacts.

The release script also supports `--versioned`, which emits a sibling bundle named with the plugin version (for example `graph-ia-release-v3.1.0`) and validates that both plugin manifests share the same semver first.

For the release and publishing checklist, see [RELEASE.md](./RELEASE.md).
