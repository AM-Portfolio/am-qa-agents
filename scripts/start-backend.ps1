# Start unified qa-agent backend on :8150
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$env:PYTHONPATH = "$Root\qa-agent;$Root\qa-agent\release_gate"
$env:QA_AGENT_WORKER_ENABLED = if ($env:QA_AGENT_WORKER_ENABLED) { $env:QA_AGENT_WORKER_ENABLED } else { "0" }

# Portal OIDC is am-qa-agents-dev (not am-dev-realm). Set before dotenv so
# .env.local (override=False) cannot keep a stale realm and 401 the code exchange.
if (-not $env:KEYCLOAK_REALM -or $env:KEYCLOAK_REALM -eq "am-dev-realm") {
  $env:KEYCLOAK_REALM = "am-qa-agents-dev"
}
if (-not $env:KEYCLOAK_ISSUER -or $env:KEYCLOAK_ISSUER -like "*/am-dev-realm") {
  $env:KEYCLOAK_ISSUER = "https://auth.asrax.in/realms/am-qa-agents-dev"
}
if (-not $env:KEYCLOAK_QA_REDIRECT_URI) {
  $env:KEYCLOAK_QA_REDIRECT_URI = "http://localhost:8151/callback"
}

Write-Host "PYTHONPATH=$env:PYTHONPATH"
Write-Host "KEYCLOAK_REALM=$env:KEYCLOAK_REALM"
Write-Host "Starting composition.main on :8150 (worker=$env:QA_AGENT_WORKER_ENABLED)..."
python -m composition.main
