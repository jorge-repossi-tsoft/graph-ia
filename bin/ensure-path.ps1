#Requires -Version 5.1
<#
.SYNOPSIS
  Registra una carpeta en el PATH de usuario y en el profile de PowerShell.

.DESCRIPTION
  Llamado por hooks/cli-install-hook.sh en Windows. Hace dos cosas, cada
  una idempotente:

    1. Agrega -TargetDir al PATH de usuario persistente (registro HKCU) vía
       [Environment]::SetEnvironmentVariable — no setx, que trunca el valor
       a 1024 caracteres y puede corromper un PATH de usuario ya largo.
       Esto cubre terminales EXTERNAS nuevas y cualquier proceso lanzado
       después por el Explorador de Windows.

    2. Agrega una línea a $PROFILE.CurrentUserAllHosts (de la versión de
       PowerShell con la que se invoque este script — llamalo una vez con
       powershell.exe y otra con pwsh.exe si ambos existen, para cubrir los
       dos). Esto cubre pestañas NUEVAS de terminal integrada en VS Code:
       aunque el proceso de VS Code ya esté corriendo con el PATH viejo
       cacheado, cada pestaña nueva arranca su propio proceso de PowerShell,
       que sí lee $PROFILE al iniciar — no depende del PATH heredado del
       proceso padre.

  Ninguno de los dos mecanismos actualiza una terminal YA abierta antes de
  correr este script — hace falta una pestaña nueva (o, si ni así aparece,
  es señal de que el profile real que carga esa terminal es otro archivo;
  ver troubleshooting en INSTALL.md).

.PARAMETER TargetDir
  Carpeta a agregar al PATH (normalmente bin/ del checkout del plugin).

.OUTPUTS
  Una línea 'PATH_UPDATED' si tocó el PATH de usuario, y/o una línea
  'PROFILE_UPDATED' si tocó el profile — para que el caller decida si avisa
  al usuario. Sin output = ya estaba todo al día, no se tocó nada.
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)]
  [string]$TargetDir
)

$ErrorActionPreference = 'Stop'

function Add-UserPathEntry {
  param([string]$Dir)
  $current = [Environment]::GetEnvironmentVariable('Path', 'User')
  $parts = @()
  if ($current) { $parts = $current -split ';' | Where-Object { $_ -ne '' } }
  if ($parts -contains $Dir) { return $false }
  $new = if ($current) { "$current;$Dir" } else { $Dir }
  [Environment]::SetEnvironmentVariable('Path', $new, 'User')
  return $true
}

function Add-ProfileEntry {
  param([string]$Dir)
  $profilePath = $PROFILE.CurrentUserAllHosts
  if (-not $profilePath) { return $false }

  if (-not (Test-Path -LiteralPath $profilePath)) {
    $parent = Split-Path -Parent $profilePath
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
      New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }
    New-Item -ItemType File -Force -Path $profilePath | Out-Null
  }

  # -Encoding UTF8: el default de Get-Content/Add-Content en Windows
  # PowerShell 5.1 NO es UTF-8 (a diferencia de pwsh 7+) — sin esto, los
  # acentos del marcador se corrompen al escribirlos.
  $existing = Get-Content -LiteralPath $profilePath -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
  if ($existing -and $existing.Contains($Dir)) { return $false }

  $marker = "# template-ia: agregado automáticamente para el comando 'graph'"
  $line = "if (`$env:Path -notlike ('*' + '$Dir' + '*')) { `$env:Path += ';$Dir' }"
  Add-Content -LiteralPath $profilePath -Value "`n$marker`n$line" -Encoding UTF8
  return $true
}

$results = @()
if (Add-UserPathEntry -Dir $TargetDir) { $results += 'PATH_UPDATED' }
if (Add-ProfileEntry -Dir $TargetDir) { $results += 'PROFILE_UPDATED' }
$results -join "`n"
