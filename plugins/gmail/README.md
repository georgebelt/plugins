# Gmail (Local MCP)

This fork replaces the OpenAI-hosted Gmail connector with the existing
[Google Workspace MCP server](https://github.com/taylorwilsdon/google_workspace_mcp)
by Taylor Wilsdon, version 2.1.0 (MIT).

The plugin packaging and launcher are maintained by georgebelt. This is a
community integration, not an official OpenAI or Google service. The launcher
does not implement Gmail API operations; the upstream server does.

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

6. Download the client JSON and save it locally at:

   `~/.config/georgebelt-gmail-mcp/client_secret.json`

7. Restrict that file to your user (`chmod 600`).

Do not put client secrets or access/refresh tokens in this repository, plugin
manifests, or chat messages. This package contains no credentials.

The developer account owns the application, but does not automatically gain
access to participating mailboxes. Do not create a separate project for each
mailbox.

## Authorize each mailbox

After the server starts, call `start_google_auth` for the desired email address
and complete Google's consent flow in the browser. Each Gmail operation must
identify `user_google_email`. Single-user fallback is deliberately disabled.

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
