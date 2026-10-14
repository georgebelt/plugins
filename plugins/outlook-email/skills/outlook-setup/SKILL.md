---
name: outlook-setup
description: Configure and troubleshoot the local Outlook Email MCP plugin using a personal Microsoft mailbox and the user's own Microsoft Entra OAuth application.
---

# Outlook setup

This plugin runs Softeria's open-source Microsoft 365 MCP server locally.
It connects directly to Microsoft Graph and requires the user's own OAuth app.
It is not a Microsoft-authored MCP server or an OpenAI connector.
Use the [README](../../README.md) for prerequisites and Microsoft app setup.

1. Ask for the intended personal Microsoft mailbox and Application (client) ID
   when they are missing. Do not hard-code a person's email into the plugin.
2. Save the local settings:
   `node <plugin-root>/scripts/configure.mjs --email <mailbox> --client-id <app-id>`.
   The app must support personal Microsoft accounts and enable public client
   flows. No client secret is required. Never substitute a third-party app ID.
3. Run `bash <plugin-root>/scripts/start.sh --login`. Show the Microsoft device
   sign-in URL and temporary code from that process. Keep the login process
   running while the user signs in and grants consent. Use the actual displayed
   expiry when available; an expired code requires a fresh login flow.
4. Read the command's result. Exit code zero alone is insufficient: the returned
   `success` must be true. The authenticated username must match the configured
   mailbox. If Microsoft returns a different primary alias, explain the mismatch
   and confirm the intended account before changing the configuration.
5. Run `--verify-login` in a new process to confirm persisted authorization.
   Reconnect the MCP plugin and call `list-mail-folders` with a small result limit.
   Report the mailbox connected only after a Graph read succeeds. Do not create
   a draft or alter a message to test connectivity.

The mailbox and app ID are stored in the user's private configuration directory.
Each email/app pair has a separate token cache. Switching mailboxes means running
configuration and login again, then reconnecting the MCP server.

Keep token caches, refresh tokens, client secrets, and callback codes out of
chat and source control. A setup check or installed plugin does not prove that
the Microsoft account has been authorized.
