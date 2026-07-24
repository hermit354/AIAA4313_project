$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Push-Location (Join-Path $root 'web_demo\frontend')
try { npm run dev } finally { Pop-Location }
