import { createHash, randomUUID } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

export const PACKAGE = '@softeria/ms-365-mcp-server@0.166.0';
export const GRAPH_TOOLS = [
  'get-current-user',
  'list-mail-messages',
  'list-mail-folders',
  'list-mail-child-folders',
  'list-mail-folder-messages',
  'get-mail-message',
  'get-mail-message-mime',
  'list-mail-attachments',
  'get-mail-attachment-content',
  'create-draft-email',
  'create-reply-draft',
  'create-reply-all-draft',
  'create-forward-draft',
  'update-mail-message',
  'add-mail-attachment',
];
export const TOOL_PATTERN = `^(${GRAPH_TOOLS.join('|')})$`;
export const SCOPES = 'User.Read Mail.ReadWrite';

export function dataDirectory(env = process.env) {
  const directory = env.OUTLOOK_LOCAL_MCP_DATA_DIR
    || path.join(os.homedir(), '.config', 'georgebelt-outlook-mcp');
  if (!path.isAbsolute(directory)) {
    throw new Error('OUTLOOK_LOCAL_MCP_DATA_DIR must be an absolute path.');
  }
  return directory;
}

export function validateSettings(value) {
  const email = typeof value?.email === 'string' ? value.email.trim().toLowerCase() : '';
  // Do not restrict domains: a Microsoft account can have a custom primary alias.
  if (email.length > 320 || !/^[^\s@/\\\x00-\x1f\x7f]+@[^\s@/\\\x00-\x1f\x7f]+\.[^\s@/\\\x00-\x1f\x7f]+$/.test(email)) {
    throw new Error('Provide the full email address of the personal Microsoft mailbox.');
  }
  const clientId = typeof value?.clientId === 'string' ? value.clientId.trim().toLowerCase() : '';
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(clientId)) {
    throw new Error('Provide your Microsoft Entra Application (client) ID, a GUID.');
  }
  return { email, clientId };
}

function requireRegularPath(file, directory = false) {
  if (!fs.existsSync(file)) return;
  const info = fs.lstatSync(file);
  if (info.isSymbolicLink() || (directory ? !info.isDirectory() : !info.isFile())) {
    throw new Error('Outlook configuration paths must be regular files and directories, not symlinks.');
  }
}

export function privateDirectory(directory) {
  requireRegularPath(directory, true);
  fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
  fs.chmodSync(directory, 0o700);
}

export function readSettings(directory) {
  const file = path.join(directory, 'config.json');
  requireRegularPath(directory, true);
  requireRegularPath(file);
  let value;
  try {
    value = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    throw new Error('Outlook setup is missing or invalid. Run configure.mjs --email <mailbox> --client-id <your-app-id>.');
  }
  return validateSettings(value);
}

export function saveSettings(directory, value) {
  const settings = validateSettings(value);
  privateDirectory(directory);
  const file = path.join(directory, 'config.json');
  requireRegularPath(file);
  const temporary = path.join(directory, `.config-${randomUUID()}.tmp`);
  try {
    fs.writeFileSync(temporary, `${JSON.stringify(settings, null, 2)}\n`, { mode: 0o600, flag: 'wx' });
    fs.renameSync(temporary, file);
  } finally {
    fs.rmSync(temporary, { force: true });
  }
  return settings;
}

export function buildInvocation(directory, settings, inheritedEnv = process.env, mode = 'serve') {
  settings = validateSettings(settings);
  const modes = {
    serve: [],
    login: ['--login'],
    verify: ['--verify-login'],
    scopes: ['--list-permissions'],
  };
  if (!Object.hasOwn(modes, mode)) throw new Error('Unknown Outlook launcher mode.');
  const profile = createHash('sha256').update(`${settings.clientId}\n${settings.email}`).digest('hex');
  const accountDirectory = path.join(directory, 'accounts', profile);
  const env = { ...inheritedEnv };
  // An unrelated Microsoft MCP setup must not replace the identity, Graph
  // endpoint, requested permissions, tool filter, or token storage.
  for (const key of Object.keys(env)) {
    if (key.startsWith('MS365_MCP_') || ['READ_ONLY', 'ENABLED_TOOLS'].includes(key)) {
      delete env[key];
    }
  }
  Object.assign(env, {
    MS365_MCP_CLIENT_ID: settings.clientId,
    MS365_MCP_CLIENT_SECRET: '',
    MS365_MCP_TENANT_ID: 'consumers',
    MS365_MCP_CLOUD_TYPE: 'global',
    MS365_MCP_GRAPH_BASE_URL: 'https://graph.microsoft.com',
    MS365_MCP_TOKEN_CACHE_PATH: path.join(accountDirectory, 'token-cache.json'),
    MS365_MCP_SELECTED_ACCOUNT_PATH: path.join(accountDirectory, 'selected-account.json'),
    MS365_MCP_REDACT_PII: 'true',
  });
  return {
    command: 'npx',
    args: [
      '--yes', '--package', PACKAGE, 'ms-365-mcp-server',
      '--enabled-tools', TOOL_PATTERN,
      '--allowed-scopes', SCOPES,
      '--expected-username', settings.email,
      ...modes[mode],
    ],
    cwd: accountDirectory,
    env,
  };
}
