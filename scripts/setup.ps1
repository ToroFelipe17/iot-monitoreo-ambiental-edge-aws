$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $projectRoot ".venv"
$pythonPath = Join-Path $venvPath "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Host "Creando entorno virtual en $venvPath"
    python -m venv $venvPath
}

Write-Host "Actualizando pip e instalando dependencias..."
& $pythonPath -m pip install --upgrade pip
& $pythonPath -m pip install -r (Join-Path $projectRoot "requirements.txt")

Write-Host ""
Write-Host "Entorno listo."
Write-Host "Python del proyecto: $pythonPath"
Write-Host "Prueba automática: .\.venv\Scripts\python.exe .\scripts\e2e_test.py"

