# Windows setup: .\scripts\setup.ps1 -Profile local-16gb
param(
    [ValidateSet("local-16gb", "server")]
    [string]$Profile = "local-16gb"
)
$ErrorActionPreference = "Stop"
# Python scripts print UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# Windows PowerShell 5.1 does not stop on native command failures
function Check { if ($LASTEXITCODE) { throw "Command failed with exit code $LASTEXITCODE" } }

if (-not (Test-Path "ComfyUI")) {
    git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git ComfyUI; Check
} else {
    git -C ComfyUI pull --ff-only; Check
}

if (-not (Test-Path ".venv")) {
    py -3.13 -m venv .venv; Check
}
$Py = Join-Path $Root ".venv\Scripts\python.exe"
& $Py -m pip install --upgrade pip; Check
& $Py -m pip install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu130; Check
& $Py -m pip install -r ComfyUI\requirements.txt; Check

& $Py scripts\download_models.py --profile $Profile; Check
Write-Host "Done. Start with: .\scripts\run.ps1"
