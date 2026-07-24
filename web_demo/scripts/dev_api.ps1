$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$python = Join-Path $root '.venv\Scripts\python.exe'
if (!(Test-Path $python)) { $python = 'python' }
& $python -m alembic -c (Join-Path $root 'web_demo\alembic.ini') upgrade head
& $python -m uvicorn web_demo.backend:app --app-dir $root --reload --port 8000
