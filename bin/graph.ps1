param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$GraphArgs
)

$ErrorActionPreference = 'Stop'

function Resolve-TemplateIaScript {
  $candidates = New-Object System.Collections.Generic.List[string]

  if ($env:TEMPLATE_IA_SCRIPT) {
    $candidates.Add($env:TEMPLATE_IA_SCRIPT)
  }

  if ($env:TEMPLATE_IA_ROOT) {
    $candidates.Add((Join-Path $env:TEMPLATE_IA_ROOT 'scripts\template-ia.py'))
  }

  # Local checkout of the plugin repo: bin\graph.ps1 -> ..\scripts\template-ia.py
  $localScript = Join-Path $PSScriptRoot '..\scripts\template-ia.py'
  $candidates.Add($localScript)

  # Installed marketplace copy from Codex
  if (Get-Command codex -ErrorAction SilentlyContinue) {
    try {
      $output = & codex plugin list 2>$null
      $inTemplateIa = $false

      foreach ($line in $output) {
        if ($line -match '^\s*Marketplace\s+`?template-ia`?\s*$') {
          $inTemplateIa = $true
          continue
        }

        if ($inTemplateIa -and $line -match '^(?<path>[A-Za-z]:\\.*)$') {
          $marketplaceRoot = $Matches.path.Trim()
          if ($marketplaceRoot) {
            $candidates.Add((Join-Path $marketplaceRoot 'scripts\template-ia.py'))
          }
          break
        }

        if ($inTemplateIa -and $line -match '^\s*Marketplace\s+') {
          $inTemplateIa = $false
        }
      }
    }
    catch {
      # If Codex is unavailable, keep falling back to other candidates.
    }
  }

  foreach ($candidate in ($candidates | Select-Object -Unique)) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) {
      return (Resolve-Path -LiteralPath $candidate).Path
    }
  }

  throw @"
No encontré template-ia.py.

Probé estas opciones:
- TEMPLATE_IA_SCRIPT
- TEMPLATE_IA_ROOT\scripts\template-ia.py
- ..\scripts\template-ia.py relativo a este wrapper
- la instalación de Codex via 'codex plugin list'

Instalá el plugin o definí TEMPLATE_IA_ROOT/TEMPLATE_IA_SCRIPT.
"@
}

$templateIaScript = Resolve-TemplateIaScript
$repoRoot = (Get-Location).Path

$arguments = @($templateIaScript, $repoRoot) + $GraphArgs
$process = Start-Process -FilePath 'py' -ArgumentList $arguments -NoNewWindow -Wait -PassThru
exit $process.ExitCode
