"""Exercise the real pinned MCP server using fake OAuth data and no Google login.

Browser calls are intercepted so fake consent URLs never open on the desktop.
Run with: uvx --from workspace-mcp==2.1.0 python plugins/gmail/tests/smoke_mcp.py
"""

import asyncio
import json
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess
import tempfile
from urllib.parse import parse_qs, urlparse

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import MCPError

from test_setup import PLUGIN_ROOT, client_config


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


async def check_protocol(data_dir, env, port):
    config = client_config(port)
    client_path = data_dir / "client_secret.json"
    client_path.write_text(json.dumps(config))
    client_path.chmod(0o600)
    parameters = StdioServerParameters(
        command="/bin/bash",
        args=[str(PLUGIN_ROOT / "scripts/start.sh")],
        env=env,
    )
    manifest = json.loads((PLUGIN_ROOT / ".mcp.json").read_text())
    expected = set(manifest["mcpServers"]["gmail"]["enabled_tools"])
    with (data_dir / "server.log").open("w") as errors:
        with anyio.fail_after(60):
            async with stdio_client(parameters, errlog=errors) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    response = (await session.list_tools()).model_dump(by_alias=True)
                    tools = response["tools"]
                    actual = {tool["name"] for tool in tools}
                    assert actual == expected, (actual - expected, expected - actual)
                    assert "send_gmail_message" not in actual
                    assert "manage_gmail_label" not in actual
                    for tool in tools:
                        if tool["name"] != "start_google_auth":
                            assert "user_google_email" in tool["inputSchema"]["required"]
                    print(f"PASS: MCP handshake and exactly {len(tools)} configured tools.")

                    try:
                        denied = await session.call_tool("send_gmail_message", {})
                    except MCPError:
                        pass  # Unknown tools can be rejected at the protocol level.
                    else:
                        assert denied.model_dump(by_alias=True)["isError"]
                    print("PASS: server rejects the disabled send tool.")

                    missing = await session.call_tool(
                        "start_google_auth", {"service_name": "gmail"}
                    )
                    assert missing.model_dump(by_alias=True)["isError"]

                    states = set()
                    for email in ("first@example.test", "second@example.test"):
                        result = await session.call_tool(
                            "start_google_auth",
                            {"service_name": "gmail", "user_google_email": email},
                        )
                        payload = result.model_dump(by_alias=True)
                        assert not payload.get("isError"), "Auth URL generation failed."
                        text = "\n".join(c.get("text", "") for c in payload["content"])
                        match = re.search(r"https://accounts\.google\.com/[^\s<>\"`]+", text)
                        assert match, "No Google authorization URL returned."
                        query = parse_qs(urlparse(match.group().rstrip(")")).query)
                        assert query["client_id"] == [config["web"]["client_id"]]
                        assert query["redirect_uri"] == [f"http://localhost:{port}/oauth2callback"]
                        assert query["login_hint"] == [email]
                        assert query["access_type"] == ["offline"]
                        assert config["web"]["client_secret"] not in text
                        states.add(query["state"][0])
                        scopes = set(query["scope"][0].split())
                        assert scopes == {
                            "openid",
                            "https://www.googleapis.com/auth/userinfo.email",
                            "https://www.googleapis.com/auth/userinfo.profile",
                            "https://www.googleapis.com/auth/gmail.readonly",
                            "https://www.googleapis.com/auth/gmail.labels",
                            "https://www.googleapis.com/auth/gmail.modify",
                            "https://www.googleapis.com/auth/gmail.compose",
                        }, scopes
                    assert len(states) == 2, "Accounts must have separate OAuth flows."
                    print("PASS: explicit accounts, distinct OAuth state, fixed callback, Gmail scopes.")


def check_occupied_port(env):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        result = subprocess.run(
            ["/bin/bash", str(PLUGIN_ROOT / "scripts/start.sh")],
            env=dict(env, GMAIL_LOCAL_MCP_PORT=str(listener.getsockname()[1])),
            input="", text=True, capture_output=True, timeout=45,
        )
        assert result.returncode != 0, "An occupied callback port must fail."
        assert "No available port" in result.stderr, "Expected callback port diagnostic."
        assert not result.stdout, "Startup diagnostics must stay off the MCP stdout stream."
    print("PASS: occupied callback port fails without silently switching ports.")


async def main():
    with tempfile.TemporaryDirectory(prefix="gmail-mcp-smoke-") as temporary:
        data_dir = Path(temporary)
        port = free_port()
        # The upstream stdio auth flow calls webbrowser.open(). A successful
        # recording stub prevents desktop-browser fallback without logging URLs.
        browser_stub = data_dir / "record-browser-open"
        browser_log = data_dir / "browser-attempts"
        browser_stub.write_text(
            '#!/bin/sh\nprintf "%s\\n" blocked >> "$GMAIL_TEST_BROWSER_LOG"\n'
            "exit 0\n"
        )
        browser_stub.chmod(0o700)
        env = dict(
            os.environ,
            GMAIL_LOCAL_MCP_DATA_DIR=str(data_dir),
            GMAIL_LOCAL_MCP_PORT=str(port),
            BROWSER=shlex.join([str(browser_stub), "%s"]),
            GMAIL_TEST_BROWSER_LOG=str(browser_log),
            # Deliberately conflicting upstream settings must not redirect auth.
            PORT="1",
            USER_GOOGLE_EMAIL="wrong@example.test",
            GOOGLE_OAUTH_CLIENT_ID="wrong-client",
            GOOGLE_OAUTH_CLIENT_SECRET="wrong-secret",
            MCP_SINGLE_USER_MODE="1",
            WORKSPACE_MCP_HTTP_PORT="1",
        )
        await check_protocol(data_dir, env, port)
        assert browser_log.read_text().splitlines() == ["blocked", "blocked"], (
            "Both fake OAuth flows must use the browser interceptor."
        )
        print("PASS: both fake OAuth browser launches were intercepted.")
        check_occupied_port(env)
    print("No Google login, mailbox read, draft creation, or label change was performed.")


if __name__ == "__main__":
    asyncio.run(main())
