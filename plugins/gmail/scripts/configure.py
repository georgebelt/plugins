#!/usr/bin/env python3
"""Validate or import a Google OAuth client without displaying credentials."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile


class SetupError(Exception):
    pass


def settings():
    data_dir = Path(
        os.environ.get("GMAIL_LOCAL_MCP_DATA_DIR")
        or Path.home() / ".config" / "georgebelt-gmail-mcp"
    )
    if not data_dir.is_absolute():
        raise SetupError("GMAIL_LOCAL_MCP_DATA_DIR must be an absolute path.")
    port = os.environ.get("GMAIL_LOCAL_MCP_PORT") or "8766"
    if not re.fullmatch(r"[1-9][0-9]{0,4}", port) or int(port) > 65535:
        raise SetupError(
            "GMAIL_LOCAL_MCP_PORT must be an integer from 1 to 65535 "
            "(without leading zeros)."
        )
    return data_dir, f"http://localhost:{port}/oauth2callback"


def read_client(path, redirect_uri):
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SetupError(
            "Cannot read valid OAuth client JSON. Download the Web application "
            "client JSON from Google Auth Platform > Clients."
        ) from None
    web = config.get("web") if isinstance(config, dict) else None
    if not isinstance(web, dict):
        raise SetupError("Create a Google OAuth client of type Web application.")
    for field in ("client_id", "client_secret"):
        if not isinstance(web.get(field), str) or not web[field].strip():
            raise SetupError(f"The OAuth client file is missing {field}.")
    if not web["client_id"].endswith(".apps.googleusercontent.com"):
        raise SetupError("The file does not contain a Google OAuth client ID.")
    if web.get("auth_uri") not in {
        "https://accounts.google.com/o/oauth2/auth",
        "https://accounts.google.com/o/oauth2/v2/auth",
    } or web.get("token_uri") != "https://oauth2.googleapis.com/token":
        raise SetupError("Download an unmodified OAuth client JSON from Google.")
    redirects = web.get("redirect_uris")
    if not isinstance(redirects, list) or redirect_uri not in redirects:
        raise SetupError(
            f"Add {redirect_uri} to the client's Authorized redirect URIs, "
            "then download the JSON again."
        )
    return config


def import_client(source, data_dir, redirect_uri, replace=False):
    config = read_client(source, redirect_uri)
    destination = data_dir / "client_secret.json"
    if destination.exists():
        try:
            existing = json.loads(destination.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = None
        if existing != config and not replace:
            raise SetupError(
                "A different client file already exists. Use --replace only "
                "when intentionally changing the OAuth application; reconnect "
                "each mailbox afterwards."
            )
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    data_dir.chmod(0o700)
    credentials = data_dir / "credentials"
    credentials.mkdir(exist_ok=True, mode=0o700)
    credentials.chmod(0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=data_dir, delete=False
        ) as stream:
            temporary = Path(stream.name)
            os.fchmod(stream.fileno(), 0o600)
            json.dump(config, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination


def check_setup(data_dir, redirect_uri):
    uvx = shutil.which("uvx")
    if not uvx and not os.access(Path.home() / ".local" / "bin" / "uvx", os.X_OK):
        raise SetupError(
            "Install uv first: https://docs.astral.sh/uv/getting-started/installation/"
        )
    client = data_dir / "client_secret.json"
    if not client.is_file():
        raise SetupError(
            f"OAuth client file is missing at {client}. "
            "Run configure.py --client-secrets /path/to/downloaded-client.json."
        )
    read_client(client, redirect_uri)
    for path in (data_dir, client, data_dir / "credentials"):
        if path.exists() and stat.S_IMODE(path.stat().st_mode) & 0o077:
            mode = "700" if path.is_dir() else "600"
            raise SetupError(
                f"Private permissions required: set mode {mode} on {path}."
            )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--client-secrets", type=Path, help="Import downloaded Web application JSON"
    )
    parser.add_argument(
        "--replace", action="store_true", help="Replace a different saved OAuth client"
    )
    parser.add_argument(
        "--check", action="store_true", help="Check local setup (also the default)"
    )
    args = parser.parse_args(argv)
    if args.replace and args.client_secrets is None:
        parser.error("--replace requires --client-secrets")
    try:
        data_dir, redirect_uri = settings()
        if args.client_secrets is not None:
            import_client(args.client_secrets.expanduser(), data_dir, redirect_uri, args.replace)
            print("OAuth client saved with private file permissions.")
        check_setup(data_dir, redirect_uri)
    except SetupError as exc:
        print(f"Gmail setup: {exc}", file=sys.stderr)
        return 1
    except OSError:
        print("Gmail setup: cannot access the private data directory.", file=sys.stderr)
        return 1
    print(f"Local configuration OK. Callback: {redirect_uri}")
    print(
        "Google API enablement and mailbox consent still require verification. "
        "Restart the Gmail MCP server, then call start_google_auth with "
        "service_name='gmail' and user_google_email set to your mailbox."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
