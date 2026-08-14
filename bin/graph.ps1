#Requires -Version 5.1
<#
.SYNOPSIS
  Wrapper corto para scripts/graph-ia.py (Windows).

.DESCRIPTION
  Resuelve graph-ia.py en este orden:
    1. $env:GRAPH_IA_SCRIPT (ruta directa al script)
    2. $env:GRAPH_IA_ROOT\scripts\graph-ia.py
    3. ..\scripts\graph-ia.py relativo a este wrapper (checkout local)
    4. la instalación de marketplace activa de Codex ('codex plugin list')
  y lo ejecuta con el primer intérprete de Python disponible (py -3,
  python, python3), pasando el directorio actual como repo_root.

.NOTES
  Mismo contrato que bin/graph (la versión POSIX para Linux/macOS).
#>

[CmdletBinding()]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$GraphArgs
)

$ErrorActionPreference = 'Stop'

function Resolve-TemplateIaScript {
  $candidates = New-Object System.Collections.Generic.List[string]

  if ($env:GRAPH_IA_SCRIPT) {
    $candidates.Add($env:GRAPH_IA_SCRIPT)
  }

  if ($env:GRAPH_IA_ROOT) {
    $candidates.Add((Join-Path $env:GRAPH_IA_ROOT 'scripts\graph-ia.py'))
  }

  # Checkout local del repo del plugin: bin\graph.ps1 -> ..\scripts\graph-ia.py
  $candidates.Add((Join-Path $PSScriptRoot '..\scripts\graph-ia.py'))

  # Instalación de marketplace de Codex
  if (Get-Command codex -ErrorAction SilentlyContinue) {
    try {
      $output = & codex plugin list 2>$null
      $inTemplateIa = $false

      foreach ($line in $output) {
        if ($line -match '^\s*Marketplace\s+`?graph-ia`?\s*$') {
          $inTemplateIa = $true
          continue
        }

        if ($inTemplateIa -and $line -match '^(?<path>[A-Za-z]:\\.*)$') {
          $marketplaceRoot = $Matches.path.Trim()
          if ($marketplaceRoot) {
            $candidates.Add((Join-Path $marketplaceRoot 'scripts\graph-ia.py'))
          }
          break
        }

        if ($inTemplateIa -and $line -match '^\s*Marketplace\s+') {
          $inTemplateIa = $false
        }
      }
    }
    catch {
      # Codex no disponible o con otra estructura de salida: seguir con el
      # resto de los candidatos.
    }
  }

  foreach ($candidate in ($candidates | Select-Object -Unique)) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) {
      return (Resolve-Path -LiteralPath $candidate).Path
    }
  }

  throw @"
No encontré graph-ia.py.

Probé estas opciones:
- GRAPH_IA_SCRIPT
- GRAPH_IA_ROOT\scripts\graph-ia.py
- ..\scripts\graph-ia.py relativo a este wrapper
- la instalación de Codex vía 'codex plugin list'

Instalá el plugin o definí GRAPH_IA_ROOT/GRAPH_IA_SCRIPT.
"@
}

function Resolve-PythonInvocation {
  # Devuelve @{ Exe = ...; PrefixArgs = @(...) } para el primer Python
  # utilizable. 'py -3' primero (launcher oficial de Windows), después
  # python/python3 del PATH. Se valida que el intérprete arranque de
  # verdad — en Windows, 'python' puede ser el alias falso de la
  # Microsoft Store que abre un navegador en vez de ejecutar.
  $attempts = @(
    @{ Exe = 'py';      PrefixArgs = @('-3') },
    @{ Exe = 'python';  PrefixArgs = @() },
    @{ Exe = 'python3'; PrefixArgs = @() }
  )

  foreach ($attempt in $attempts) {
    if (-not (Get-Command $attempt.Exe -ErrorAction SilentlyContinue)) { continue }
    try {
      $null = & $attempt.Exe @($attempt.PrefixArgs + '--version') 2>$null
      if ($LASTEXITCODE -eq 0) { return $attempt }
    }
    catch { }
  }

  throw @"
No encontré un intérprete de Python 3 utilizable (probé: py -3, python, python3).

Instalá Python 3 desde https://www.python.org/downloads/ y asegurate de
marcar "Add python.exe to PATH" durante la instalación.
"@
}

$templateIaScript = Resolve-TemplateIaScript
$python = Resolve-PythonInvocation
$repoRoot = (Get-Location).Path

if ($null -eq $GraphArgs) { $GraphArgs = @() }
$allArgs = @($python.PrefixArgs) + @($templateIaScript, $repoRoot) + $GraphArgs

# Invocación directa (no Start-Process): hereda stdin/stdout/stderr de la
# consola, respeta rutas con espacios sin re-quoting manual, y deja el exit
# code real en $LASTEXITCODE.
& $python.Exe @allArgs
exit $LASTEXITCODE
