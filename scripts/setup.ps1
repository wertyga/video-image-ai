# Установка на Windows: .\scripts\setup.ps1 -Profile local-16gb
param(
    [ValidateSet("local-16gb", "server")]
    [string]$Profile = "local-16gb"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path "ComfyUI")) {
    git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git ComfyUI
} else {
    git -C ComfyUI pull --ff-only
}

if (-not (Test-Path ".venv")) {
    py -3.13 -m venv .venv
}
$Py = Join-Path $Root ".venv\Scripts\python.exe"
& $Py -m pip install --upgrade pip
& $Py -m pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu130
& $Py -m pip install -r ComfyUI\requirements.txt

& $Py scripts\download_models.py --profile $Profile
Write-Host "Готово. Запуск: .\scripts\run.ps1"
