# Port-forward VPS Kind services for local qa-agent lab.
# Requires: VPS\VPS\kubeconfig.vps (or set KUBECONFIG).
#
# Forwards (default local ports):
#   Temporal frontend  127.0.0.1:7233  -> temporal/svc/temporal-frontend:7233
#   InfluxDB           127.0.0.1:8086  -> infra/svc/influxdb:8086
#   Qdrant (optional)  127.0.0.1:6333  -> am-ai/svc/qdrant:6333  (STS often scaled to 0)
#
# Usage:
#   .\scripts\vps-port-forward.ps1
#   .\scripts\vps-port-forward.ps1 -IncludeQdrant
#   npm run vps:forward

param(
    [switch]$IncludeQdrant,
    [string]$Kubeconfig = ""
)

$ErrorActionPreference = "Stop"

$candidates = @(
    $Kubeconfig,
    $env:KUBECONFIG,
    (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "VPS\VPS\kubeconfig.vps"),
    "F:\am-repos\am-repos\VPS\VPS\kubeconfig.vps"
) | Where-Object { $_ -and (Test-Path $_) }

if (-not $candidates) {
    Write-Error "kubeconfig.vps not found. Pass -Kubeconfig or set KUBECONFIG."
    exit 1
}

$env:KUBECONFIG = $candidates[0]
Write-Host "KUBECONFIG=$env:KUBECONFIG"

try {
    kubectl cluster-info --request-timeout=8s | Out-Null
} catch {
    Write-Error "Cannot reach VPS cluster with this kubeconfig."
    exit 1
}

$jobs = @(
    @{ Name = "temporal"; Args = @("-n", "temporal", "port-forward", "svc/temporal-frontend", "7233:7233") },
    @{ Name = "influx"; Args = @("-n", "infra", "port-forward", "svc/influxdb", "8086:8086") }
)

if ($IncludeQdrant) {
    $ready = kubectl get sts qdrant -n am-ai -o jsonpath="{.status.readyReplicas}" 2>$null
    if (-not $ready -or $ready -eq "0") {
        Write-Warning "Qdrant StatefulSet replicas are 0 (no endpoints). Scale first: kubectl scale sts qdrant -n am-ai --replicas=1"
    }
    $jobs += @{ Name = "qdrant"; Args = @("-n", "am-ai", "port-forward", "svc/qdrant", "6333:6333") }
}

Write-Host "Starting port-forwards (Ctrl+C stops all)..."
$procs = @()
foreach ($j in $jobs) {
    Write-Host "  $($j.Name): kubectl $($j.Args -join ' ')"
    $procs += Start-Process -FilePath "kubectl" -ArgumentList $j.Args -PassThru -NoNewWindow
}

Write-Host ""
Write-Host "Wire qa-agent/.env while these run:"
Write-Host "  TEMPORAL_HOST=127.0.0.1:7233"
Write-Host "  INFLUXDB_URL=http://127.0.0.1:8086"
if ($IncludeQdrant) {
    Write-Host "  QDRANT_HOST=127.0.0.1"
    Write-Host "  QDRANT_PORT=6333"
    Write-Host "  QDRANT_HTTPS=false"
}
Write-Host ""
Write-Host "Public already up (no PF): https://am-dev.asrax.in/ui-test  https://temporal.asrax.in"
Write-Host "Press Ctrl+C to exit..."

try {
    while ($true) {
        $alive = $procs | Where-Object { -not $_.HasExited }
        if (-not $alive) {
            Write-Warning "All kubectl port-forward processes exited."
            break
        }
        Start-Sleep -Seconds 2
    }
} finally {
    foreach ($p in $procs) {
        if (-not $p.HasExited) {
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
