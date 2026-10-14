# Train a LoRA with ai-toolkit using the models already in ComfyUI/models.
# Usage: .\scripts\train_lora.ps1 training\auburn_freckles.yaml
param([Parameter(Mandatory = $true)][string]$Config)
# No "Stop" here: Windows PowerShell 5.1 turns every stderr line (tqdm progress bars)
# into an error record when output is redirected, which would abort training.
$Root = Split-Path -Parent $PSScriptRoot
$ConfigPath = (Resolve-Path $Config).Path
$env:MODELS_PATH = Join-Path $Root "ComfyUI\models"
$env:PYTHONUNBUFFERED = "1"
Set-Location (Join-Path $Root "ai-toolkit")
& cmd /c "venv\Scripts\python.exe run.py `"$ConfigPath`" 2>&1"
if ($LASTEXITCODE) { throw "Training failed with exit code $LASTEXITCODE" }
Write-Host "LoRA files: ai-toolkit\output\<name>\. Copy the chosen one to ComfyUI\models\loras."
