$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$apiScript = Join-Path $root 'web_demo\scripts\dev_api.ps1'
Start-Process powershell -ArgumentList '-ExecutionPolicy','Bypass','-File',$apiScript -WindowStyle Hidden
Start-Sleep -Seconds 2
& (Join-Path $root 'web_demo\scripts\dev_frontend.ps1')
