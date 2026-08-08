param(
  [string]$ApiRoot = "",
  [string]$DataRoot = ""
)
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($ApiRoot)) { $ApiRoot = Join-Path $PSScriptRoot "..\api" }
if ([string]::IsNullOrWhiteSpace($DataRoot)) { $DataRoot = Join-Path $env:LOCALAPPDATA "VAYUJIT OS" }
$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
if (-not $python) { throw "Python 3.12 is required. Install it from python.org, then rerun this command." }
$runtimeRoot = Join-Path $DataRoot "runtime"
$venv = Join-Path $runtimeRoot "api-venv"
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
& $python.Source -3.12 -m venv $venv 2>$null
if ($LASTEXITCODE -ne 0) { & $python.Source -m venv $venv }
$venvPython = Join-Path $venv "Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install $ApiRoot
if ($LASTEXITCODE -ne 0) { throw "Unable to install the local API runtime." }
Write-Output $venvPython
