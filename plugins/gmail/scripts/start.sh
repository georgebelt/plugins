#!/bin/bash
set -euo pipefail
umask 077

# This is a launcher for the upstream server, not a Gmail implementation.
gmail_data_dir="${GMAIL_LOCAL_MCP_DATA_DIR:-${HOME}/.config/georgebelt-gmail-mcp}"
case "${gmail_data_dir}" in
  /*) ;;
  *)
    echo "GMAIL_LOCAL_MCP_DATA_DIR must be an absolute path." >&2
    exit 1
    ;;
esac

gmail_port="${GMAIL_LOCAL_MCP_PORT:-8766}"
if [[ ! "${gmail_port}" =~ ^[1-9][0-9]{0,4}$ ]] || (( gmail_port > 65535 )); then
  echo "GMAIL_LOCAL_MCP_PORT must be an integer from 1 to 65535 (without leading zeros)." >&2
  exit 1
fi

mkdir -p "${gmail_data_dir}/credentials"
chmod 700 "${gmail_data_dir}" "${gmail_data_dir}/credentials"

# This plugin owns its Google client, account selection, and local transport.
# An unrelated Workspace MCP installation must not override these settings.
unset PORT USER_GOOGLE_EMAIL GOOGLE_OAUTH_CLIENT_ID GOOGLE_OAUTH_CLIENT_SECRET
unset GOOGLE_CLIENT_SECRETS GOOGLE_SERVICE_ACCOUNT_KEY_FILE GOOGLE_SERVICE_ACCOUNT_KEY_JSON
unset WORKSPACE_MCP_HTTP_PORT WORKSPACE_EXTERNAL_URL
export EXTERNAL_OAUTH21_PROVIDER=false
export TRUST_GATEWAY_IDENTITY=false
export WORKSPACE_MCP_STATELESS_MODE=false
export WORKSPACE_MCP_CREDENTIAL_STORE_BACKEND=local_directory
export GOOGLE_CLIENT_SECRET_PATH="${gmail_data_dir}/client_secret.json"
export WORKSPACE_MCP_CREDENTIALS_DIR="${gmail_data_dir}/credentials"
export WORKSPACE_MCP_PORT="${gmail_port}"
export WORKSPACE_MCP_HOST="127.0.0.1"
# Google Web application redirect URIs must match exactly. Fail on collisions
# rather than move the listener away from the registered callback URL.
export WORKSPACE_MCP_PORT_FALLBACK_COUNT=0
export WORKSPACE_MCP_BASE_URI="http://localhost"
export GOOGLE_OAUTH_REDIRECT_URI="http://localhost:${WORKSPACE_MCP_PORT}/oauth2callback"
export OAUTHLIB_INSECURE_TRANSPORT=1
# Resolve accounts explicitly by email; never select the first stored account.
export MCP_SINGLE_USER_MODE=0
export MCP_ENABLE_OAUTH21=false

if command -v uvx >/dev/null 2>&1; then
  gmail_uvx="$(command -v uvx)"
elif [[ -x "${HOME}/.local/bin/uvx" ]]; then
  gmail_uvx="${HOME}/.local/bin/uvx"
else
  echo "Gmail Local MCP requires uv: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

# Keep logs and downloaded files outside the installed plugin cache.
cd "${gmail_data_dir}"
exec "${gmail_uvx}" --from "workspace-mcp==2.1.0" workspace-mcp \
  --transport stdio \
  --tool-tier complete \
  --permissions gmail:drafts \
  --disabled-tools send_gmail_message manage_gmail_label
