# Outlook Email (Local MCP)

This fork replaces the OpenAI Outlook Email connector with a local stdio MCP
server that calls Microsoft's official Graph API:

```text
Codex → local Softeria MCP server → Microsoft OAuth + Microsoft Graph
```

The adapter is community-maintained open-source software, pinned to
[`@softeria/ms-365-mcp-server@0.166.0`](https://github.com/Softeria/ms-365-mcp-server/tree/v0.166.0).
It runs on your computer. The OAuth application belongs to you: this plugin
requires your own client ID and does not use the upstream project's shared app.

## Accounts and capabilities

Configure any personal Microsoft mailbox, including Outlook.com, Hotmail, and
Live. No user's email or OAuth app ID is bundled with the plugin. This version
uses the `consumers` authority; organizational Microsoft 365 accounts need a
separate configuration and are outside this version's scope.

It supports searching and reading messages, folders and attachments, preparing
new/reply/forward drafts, and editing messages. Sending and deletion tools,
calendar tools, and generic Graph execution are excluded at the server level.
The Graph permission boundary is `User.Read` and `Mail.ReadWrite`; it does not
request `Mail.Send`. `Mail.ReadWrite` is broader than the exposed tools and is
required for creating and editing drafts.

The upstream server also registers authentication/account-management tools.
The plugin exposes only `login`, `verify-login`, and `list-accounts` from that
group. The configured username is enforced by the server.

## Setup

Install Node.js 22+ with npm/npx. The Bash launcher supports macOS and Linux.

1. Open [Microsoft Entra app registrations](https://entra.microsoft.com/).
   Register an application that supports **Personal Microsoft accounts**.
   Registration requires access to a Microsoft Entra tenant with app-registration
   permissions. The developer/tenant account can differ from the mailbox account.
2. In the application's Authentication settings, enable **Allow public client
   flows** for device-code sign-in. This local public client needs no client secret.
3. Add Microsoft Graph **delegated** permissions `User.Read` and `Mail.ReadWrite`.
   Microsoft sign-in also uses standard OpenID/offline-access permissions.
4. Copy the **Application (client) ID**, then configure the plugin:

   ```bash
   node plugins/outlook-email/scripts/configure.mjs \
     --email your-account@outlook.com \
     --client-id YOUR-APPLICATION-CLIENT-ID
   ```

5. Start sign-in:

   ```bash
   bash plugins/outlook-email/scripts/start.sh --login
   ```

   Visit the Microsoft URL shown by the command, enter its temporary code, and
   sign in with the configured mailbox. Leave the command running until it
   completes. If the code expires, run the command again.

6. Verify persisted authorization in a new process:

   ```bash
   bash plugins/outlook-email/scripts/start.sh --verify-login
   ```

   Check that the JSON response contains `"success": true`. Then connect the
   plugin in Codex and use `list-mail-folders` to verify mailbox access.

For an account or app change, repeat configuration and sign-in, then reconnect
the plugin. Every email/app pair uses its own cache; existing account caches
are preserved.

## Local configuration and credentials

Settings live at `~/.config/georgebelt-outlook-mcp/config.json`.
Set `OUTLOOK_LOCAL_MCP_DATA_DIR` to an absolute path to override the base directory;
use the same value for configuration, login, and MCP startup.

Credentials are stored in a separate account directory under that base.
The upstream server encrypts the cache with AES-256-GCM and stores its key in
the OS credential store when available. Where keytar is unavailable, it keeps
the key in a private file beside the encrypted cache. That fallback relies on
filesystem access controls rather than OS-keystore isolation. The launcher
creates private directories; upstream credential files use mode `0600`.

The launcher clears unrelated upstream Microsoft MCP environment settings, fixes
the Graph endpoint to `https://graph.microsoft.com`, and pins the mailbox, tools,
and scopes. An external `.env` in another project is not loaded. Secrets and
tokens must never be committed to this repository or pasted into chat.

## Microsoft official MCP versus Graph

Microsoft provides [Work IQ MCP](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/mcp/overview)
for Microsoft 365 organizational environments. Its documented setup requires
tenant administration and applicable billing arrangements. This plugin is for
personal mailboxes and uses the [Graph Mail API](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0),
which explicitly supports delegated personal Microsoft account access.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Missing local configuration | Run `configure.mjs` with both the mailbox and your app's client ID. |
| App not found or `invalid_grant` | Check the client ID, personal-account support, and public-client-flow setting. New registrations may take time to propagate. |
| Expected account is not cached | Complete `start.sh --login` for the configured mailbox before starting MCP. |
| Unexpected account after login | Check the Microsoft account's primary alias; confirm the intended mailbox before updating local configuration. |
| Login code expired | Run `--login` again and complete the new device-code flow. |
| Login succeeds but mailbox access fails | Check that the account has an Outlook mailbox and that the requested Graph permissions were granted. |
| No new tools in an existing Codex chat | Reconnect the plugin so Codex loads the new MCP configuration. |

## Development checks

```bash
node --test plugins/outlook-email/tests/settings.test.mjs
node plugins/outlook-email/tests/smoke.mjs
```

The smoke test checks the pinned server's effective permissions and tool surface
without signing in to Microsoft or accessing a mailbox.
