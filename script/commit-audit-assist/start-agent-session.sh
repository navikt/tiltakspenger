#!/usr/bin/env bash
# start-agent-session.sh
#
# Starts a Chrome instance with remote debugging enabled, using a persistent
# profile, waits for the human to log in manually, then verifies the CDP
# endpoint is reachable so an AI agent (e.g. via Playwright MCP) can attach
# to the already-authenticated session without ever handling credentials.
#
# Usage:
#   ./start-agent-session.sh [start_url]
#
# Env vars (all optional, defaults shown):
#   CDP_PORT=9222
#   PROFILE_DIR=auto (see note below)
#   CHROME_BIN=auto-detected
#
# Note on PROFILE_DIR: if the detected browser is installed as a snap
# (common for Brave/Chromium on Ubuntu), snap's AppArmor confinement
# blocks writing a custom --user-data-dir to arbitrary paths such as
# "$HOME/.cache/..." — it must live under the snap's own writable data
# dir ("$HOME/snap/<snap-name>/current/..."). This script detects that
# automatically and picks the right default; only set PROFILE_DIR
# yourself if you need to override it.

set -euo pipefail

CDP_PORT="${CDP_PORT:-9222}"
PROFILE_DIR_OVERRIDE="${PROFILE_DIR:-}"
START_URL="${1:-about:blank}"

# --- 1. Locate a Chrome/Chromium binary -------------------------------------
find_chrome() {
    local candidates=(
        brave-browser
        brave
        "/usr/bin/brave-browser"
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
        google-chrome
        google-chrome-stable
        chromium
        chromium-browser
        "/usr/bin/google-chrome"
        "/usr/bin/chromium"
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    )
    for c in "${candidates[@]}"; do
        if command -v "$c" >/dev/null 2>&1; then
            echo "$c"
            return 0
        elif [ -x "$c" ]; then
            echo "$c"
            return 0
        fi
    done
    return 1
}

CHROME_BIN="${CHROME_BIN:-$(find_chrome || true)}"
if [ -z "${CHROME_BIN:-}" ]; then
    echo "ERROR: could not find a Chrome/Chromium/Brave binary. Set CHROME_BIN explicitly." >&2
    exit 1
fi

# --- 2. Pick a profile dir that snap confinement will actually allow -------
# Snap-packaged browsers (Brave, Chromium on Ubuntu) run under AppArmor
# confinement that silently denies writes to a custom --user-data-dir
# outside their own data directory (e.g. "$HOME/.cache/..." fails with
# "Permission denied" on the SingletonLock file). Their own snap data dir
# ("$HOME/snap/<name>/current/...") is always writable, so default there
# when the browser is snap-installed.
#
# Note: "/snap/bin/<name>" is itself a symlink to "/usr/bin/snap" (the snap
# dispatcher), so don't fully resolve it with readlink -f — check the
# unresolved command path instead.
resolved_bin="$(command -v "$CHROME_BIN" 2>/dev/null || echo "$CHROME_BIN")"

if [ -z "$PROFILE_DIR_OVERRIDE" ] && [[ "$resolved_bin" == /snap/bin/* ]]; then
    snap_name="$(basename "$resolved_bin")"
    PROFILE_DIR="$HOME/snap/${snap_name}/current/agent-browser-profile"
    echo "Detected snap-confined browser (snap: ${snap_name}) — using ${PROFILE_DIR} as profile dir."
else
    PROFILE_DIR="${PROFILE_DIR_OVERRIDE:-$HOME/.cache/agent-browser-profile}"
fi

# --- 3. Guard: don't collide with the reserved nais-login port --------------
if [ "$CDP_PORT" = "8085" ]; then
    echo "ERROR: port 8085 is reserved for 'nais login' — choose a different CDP_PORT." >&2
    exit 1
fi

# --- 4. Launch Chrome with remote debugging + persistent profile -----------
mkdir -p "$PROFILE_DIR"

if curl -s -o /dev/null "http://localhost:${CDP_PORT}/json/version"; then
    echo "A CDP endpoint is already listening on port ${CDP_PORT} — reusing it."
else
    echo "Launching $CHROME_BIN with remote debugging on port ${CDP_PORT}..."
    "$CHROME_BIN" \
        --remote-debugging-port="${CDP_PORT}" \
        --user-data-dir="${PROFILE_DIR}" \
        --no-first-run \
        --no-default-browser-check \
        "${START_URL}" \
        >/tmp/agent-chrome.log 2>&1 &

    disown

    # Wait for the DevTools endpoint to come up (max ~15s)
    for i in $(seq 1 30); do
        if curl -s -o /dev/null "http://localhost:${CDP_PORT}/json/version"; then
            break
        fi
        sleep 0.5
    done
fi

if ! curl -s -o /dev/null "http://localhost:${CDP_PORT}/json/version"; then
    echo "ERROR: Chrome did not expose a CDP endpoint on port ${CDP_PORT}. Check /tmp/agent-chrome.log" >&2
    exit 1
fi

echo
echo "Chrome is running with CDP on http://localhost:${CDP_PORT}"
echo "Profile dir: ${PROFILE_DIR}  (persists login across restarts)"
echo

# --- 5. Human logs in manually ----------------------------------------------
echo ">>> Please log in to the application manually in the opened browser window."
read -r -p ">>> Press ENTER once you are logged in and ready for the agent to attach... "

# --- 6. Sanity-check the session looks authenticated ------------------------
echo "CDP endpoint confirmed reachable. Open tabs:"
curl -s "http://localhost:${CDP_PORT}/json" | python3 -c \
  "import sys, json; [print(f\"  - {t.get('title','')}: {t.get('url','')}\") for t in json.load(sys.stdin) if t.get('type') == 'page']"

echo
echo "Next step: point the agent at AGENTS.md in this folder and ask it to start"
echo "the review workflow — it will bootstrap a scoped, origin-locked session"
echo "against this CDP endpoint itself (see lib/scoped-browser-session.js)."
