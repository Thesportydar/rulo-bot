#!/usr/bin/env bash
# Instala (o reinstala) el LaunchAgent que corre el monitor cada `interval_seconds`.
# Uso: scripts/install_launchd.sh [uninstall]
set -euo pipefail

LABEL="com.rulo.monitor"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
if [[ "${1:-}" == "uninstall" ]]; then
  rm -f "$PLIST"
  echo "desinstalado"
  exit 0
fi

# launchd no ve los shims de pyenv: resolvemos el binario real
PYTHON="$(pyenv which python3 2>/dev/null || command -v python3)"
INTERVAL="$(cd "$ROOT" && "$PYTHON" -c 'import tomllib;print(tomllib.load(open("config.toml","rb")).get("interval_seconds",120))')"
mkdir -p "$ROOT/logs"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string><string>-m</string><string>rulo</string>
  </array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>StartInterval</key><integer>$INTERVAL</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$ROOT/logs/rulo.log</string>
  <key>StandardErrorPath</key><string>$ROOT/logs/rulo.err.log</string>
</dict>
</plist>
PLIST

launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "instalado: $PLIST (cada ${INTERVAL}s, python $PYTHON)"
echo "logs: $ROOT/logs/"
