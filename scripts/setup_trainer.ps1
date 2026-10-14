# Install ai-toolkit (LoRA training) into .\ai-toolkit with its own Python 3.12 (via uv).
# Run .\scripts\setup.ps1 first.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
function Check { if ($LASTEXITCODE) { throw "Command failed with exit code $LASTEXITCODE" } }

& .venv\Scripts\python.exe -m pip install -q uv; Check
$Uv = Join-Path $Root ".venv\Scripts\uv.exe"
if (-not (Test-Path "ai-toolkit")) {
    git clone --depth 1 https://github.com/ostris/ai-toolkit.git ai-toolkit; Check
}
Set-Location ai-toolkit
if (-not (Test-Path "venv")) { & $Uv venv --python 3.12 venv; Check }
& $Uv pip install --python venv\Scripts\python.exe torch==2.13.0 torchvision==0.28.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu130; Check
& $Uv pip install --python venv\Scripts\python.exe -r requirements.txt --index-strategy unsafe-best-match --extra-index-url https://download.pytorch.org/whl/cu130; Check
& venv\Scripts\python.exe -c "import torch; assert torch.cuda.is_available(); print('ai-toolkit ready, torch', torch.__version__)"; Check
