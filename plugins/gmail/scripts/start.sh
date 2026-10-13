#!/bin/bash
set -euo pipefail
umask 077

# This is a launcher for the upstream server, not a Gmail implementation.
gmail_data_dir="${GMAIL_LOCAL_MCP_DATA_DIR:-${HOME}/.config/georgebelt-gmail-mcp}"
mkdir -p "${gmail_data_dir}/credentials"
chmod 700 "${gmail_data_dir}" "${gmail_data_dir}/credentials"

export GOOGLE_CLIENT_SECRET_PATH="${gmail_data_dir}/client_secret.json"
export WORKSPACE_MCP_CREDENTIALS_DIR="${gmail_data_dir}/credentials"
export WORKSPACE_MCP_PORT="${GMAIL_LOCAL_MCP_PORT:-8766}"
export WORKSPACE_MCP_BASE_URI="http://localhost"
export GOOGLE_OAUTH_REDIRECT_URI="http://localhost:${WORKSPACE_MCP_PORT}/oauth2callback"
export OAUTHLIB_INSECURE_TRANSPORT=1
# Resolve accounts explicitly by email; never select the first stored account.
export MCP_SINGLE_USER_MODE=0
export MCP_ENABLE_OAUTH21=false
unset USER_GOOGLE_EMAIL

if command -v uvx >/dev/null 2>&1; then
  gmail_uvx="$(command -v uvx)"
elif [[ -x "${HOME}/.local/bin/uvx" ]]; then
  gmail_uvx="${HOME}/.local/bin/uvx"
else
  echo "Gmail Local MCP requires uv: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

# Keep upstream .env discovery and downloaded files outside the installed cache.
cd "${gmail_data_dir}"
exec "${gmail_uvx}" --from "workspace-mcp==2.1.0" workspace-mcp \
  --transport stdio \
  --tool-tier complete \
  --permissions gmail:drafts \
  --disabled-tools send_gmail_message
