# Gmail (Local MCP)

This fork replaces the OpenAI-hosted Gmail connector with the existing
[Google Workspace MCP server](https://github.com/taylorwilsdon/google_workspace_mcp)
by Taylor Wilsdon, version 2.1.0 (MIT).

The plugin packaging and launcher are maintained by georgebelt. This is a
community integration, not an official OpenAI or Google service. The launcher
does not implement Gmail API operations; the upstream server does.

```text
Codex → local MCP over stdio → Google OAuth + Gmail API
```

Personal `@gmail.com` accounts are supported through Google's normal OAuth
consent flow. Enable **Gmail API** (`gmail.googleapis.com`), not **Gmail MCP
API** (`gmailmcp.googleapis.com`). Google Workspace Developer Preview is not
required for this local route.

## Capabilities

- Search and read messages, threads, and attachments.
- Create new, reply, and forward drafts in Gmail.
- Read labels and organize messages.
- Connect multiple Google accounts using one OAuth client. Each account grants
  its own consent and has its own saved credentials.

The plugin enables only the listed Gmail tools and the Google authorization
tool. It does not expose email sending. Google OAuth scopes such as
`gmail.compose` and `gmail.modify` can authorize more than the enabled tools;
the draft-only boundary is enforced by server and plugin tool configuration,
not by a Google draft-only scope.

## Install

Add `https://github.com/georgebelt/plugins` as a marketplace and install
**Gmail (Local MCP)**. The same package is included in the API catalog.

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if it is not
already available. The first server start downloads the pinned upstream package.
No OpenAI connector account or Google Workspace Developer Preview enrollment
is required.

This launcher targets macOS and Linux with Bash. The browser completing OAuth
must be able to reach the local callback listener on the machine running the
plugin. Installation in a cloud-only host is not covered by this setup.

Run the plugin's **gmail-setup** skill for guided setup. The commands below run
from this repository's root. They use Python 3.9+ for the configuration helper;
if needed, replace `python3` with `uvx --from workspace-mcp==2.1.0 python`.

## One-time application setup

Use a developer or adult account that is eligible to use Google Cloud:

1. Create or select one [Google Cloud project](https://console.cloud.google.com/).
2. Enable **Gmail API**.
3. Configure Google Auth Platform branding and an **External** audience.
4. If the app is in **Testing**, add every mailbox that will authorize it under
   **Test users**.
5. Create an OAuth client of type **Web application** and add this exact
   authorized redirect URI:

   `http://localhost:8766/oauth2callback`

6. Download the client JSON, then import it without printing its contents:

   ```bash
   python3 plugins/gmail/scripts/configure.py \
     --client-secrets "/absolute/path/to/downloaded-client.json"
   ```

   This validates the Web application client and redirect URI, then saves a
   private copy at `~/.config/georgebelt-gmail-mcp/client_secret.json`
   (mode `600`). The data and credentials directories use mode `700`.

7. Check configuration and restart/reconnect the plugin's Gmail MCP server:

   ```bash
   python3 plugins/gmail/scripts/configure.py --check
   ```

   The check reads only the OAuth client configuration, not saved mailbox
   tokens. It does not verify Cloud API enablement or mailbox authorization.
   To intentionally replace a different saved OAuth client, add `--replace`
   to the import command and reauthorize each mailbox.

Do not put client secrets or access/refresh tokens in this repository, plugin
manifests, or chat messages. This package contains no credentials.

The developer account owns the application, but does not automatically gain
access to participating mailboxes. Do not create a separate project for each
mailbox.

## Authorize each mailbox

After the server starts, call `start_google_auth` for the desired email address
with both arguments:

```json
{
  "service_name": "gmail",
  "user_google_email": "your-account@gmail.com"
}
```

Complete the returned Google consent URL in your browser. Then call
`list_gmail_labels` with the same `user_google_email` to verify access. Each
Gmail operation must identify `user_google_email`. Single-user fallback is
deliberately disabled.

The authorization URL expires **10 minutes after it is generated**. Keep the
MCP server running and complete all Google sign-in, parent approval, and consent
steps within that window. If it expires, call `start_google_auth` again and use
the new URL. Reloading an old callback URL cannot restart authorization; a
callback is accepted only once.

For a supervised child's account, a parent may need to approve the application
through [Family Link](https://support.google.com/families/answer/9204736).
Availability for specific Gmail scopes must be confirmed through Google's
actual consent flow; installing this package does not override age restrictions.

Credentials are stored outside the plugin cache in:

`~/.config/georgebelt-gmail-mcp/credentials/`

If Google keeps the OAuth application in Testing, its refresh tokens for Gmail
can expire after seven days, requiring another consent flow. Consult
[Google's OAuth documentation](https://developers.google.com/identity/protocols/oauth2#expiration)
before deciding whether to change the application's publishing status.

## Updates

Refresh the `georgebelt-plugins` marketplace and install an offered update in
Codex. The dependency is pinned to 2.1.0 so a server restart does not silently
replace it with a different release. Updating the upstream server requires a
new plugin revision that changes the pin in `scripts/start.sh`.

Authentication files live outside the installed plugin and survive plugin
updates. Uninstalling the plugin does not revoke Google access; revoke access
from the corresponding Google account when it is no longer wanted.

## Optional local configuration

- `GMAIL_LOCAL_MCP_DATA_DIR`: override the private data directory.
- `GMAIL_LOCAL_MCP_PORT`: override 8766; update the Google OAuth redirect URI
  to match before authorizing.

The data directory must be an absolute path. Set these variables in the
environment that starts Codex/MCP, and use the same values for `configure.py`.
A variable exported in a separate terminal does not change an already running
desktop app's environment.

The launcher fixes the callback port and ignores unrelated upstream client,
account, service-account, and HTTP-sidecar settings. A port conflict fails
visibly instead of silently changing Google's registered redirect URI.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Missing OAuth client or invalid JSON | Run `configure.py --client-secrets` with the Web application JSON downloaded from Google. |
| `redirect_uri_mismatch` | Register exactly `http://localhost:8766/oauth2callback`, or the configured port; download and import the updated JSON. |
| `access_denied` / test user restriction | Add the mailbox under Google Auth Platform → Audience → Test users; check account or Workspace admin restrictions. |
| Gmail API disabled | Enable `gmail.googleapis.com` in the project that owns the OAuth client. |
| Callback port already in use | Close the old Gmail MCP connection, or configure a different port and register its redirect URI. |
| `Invalid or expired OAuth state parameter` | The link may have exceeded its 10-minute lifetime or the callback may already have been consumed. Run `start_google_auth` again, keep the same MCP server running, and complete the new flow within 10 minutes. Do not reload an old callback or edit its state. |
| Expired or revoked grant | Run `start_google_auth` for that mailbox and complete consent again. |
| Only setup checks pass | Run `list_gmail_labels` after consent; local validation alone does not establish mailbox access. |

## Development checks

The unit tests use temporary directories and fake client files:

```bash
python3 -m unittest discover -s plugins/gmail/tests -p 'test_*.py'
```

The protocol smoke test starts the pinned upstream server, checks the tool list,
rejects a send call, and inspects a consent URL generated from fake credentials.
Browser calls are intercepted so those fake consent URLs do not open on the
desktop. It does not log in to Google or read mail:

```bash
uvx --from workspace-mcp==2.1.0 python plugins/gmail/tests/smoke_mcp.py
```
