#!/usr/bin/env bash
# Start the SuperTale CE API and bundled frontend locally.
set -euo pipefail

gateway_mode=auto
while [ "$#" -gt 0 ]; do
  case "$1" in
    --gateway-mode)
      if [ "$#" -lt 2 ]; then echo '--gateway-mode requires auto, on, or off.' >&2; exit 2; fi
      gateway_mode="$2"
      shift 2
      ;;
    --gateway-mode=*) gateway_mode="${1#*=}"; shift ;;
    --help|-h) echo 'Usage: scripts/start-ce.sh [--gateway-mode auto|on|off]'; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
case "$gateway_mode" in
  auto|on|off) ;;
  *) echo '--gateway-mode must be auto, on, or off.' >&2; exit 2 ;;
esac

root_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root_dir"

api_port="${NOVELVIDEO_API_PORT:-8780}"
api_host="${NOVELVIDEO_API_HOST:-0.0.0.0}"
frontend_port="${SUPERTALE_FE_PORT:-5173}"
frontend_host="${SUPERTALE_FE_HOST:-0.0.0.0}"
api_ready_timeout="${NOVELVIDEO_API_READY_TIMEOUT:-90}"
api_pid=""
fe_pid=""
gateway_pid=""

cleanup() {
  local exit_status=$?
  local service_pid attempt running
  trap - EXIT
  # Repeated Ctrl+C must not interrupt cleanup halfway through.
  trap '' INT TERM
  for service_pid in "$fe_pid" "$api_pid" "$gateway_pid"; do
    if [ -n "$service_pid" ]; then
      # Signal the group even if its original leader has already exited.
      kill -TERM -- "-$service_pid" >/dev/null 2>&1 || true
    fi
  done
  # Give both groups time to shut down, then force any stubborn descendants
  # to exit. Never wait indefinitely on a service that ignores SIGTERM.
  for ((attempt = 0; attempt < 30; attempt++)); do
    running=false
    for service_pid in "$fe_pid" "$api_pid" "$gateway_pid"; do
      if [ -n "$service_pid" ] && kill -0 -- "-$service_pid" >/dev/null 2>&1; then
        running=true
      fi
    done
    if [ "$running" = false ]; then break; fi
    sleep 0.1
  done
  for service_pid in "$fe_pid" "$api_pid" "$gateway_pid"; do
    if [ -n "$service_pid" ]; then
      kill -KILL -- "-$service_pid" >/dev/null 2>&1 || true
      wait "$service_pid" 2>/dev/null || true
    fi
  done
  exit "$exit_status"
}

trap 'exit 130' INT
trap 'exit 143' TERM
trap cleanup EXIT

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it first: https://docs.astral.sh/uv/" >&2
  exit 2
fi

if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm is required for the bundled frontend. Install it first: corepack enable && corepack prepare pnpm@11.5.0 --activate" >&2
  exit 2
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required for the local API health check." >&2
  exit 2
fi

if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
    echo "Created .env from .env.example."
    echo "Edit .env and set NEWAPI_BASE_URL / NEWAPI_API_KEY for generation features."
  else
    echo ".env.example is missing; continuing with shell environment only." >&2
  fi
fi

if [ -f ".env" ]; then
  set -a
  # shellcheck source=/dev/null
  source ".env"
  set +a
fi

# Force standalone CE mode. Empty strings intentionally override any .env values.
export ST_EDITION=ce
export ST_CONTROL_PLANE_DSN=
export ST_REDIS_URL=
export ST_CELERY_BROKER_URL=
export ST_CELERY_RESULT_BACKEND=
export NOVELVIDEO_API_HOST="$api_host"
export NOVELVIDEO_API_PORT="$api_port"
export NOVELVIDEO_API_URL="http://127.0.0.1:${api_port}"
export DRAMACLAW_API_URL="$NOVELVIDEO_API_URL"
export SUPERTALE_API_URL="$NOVELVIDEO_API_URL"
# Make the local CE storage roots explicit so Hermes does not emit a fallback
# warning on every first chat turn. These are the same paths derived from the
# repository root when no overrides are provided.
export NOVELVIDEO_DATA_ROOT="${NOVELVIDEO_DATA_ROOT:-$root_dir}"
export NOVELVIDEO_STATE_DIR="${NOVELVIDEO_STATE_DIR:-$NOVELVIDEO_DATA_ROOT/state}"
export NOVELVIDEO_OUTPUT_DIR="${NOVELVIDEO_OUTPUT_DIR:-$NOVELVIDEO_DATA_ROOT/output}"
export NOVELVIDEO_RUNTIME_DIR="${NOVELVIDEO_RUNTIME_DIR:-$NOVELVIDEO_DATA_ROOT/runtime}"

# A source checkout does not build the credential-safe, DramaClaw-patched
# Codex runtime shipped by the Docker image. This local launcher installs
# Hermes below, so use it unless the operator explicitly configured another
# backend through either the current or legacy environment variable (and, for
# Codex, a valid CODEX_BIN).
if [ -z "${DRAMACLAW_CHAT_BACKEND:-}" ] && [ -z "${SUPERTALE_CHAT_BACKEND:-}" ]; then
  export DRAMACLAW_CHAT_BACKEND=hermes
fi

# Match sandbox_wrap's stripped, case-insensitive flag values for guidance.
sandbox_flag_enabled() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

# Explain unconfigured Linux Hermes requirements before dependency setup.
# This is guidance only: sandbox_wrap remains the authority for enforcement.
if [ "$(uname -s)" = "Linux" ] && \
   [ "${DRAMACLAW_CHAT_BACKEND:-${SUPERTALE_CHAT_BACKEND:-hermes}}" = "hermes" ] && \
   ! sandbox_flag_enabled "${SUPERTALE_ALLOW_UNSANDBOXED:-}" && \
   ! sandbox_flag_enabled "${SUPERTALE_LINUX_SANDBOX:-}"; then
  echo "Linux Hermes chat: when the sandbox is unavailable or not activated, chat is refused by default." >&2
  echo "For single-user local development only, explicitly set SUPERTALE_ALLOW_UNSANDBOXED=1 in .env or the shell to allow a warning-backed fallback." >&2
  echo "This opt-in cannot bypass sandbox requirements in EE or production. See docs/en/getting-started/installation.md." >&2
fi

if [ "${NEWAPI_API_KEY:-}" = "your_newapi_token" ] || [ -z "${NEWAPI_API_KEY:-}" ]; then
  echo "Warning: NEWAPI_API_KEY is not configured. API can start, but AI generation will fail." >&2
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Warning: ffmpeg is not on PATH. Video/audio processing may fail." >&2
fi

echo "Checking/installing dependencies with uv sync --group dev ..."
uv sync --group dev

gateway_python="$root_dir/.venv/bin/python"
gateway_plan="$("$gateway_python" scripts/local_gateway.py select --root "$root_dir" --gateway-mode "$gateway_mode")"
gateway_action="$(printf '%s' "$gateway_plan" | "$gateway_python" -c 'import json,sys; print(json.load(sys.stdin)["action"])')"
printf '%s' "$gateway_plan" | "$gateway_python" -c 'import json,sys; print(json.load(sys.stdin)["message"])'
gateway_url=""
if [ "$gateway_action" = error ]; then exit 1; fi
if [ "$gateway_action" = start ] || [ "$gateway_action" = reuse ]; then
  gateway_url="$(printf '%s' "$gateway_plan" | "$gateway_python" -c 'import json,sys; print(json.load(sys.stdin)["url"])')"
  export NEWAPI_ADMIN_BASE_URL="$gateway_url"
fi
if [ "$gateway_action" = start ]; then
  gateway_port="$(printf '%s' "$gateway_plan" | "$gateway_python" -c 'import json,sys; print(json.load(sys.stdin)["port"])')"
  if [ "$gateway_port" = "$api_port" ] || [ "$gateway_port" = "$frontend_port" ]; then
    echo "Gateway PORT conflicts with the API or frontend port." >&2
    exit 1
  fi
  # Refuse occupied ports before probing, so another service cannot look ready.
  "$gateway_python" -c 'import socket,sys; s=socket.socket(); s.bind(("", int(sys.argv[1]))); s.close()' "$gateway_port"
  "$gateway_python" scripts/local_gateway.py prepare --root "$root_dir" >/dev/null
fi

# Keep the Hermes fork in its own environment. The fork currently pins an
# older OpenAI SDK than pydantic-ai requires for Recipe text execution; putting
# both in the application .venv makes setup-hermes silently downgrade the API
# runtime and every generate_text action fails before its model request starts.
hermes_env_dir="${HERMES_ENV_DIR:-$root_dir/.cache/hermes-venv}"
export HERMES_ENV_DIR="$hermes_env_dir"
export HERMES_CLI_PATH="${HERMES_CLI_PATH:-$hermes_env_dir/bin/hermes}"
export HERMES_PYTHON="${HERMES_PYTHON:-$hermes_env_dir/bin/python}"
export HERMES_BASE_PYTHON="${HERMES_BASE_PYTHON:-$root_dir/.venv/bin/python}"
echo "Checking Hermes CLI version ..."
scripts/setup-hermes.sh

if [ ! -d "frontend/node_modules" ]; then
  echo "Installing frontend dependencies with pnpm install ..."
  (cd frontend && pnpm install)
fi

echo "Starting SuperTale CE API at http://${api_host}:${api_port}/api/v1"
echo "Health check: http://127.0.0.1:${api_port}/api/v1/config"
# Bash job control puts each background service in its own process group.
# This works on Linux and macOS without a platform-specific setsid command.
set -m
if [ "$gateway_action" = start ]; then
  "$gateway_python" scripts/local_gateway.py run --root "$root_dir" &
  gateway_pid="$!"
  gateway_deadline=$((SECONDS + api_ready_timeout))
  until curl -fsS --max-time 2 "$gateway_url/api/status" | "$gateway_python" -c 'import json,sys; sys.exit(0 if json.load(sys.stdin).get("success") is True else 1)' >/dev/null 2>&1; do
    if ! kill -0 "$gateway_pid" >/dev/null 2>&1 || [ "$SECONDS" -ge "$gateway_deadline" ]; then
      echo "Gateway exited or did not become ready: $gateway_url" >&2
      exit 1
    fi
    sleep 1
  done
  echo "Gateway ready: $gateway_url"
fi
# Dependencies are synchronized explicitly above.  `uv run` otherwise performs
# an implicit sync in this background process, which can download the 100+ MiB
# Codex binary while the readiness timeout is already counting down.
uv run --no-sync novelvideo api --host "$api_host" --port "$api_port" &
api_pid="$!"

echo "Waiting for API readiness..."
api_ready_url="http://127.0.0.1:${api_port}/api/v1/config"
api_ready_deadline=$((SECONDS + api_ready_timeout))
until curl -fsS --max-time 2 "$api_ready_url" >/dev/null 2>&1; do
  if ! kill -0 "$api_pid" >/dev/null 2>&1; then
    echo "API process exited before becoming ready." >&2
    exit 1
  fi
  if [ "$SECONDS" -ge "$api_ready_deadline" ]; then
    echo "API did not become ready within ${api_ready_timeout}s: ${api_ready_url}" >&2
    exit 1
  fi
  sleep 1
done
echo "API is ready."

echo "Starting SuperTale CE frontend at http://127.0.0.1:${frontend_port}"
echo "Frontend API target comes from frontend/.env"
(
  cd frontend
  exec pnpm dev --host "$frontend_host" --port "$frontend_port"
) &
fe_pid="$!"

echo "Press Ctrl+C to stop."

while true; do
  if [ -n "$gateway_pid" ] && ! kill -0 "$gateway_pid" >/dev/null 2>&1; then
    echo "Gateway process exited."
    exit 1
  fi
  if ! kill -0 "$api_pid" >/dev/null 2>&1; then
    echo "API process exited."
    exit 1
  fi
  if ! kill -0 "$fe_pid" >/dev/null 2>&1; then
    echo "Frontend process exited."
    exit 1
  fi
  sleep 1
done
