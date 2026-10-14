---
name: gmail-setup
description: Set up or troubleshoot Gmail (Local MCP), import a Google OAuth client, and connect Gmail accounts without the OpenAI Gmail connector.
---

# Gmail setup

This plugin runs `workspace-mcp==2.1.0` locally and calls the Gmail API.
Personal Gmail accounts can authorize an External OAuth app as test users.
Use the [plugin README](../../README.md) for the Google Cloud steps and troubleshooting.
This route requires Gmail API only; do not direct users to Gmail MCP API or
Workspace Developer Preview.

1. Check local setup with `python3 <plugin-root>/scripts/configure.py --check`.
   The script reports paths and errors without displaying secret values.
   If Python is unavailable, use `uvx --from workspace-mcp==2.1.0 python` in its place.
2. For a missing OAuth client, guide the user to create a **Web application**
   client with the exact callback `http://localhost:8766/oauth2callback`.
   For a custom `GMAIL_LOCAL_MCP_PORT`, use that port in both Google and the
   MCP launch environment. Add the mailbox to the app's test users.
3. When the user supplies the local path to the downloaded JSON, import it:
   `python3 <plugin-root>/scripts/configure.py --client-secrets <path>`.
   Keep client secrets, tokens, and credential file contents out of chat and
   source control. Do not search for or display unrelated credential files.
4. Restart/reconnect this plugin's MCP server if its configuration changed.
   Use its `start_google_auth` tool with `service_name="gmail"` and the exact
   `user_google_email` chosen by the user. Show the returned authorization URL
   and let the user complete Google's consent flow. Tell the user that the link
   expires after **10 minutes**, including time spent on parent approval. Keep
   the same MCP server running while the user completes the flow. The server
   may open the browser automatically; avoid opening duplicate consent tabs.
5. Verify the connection using `list_gmail_labels` for that same email address.
   Report successful authentication only after a Gmail read succeeds. A valid
   local configuration or a generated consent URL does not prove authorization.

Each Gmail operation must pass the intended `user_google_email`. For multiple
mailboxes, authorize them separately; do not assume the first saved account is
the one the user wants. This setup does not authorize creating drafts or
changing labels as a test.

For `Invalid or expired OAuth state parameter`, generate a fresh authorization
URL with `start_google_auth` and use that new flow. Never replay a callback URL,
restore a consumed state, or disable state validation. Callback URLs contain
authorization codes; do not ask users to paste them into chat.

If the callback port is occupied, close the old Gmail MCP connection or choose a
different port and update Google's redirect URI before reconnecting. Do not
silently switch ports. A remote/headless host needs an explicit way for the
browser to reach its loopback callback; the default setup assumes a local host.
