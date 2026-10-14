# Start ComfyUI on Windows, UI at http://127.0.0.1:8188
$Root = Split-Path -Parent $PSScriptRoot
& (Join-Path $Root ".venv\Scripts\python.exe") (Join-Path $Root "ComfyUI\main.py") `
    --output-directory (Join-Path $Root "output") @args
