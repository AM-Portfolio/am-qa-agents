# Start unified qa-agent backend on :8150
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$env:PYTHONPATH = "$Root\qa-agent;$Root\qa-agent\release_gate"
$env:QA_AGENT_WORKER_ENABLED = if ($env:QA_AGENT_WORKER_ENABLED) { $env:QA_AGENT_WORKER_ENABLED } else { "0" }

Write-Host "PYTHONPATH=$env:PYTHONPATH"
Write-Host "Starting composition.main on :8150 (worker=$env:QA_AGENT_WORKER_ENABLED)..."
python -m composition.main
