# QA Portal — Windows thin installer

Postman-style desktop client for the QA operator portal. Same Flutter UI as the web portal; talks to remote (or local) **qa-agent** over HTTPS. The Python backend is **not** bundled.

## Share with teammates (recommended)

One URL per environment:

| Env | Get app page |
|-----|----------------|
| Preprod | https://am-preprod.asrax.in/qa/download |
| Prod | https://am.asrax.in/qa/download |
| Dev | https://am-dev.asrax.in/qa/download |

The page shows:

- Current **version**
- **Download for Windows** (`QAPortal-win-Setup.exe`)
- **Open in browser** (same env’s `/qa/ui`)

Or from the portal: **Profile → Get Windows app**.

## Install

1. Open the download page for your env (above).
2. Click **Download for Windows**.
3. Run Setup — installs under `%LocalAppData%\com.asrax.qaportal\` and launches **QA Portal**.

GitHub Releases (optional / CI): https://github.com/AM-Portfolio/am-qa-agents/releases (tags `qa-portal-v*`).

## Point at an API

Release builds default to **preprod**: `https://am-preprod.asrax.in/qa`.

In the running app, use the header **connection chip / Environments** to switch Local ↔ Contabo dig ↔ Preprod without rebuilding (overrides bake-time `API_BASE`).

| Goal | How |
|------|-----|
| Chrome + local `:8150` | `npm run run:chrome:local` (Network host = `localhost:8150`) |
| Chrome + Contabo dig | `npm run run:dev` (Network host = `am-dev.asrax.in`) |
| Local qa-agent `:8150` (Windows) | `npm run run:windows` |
| Preprod | Default release / `npm run run:windows:preprod` |
| Dev cluster (Windows) | `npm run run:windows:dev` |

Rebuild a custom release:

```powershell
cd qa-portal-ui
npm run build:windows:local   # or build:windows for preprod
npm run pack:windows
```

Artifacts:

- Velopack feed: `dist/windows/Releases/`
- Download page bake: `download/desktop/QAPortal-win-Setup.exe` + `download/desktop-release.json`

## Updates

On launch, the installed app asks Velopack `Update.exe` to check the GitHub Releases feed (`VELOPACK_URL`, default `…/releases/latest/download`). If a newer pack is published, it downloads and restarts.

## Dev prerequisites (local Windows build)

- Flutter stable with Windows desktop enabled
- Visual Studio **Desktop development with C++** (+ ATL for some plugins)
- Developer Mode (symlinks) for plugins
- .NET 8 SDK + `dotnet tool install -g vpk` (for packing only)

```powershell
npm run get
npm run run:windows          # needs local qa-agent on :8150
# Terminal A: npm start from am-qa-agents root
```

Local download page (with backend running):

`http://localhost:8150/download/`

CI builds on `windows-latest` via `.github/workflows/qa-portal-windows.yml` (tag `qa-portal-v*` or workflow_dispatch). Image bake pulls Setup into `/qa/download` via `.github/workflows/qa-agent.yml`.

## Code signing

Optional repo secrets (recommended for SmartScreen):

| Secret | Meaning |
|--------|---------|
| `WINDOWS_CERT_PFX_B64` | Base64 of the Authenticode `.pfx` |
| `WINDOWS_CERT_PASSWORD` | PFX password |

Without them, CI still publishes an unsigned stub (operators may see SmartScreen warnings).

## Release checklist

1. Bump `qa-portal-ui/pubspec.yaml` version (e.g. `0.1.1+1`).
2. Tag: `git tag qa-portal-v0.1.1 && git push origin qa-portal-v0.1.1`
3. Wait for **Publish — qa-portal-ui Windows** workflow (Setup + GH Release).
4. Deploy / rebuild **am-qa-agents** image so `/qa/download` serves the new Setup.
5. Share `https://am-preprod.asrax.in/qa/download` (or prod/dev equivalent).
