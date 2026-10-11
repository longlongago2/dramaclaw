<!-- lang-switch -->
**English** · [简体中文](../../zh/getting-started/installation.md)

# Installation Guide

> Set up the runtime environment for DramaClaw CE on macOS / Windows / Linux. If you just want the fastest path to running it, go straight to [Quickstart](quickstart.md); this guide covers per-platform prerequisites and the two installation methods (Docker and local development).

DramaClaw CE is a single-machine service that needs **no PostgreSQL / Redis**. Docker brings up `api` + the bundled `newapi` gateway + `web`; models are served through the DramaClaw official gateway RelayClaw by default, or through the bundled gateway once you switch to Custom mode in Settings. Nothing runs models on your machine, so an ordinary machine is enough.

## Pick one of two installation methods

| Method | Best for | Prerequisites |
|---|---|---|
| **Docker (recommended)** | Deployment, trials, production self-hosting | Just Docker; ffmpeg and friends are in the image |
| **Local development (uv)** | Editing code, debugging | Python 3.11–3.12, uv, ffmpeg (installed yourself) |

> ffmpeg/ffprobe are **system dependencies**; CE does not distribute their binaries (see [ADR-0002](../../adr/0002-ffmpeg-system-dependency.md) for the reasoning). The Docker image already bundles them; for local development you install them yourself — see the [ffmpeg guide](../guides/ffmpeg.md).

---

## A. Docker (recommended)

Prerequisites: Docker + `docker compose`.

| Platform | Install |
|---|---|
| **macOS** | [Docker Desktop](https://www.docker.com/products/docker-desktop/) (works on both Apple Silicon and Intel) |
| **Windows** | Docker Desktop with the **WSL2** backend enabled (Settings → General → Use WSL2) |
| **Linux** | Docker Engine + `docker-compose-plugin` (from your distro's package manager) — Docker Compose **≥ 2.24** (`docker compose version`; the compose file uses the `env_file` long syntax) |

Once installed:

```bash
git clone https://github.com/dramaclaw/dramaclaw.git
git clone https://github.com/dramaclaw/dramaclaw-gateway.git   # bundled gateway, built from ../dramaclaw-gateway
cd dramaclaw
cp .env.example .env        # at minimum, change PROMPT_EXPORT_PASSWORD to a non-default value
docker compose up -d --build    # builds api, web and the gateway from the two checkouts
# no build? docker compose -f docker-compose.release.yml up -d   # pulls published images, no gateway clone needed
```

After it's up, open **`http://localhost:8080`** in your browser (the app UI); the REST API is at `http://localhost:8780`. Go to Settings → Model Configuration → Official Channel, paste your DC key, save, and you're ready. For the full walkthrough see [Quickstart](quickstart.md); for start/stop/backup see the [Self-Hosting Handbook](../guides/self-hosting.md).

> Windows users should clone and run inside the **WSL2 terminal** (keep it on the Linux filesystem, not under `/mnt/c/...`) to avoid volume-mount performance and line-ending issues.

---

## B. Local development (uv + Python 3.11–3.12)

### 1. Install prerequisites

| Platform | Python 3.11/3.12 | uv | ffmpeg |
|---|---|---|---|
| **macOS** | `brew install python@3.12` | `brew install uv` | `brew install ffmpeg` |
| **Windows** | [python.org](https://www.python.org/downloads/) or `winget install Python.Python.3.12` | `winget install astral-sh.uv` | `winget install Gyan.FFmpeg` (or use WSL2 and follow the Linux flow) |
| **Linux (Debian/Ubuntu)** | `apt install python3.12` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `apt install ffmpeg` |

> Python must be in the **3.11–3.12** range (`requires-python = ">=3.11,<3.13"`). uv pins dependency versions according to `uv.lock`.

### 2. Install dependencies and start

```bash
git clone https://github.com/dramaclaw/dramaclaw.git
cd dramaclaw

cp .env.example .env && $EDITOR .env     # set the gateway and key

scripts/start-ce.sh                      # install dependencies and start API + frontend
```

For native Windows PowerShell (no Bash or Docker):

```powershell
.\scripts\start-ce.ps1
```

The launcher calls `scripts/setup-hermes.ps1` to install the project fork in the
isolated `.cache/hermes-venv`. It starts the API with hot reload and the frontend
at `http://localhost:5173`. Ctrl+C stops both process trees; logs are in
`runtime/dev-*`. Use `-SkipHermes` to skip chat runtime setup, and `-SkipInstall`
when dependencies are already installed. These switches do not change the chat
backend configuration.

Both launchers accept a gateway mode, defaulting to `auto`:

```powershell
.\scripts\start-ce.ps1 -GatewayMode auto # official: skip; custom/hybrid: inspect configuration
.\scripts\start-ce.ps1 -GatewayMode on   # start the sibling gateway, or reuse a healthy instance
.\scripts\start-ce.ps1 -GatewayMode off  # start only API + frontend
```

For Bash use `scripts/start-ce.sh --gateway-mode auto`, replacing `auto` with
`on` or `off` when needed.
`auto` reads the saved model mode and gateway address without changing settings.
Official mode skips local discovery/builds. Custom and hybrid modes first check
the configured gateway's `/api/status`; a healthy existing instance is reused
and is never stopped by this launcher. An unavailable remote endpoint cannot
be replaced by a local checkout. For a matching local endpoint, the launcher
discovers `<dramaclaw parent>/dramaclaw-gateway`, builds it with Go, and starts it.
Bun is required only when its `web/dist` is missing. The port comes from `PORT`
in its environment or `.env`, then from its Go source default. Missing required
projects, port mismatches and startup failures show actionable errors; use `off`
to start the UI for configuration repair. No gateway address is invented.
The default SQLite file is `state/newapi/one-api.db`; explicit gateway database
and Redis settings are preserved. Ctrl+C stops only service trees started by
this launcher. `on` starts/reuses a gateway without changing the saved model mode.
Mode selection happens at startup; after switching from Official to a local
gateway in Settings, restart the launcher or launch with `on`.
If execution policy blocks scripts, use
`powershell -ExecutionPolicy Bypass -File .\scripts\start-ce.ps1`; this changes
policy only for that process.


Docker images and direct `novelvideo api` invocations default to Codex. Images include the
credential-safe patched Codex App Server runtime; direct source invocations need a valid `CODEX_BIN`.
`scripts/start-ce.sh` installs Hermes in an isolated environment for source development and selects
Hermes only when no chat backend is explicitly configured. `DRAMACLAW_CHAT_BACKEND` takes
precedence over the legacy `SUPERTALE_CHAT_BACKEND` variable.
CE defaults to `ST_EDITION=ce`, no-login single local user, and in-process inline task execution
(no Ray/Redis/Celery).

### Linux source-checkout Hermes sandbox choice

This applies only to Hermes; Codex does not use this sandbox switch. On Linux, Hermes
refuses chat by default when the sandbox is missing, unusable, or not activated.
When neither `SUPERTALE_ALLOW_UNSANDBOXED` nor `SUPERTALE_LINUX_SANDBOX` is enabled,
`scripts/start-ce.sh` prints configuration guidance before installing dependencies. Enabled values are `1/true/yes/on`, ignoring case and surrounding
whitespace; `0/false` does not enable a switch. Direct `novelvideo api` invocations with Hermes
explicitly selected follow the same sandbox enforcement rule.

For **single-user local development**, if you accept running Hermes without a sandbox,
explicitly add this to `.env`:

```dotenv
SUPERTALE_ALLOW_UNSANDBOXED=1
```

Or scope it to one launch:

```bash
SUPERTALE_ALLOW_UNSANDBOXED=1 scripts/start-ce.sh
```

This permits a warning-backed fallback only when the sandbox is unavailable; it does not
disable a usable sandbox. `SUPERTALE_ENV=production` or a nonempty `ST_CONTROL_PLANE_DSN`
still requires sandboxing, and the opt-in cannot override that boundary. Do not set
`SUPERTALE_LINUX_SANDBOX=1` merely to suppress the error: that switch requires a deployment
that isolates the current user's data directories through mounts.

### 3. Verify

```bash
curl http://localhost:8780/api/v1/config   # a 200 response means it's working
```

### 4. Gateway (only for Custom / Local + Official Hybrid mode)

Official mode needs nothing else. In `auto` mode, source launchers start the sibling gateway only when the saved configuration requires a matching local instance and none is healthy. For a separately managed gateway, configure its management address and database in Settings. The default CE SQLite file is `./state/newapi/one-api.db`, which is what **Initialize** in Settings writes to. To use the published image instead, run it with that directory mounted:

```bash
mkdir -p state/newapi
docker run -d --name dramaclaw-gateway -p 127.0.0.1:3000:3000 \
  -v "$PWD/state/newapi:/data" \
  claymorelab/dramaclaw-gateway:v1.0.0-rc.24-dramaclaw.1
```

or build and run the gateway from the sibling `dramaclaw-gateway` checkout with `SQLITE_PATH` pointing at that file. See [Configuring Models](configuring-models.md) for the mode setup.

---

## Optional: world features (3DGS / SHARP depth)

Heavy features such as voxel/panorama-to-3D live in the optional `world` extra; they **require a GPU and an extra toolchain** and are not installed by default:

```bash
uv sync --extra world                       # installs torch / ml-sharp / da2 and others
npm install -g @playcanvas/splat-transform  # PLY→SOG compression tool
```

Docker: `INSTALL_WORLD=1 docker compose up -d --build`. The slim base is CPU-only; GPU acceleration needs a CUDA base + nvidia runtime. Model weights are downloaded automatically at runtime, not baked into the image.

> If you're not doing any 3D/voxel workflows, you can ignore this section; plain text→finished video doesn't need it.

---

## Next steps

- Get your first result working: [Quickstart](quickstart.md)
- Connect your own model gateway: [Configuring Model Providers](configuring-models.md)
- Install/verify ffmpeg: [ffmpeg guide](../guides/ffmpeg.md)
- Running into problems: [Troubleshooting](../guides/troubleshooting.md)
