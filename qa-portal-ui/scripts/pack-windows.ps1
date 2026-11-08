# Pack Flutter Windows release with Velopack (thin Setup.exe + update feed).
# Prerequisites: flutter build windows --release, .NET SDK, `dotnet tool install -g vpk`
# Usage:  .\scripts\pack-windows.ps1
#         .\scripts\pack-windows.ps1 -SkipBuild -Version 0.1.0

[CmdletBinding()]
param(
    [string]$Version = "",
    [switch]$SkipBuild,
    [string]$ApiBase = "https://am-preprod.asrax.in/qa",
    [string]$RootPath = "/qa",
    [string]$VelopackUrl = "https://github.com/AM-Portfolio/am-qa-agents/releases/latest/download",
    [string]$CertPfx = "",
    [string]$CertPassword = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Get-PubspecVersion {
    $line = Get-Content (Join-Path $Root "pubspec.yaml") | Where-Object { $_ -match '^version:\s*' } | Select-Object -First 1
    if (-not $line) { throw "Could not read version from pubspec.yaml" }
    $raw = ($line -replace '^version:\s*', '').Trim()
    # pubspec is 0.1.0+1 - Velopack wants semver2 without build metadata +N
    return ($raw -split '\+')[0]
}

if (-not $Version) {
    $Version = Get-PubspecVersion
}

Write-Host "QA Portal Windows pack version=$Version"

if (-not $SkipBuild) {
    Write-Host "Building Flutter Windows release..."
    flutter build windows --release `
        --dart-define="API_BASE=$ApiBase" `
        --dart-define="ROOT_PATH=$RootPath" `
        --dart-define="VELOPACK_URL=$VelopackUrl"
}

$PackDir = Join-Path $Root "build\windows\x64\runner\Release"
if (-not (Test-Path (Join-Path $PackDir "QAPortal.exe"))) {
    throw "Missing QAPortal.exe under $PackDir - run flutter build windows first"
}

$vpk = Get-Command vpk -ErrorAction SilentlyContinue
if (-not $vpk) {
    Write-Host "Installing vpk global tool..."
    dotnet tool update -g vpk
}

$OutDir = Join-Path $Root "dist\windows\Releases"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$Icon = Join-Path $Root "windows\runner\resources\app_icon.ico"
$packArgs = @(
    "pack",
    "--packId", "com.asrax.qaportal",
    "--packVersion", $Version,
    "--packDir", $PackDir,
    "--mainExe", "QAPortal.exe",
    "--packTitle", "QA Portal",
    "--runtime", "win-x64",
    "--outputDir", $OutDir
)
if (Test-Path $Icon) {
    $packArgs += @("--icon", $Icon)
}

Write-Host "vpk $($packArgs -join ' ')"
& vpk @packArgs
if ($LASTEXITCODE -ne 0) { throw "vpk pack failed with exit $LASTEXITCODE" }

# Stable download name for operators / GH latest/download link
$Setup = Get-ChildItem $OutDir -Filter "*Setup.exe" | Select-Object -First 1
$StableSetup = Join-Path $OutDir "QAPortal-win-Setup.exe"
if ($Setup) {
    Copy-Item $Setup.FullName $StableSetup -Force
    Write-Host "Stub installer: $StableSetup"
}

# Bake into /download page path (served by qa-agent at /qa/download)
$DownloadDesktop = Join-Path $Root "download\desktop"
New-Item -ItemType Directory -Force -Path $DownloadDesktop | Out-Null
if (Test-Path $StableSetup) {
    Copy-Item $StableSetup (Join-Path $DownloadDesktop "QAPortal-win-Setup.exe") -Force
    Write-Host "Download page Setup: $DownloadDesktop\QAPortal-win-Setup.exe"
}

$releasedAt = (Get-Date).ToString("yyyy-MM-dd")
$notes = "Windows thin installer for QA Portal. Talks to this environment's qa-agent API."
@{
    version          = $Version
    releasedAt       = $releasedAt
    windowsSetup     = "desktop/QAPortal-win-Setup.exe"
    windowsSetupName = "QAPortal-win-Setup.exe"
    webPath          = "../ui/"
    notes            = $notes
} | ConvertTo-Json | Set-Content -Path (Join-Path $Root "download\desktop-release.json") -Encoding utf8
# Root copy for API fallback / docs (paths relative to portal root)
@{
    version          = $Version
    releasedAt       = $releasedAt
    windowsSetup     = "download/desktop/QAPortal-win-Setup.exe"
    windowsSetupName = "QAPortal-win-Setup.exe"
    webPath          = "ui/"
    notes            = $notes
} | ConvertTo-Json | Set-Content -Path (Join-Path $Root "desktop-release.json") -Encoding utf8
Write-Host "Updated desktop-release.json version=$Version"

if ($CertPfx -and (Test-Path $CertPfx)) {
    Write-Host "Authenticode signing..."
    $signables = Get-ChildItem $OutDir -Include "*.exe", "*.nupkg" -Recurse -File
    foreach ($f in $signables) {
        $sigArgs = @(
            "sign", "/fd", "SHA256", "/tr", "http://timestamp.digicert.com", "/td", "SHA256",
            "/f", $CertPfx
        )
        if ($CertPassword) { $sigArgs += @("/p", $CertPassword) }
        $sigArgs += $f.FullName
        & signtool @sigArgs
        if ($LASTEXITCODE -ne 0) { throw "signtool failed for $($f.Name)" }
    }
} else {
    Write-Host "Skipping code sign (no -CertPfx). Set WINDOWS_CERT_PFX in CI for SmartScreen."
}

Write-Host "Done. Upload contents of $OutDir to the GitHub Release."
Get-ChildItem $OutDir | Format-Table Name, Length
