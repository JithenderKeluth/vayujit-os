$ErrorActionPreference = "Stop"
$apiRoot = Join-Path $PSScriptRoot "..\apps\api"
$venvRoot = Join-Path $apiRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"

function Find-Python312 {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $launcher) {
        & $launcher.Source -3.12 -c "import sys; assert sys.version_info[:2] == (3, 12)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return [PSCustomObject]@{
                Executable = $launcher.Source
                Arguments = @("-3.12")
            }
        }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        & $python.Source -c "import sys; assert sys.version_info[:2] == (3, 12)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return [PSCustomObject]@{
                Executable = $python.Source
                Arguments = @()
            }
        }
    }

    return $null
}

$pythonCommand = Find-Python312
if ($null -eq $pythonCommand) {
    throw @"
Python 3.12 is required but was not found.

Install it on Windows with:
  winget install --exact --id Python.Python.3.12

Then open a new terminal, verify with:
  py -3.12 --version

Finally rerun:
  npm run api:install
"@
}

$pythonExecutable = $pythonCommand.Executable
$pythonArguments = $pythonCommand.Arguments

& $pythonExecutable @pythonArguments -m venv $venvRoot
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
    throw "Python 3.12 failed to create the virtual environment at $venvRoot."
}

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip in the API virtual environment."
}

& $venvPython -m pip install -e "$apiRoot[dev]"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install API development dependencies."
}
