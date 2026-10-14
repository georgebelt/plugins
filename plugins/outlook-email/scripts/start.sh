#!/bin/bash
set -euo pipefail
umask 077

# Desktop apps may not inherit a shell's Homebrew PATH.
if ! command -v node >/dev/null 2>&1; then
  for outlook_bin in /opt/homebrew/bin /usr/local/bin "${HOME}/.local/bin"; do
    if [[ -x "${outlook_bin}/node" ]]; then
      export PATH="${outlook_bin}:${PATH}"
      break
    fi
  done
fi
if ! command -v node >/dev/null 2>&1 || ! command -v npx >/dev/null 2>&1; then
  echo "Outlook Local MCP requires Node.js 22+ and npm (including npx)." >&2
  exit 1
fi

outlook_script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec node "${outlook_script_dir}/run.mjs" "$@"
