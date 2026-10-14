import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  dataDirectory, validateSettings, saveSettings, readSettings, buildInvocation,
  GRAPH_TOOLS, TOOL_PATTERN, SCOPES, PACKAGE,
} from '../scripts/settings.mjs';

const clientId = '11111111-2222-3333-4444-555555555555';
const settings = { email: 'one@outlook.com', clientId };
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function temporary(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'outlook-settings-'));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  return directory;
}

test('accepts configurable personal mailboxes and custom aliases', () => {
  for (const email of ['one@outlook.com', 'two@hotmail.com', 'three@live.com', 'alias@example.org']) {
    assert.deepEqual(validateSettings({ email: ` ${email.toUpperCase()} `, clientId }), { email, clientId });
  }
});

test('requires an email and the owner-provided application ID', () => {
  for (const email of ['', 'person', 'a/b@example.org', 'a@example.org\ninjected']) {
    assert.throws(() => validateSettings({ email, clientId }), /email address/);
  }
  for (const invalidId of ['', 'shared', 'secret-value']) {
    assert.throws(() => validateSettings({ ...settings, clientId: invalidId }), /Application/);
  }
  assert.throws(() => dataDirectory({ OUTLOOK_LOCAL_MCP_DATA_DIR: './relative' }), /absolute/);
});

test('configuration is private, atomic, and contains only supported settings', (t) => {
  const directory = temporary(t);
  saveSettings(directory, { ...settings, accessToken: 'must-not-be-saved' });
  assert.deepEqual(readSettings(directory), settings);
  assert.equal(fs.statSync(directory).mode & 0o777, 0o700);
  assert.equal(fs.statSync(path.join(directory, 'config.json')).mode & 0o777, 0o600);
  assert.deepEqual(fs.readdirSync(directory), ['config.json']);
  saveSettings(directory, { ...settings, email: 'two@hotmail.com' });
  assert.equal(readSettings(directory).email, 'two@hotmail.com');
});

test('does not follow a configuration symlink or expose malformed file contents', (t) => {
  const directory = temporary(t);
  const target = path.join(directory, 'unrelated.json');
  fs.writeFileSync(target, 'private-token-value');
  fs.symlinkSync(target, path.join(directory, 'config.json'));
  assert.throws(() => saveSettings(directory, settings), /symlinks/);
  assert.equal(fs.readFileSync(target, 'utf8'), 'private-token-value');
  fs.unlinkSync(path.join(directory, 'config.json'));
  fs.writeFileSync(path.join(directory, 'config.json'), 'private-token-value');
  assert.throws(() => readSettings(directory), (error) => !error.message.includes('private-token-value'));
});

test('separates credential caches by mailbox and application', () => {
  const base = path.resolve(os.tmpdir(), 'outlook-cache-test');
  const a = buildInvocation(base, settings, {});
  const b = buildInvocation(base, { ...settings, email: 'two@hotmail.com' }, {});
  const c = buildInvocation(base, { ...settings, clientId: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee' }, {});
  assert.equal(new Set([a.cwd, b.cwd, c.cwd]).size, 3);
  assert.equal(buildInvocation(base, settings, {}).cwd, a.cwd);
  assert.ok(a.cwd.startsWith(path.join(base, 'accounts') + path.sep));
});

test('conflicting upstream settings cannot change provider, identity, scopes, or tools', () => {
  const invocation = buildInvocation(path.resolve(os.tmpdir(), 'outlook-env-test'), settings, {
    PATH: '/usr/bin',
    MS365_MCP_OAUTH_TOKEN: 'unrelated-token',
    MS365_MCP_GRAPH_BASE_URL: 'https://example.test',
    MS365_MCP_CLIENT_ID: 'unrelated-client',
    MS365_MCP_CLIENT_SECRET: 'unrelated-secret',
    MS365_MCP_TENANT_ID: 'organizations',
    MS365_MCP_EXTRA_SCOPES: 'Mail.Send',
    MS365_MCP_AUTH_CACHE_COMMAND: 'unrelated-command',
    MS365_MCP_EXPECTED_USERNAME: 'wrong@example.test',
    MS365_MCP_USE_KEYTAR: '0',
    MS365_MCP_ORG_MODE: 'true',
    ENABLED_TOOLS: '.*',
    READ_ONLY: 'false',
  });
  assert.equal(invocation.env.PATH, '/usr/bin');
  assert.equal(invocation.env.MS365_MCP_CLIENT_ID, clientId);
  assert.equal(invocation.env.MS365_MCP_CLIENT_SECRET, '');
  assert.equal(invocation.env.MS365_MCP_TENANT_ID, 'consumers');
  assert.equal(invocation.env.MS365_MCP_GRAPH_BASE_URL, 'https://graph.microsoft.com');
  for (const key of ['MS365_MCP_OAUTH_TOKEN', 'MS365_MCP_EXTRA_SCOPES', 'MS365_MCP_AUTH_CACHE_COMMAND', 'ENABLED_TOOLS', 'MS365_MCP_USE_KEYTAR']) {
    assert.equal(invocation.env[key], undefined);
  }
  assert.equal(invocation.args[invocation.args.indexOf('--expected-username') + 1], settings.email);
  assert.equal(invocation.args[invocation.args.indexOf('--enabled-tools') + 1], TOOL_PATTERN);
  assert.equal(invocation.args[invocation.args.indexOf('--allowed-scopes') + 1], SCOPES);
  assert.ok(invocation.args.includes(PACKAGE));
  const filter = new RegExp(TOOL_PATTERN);
  for (const blocked of ['send-mail', 'send-draft-message', 'reply-mail-message', 'delete-mail-message', 'graph-batch', 'download-bytes']) {
    assert.equal(filter.test(blocked), false);
  }
});

test('plugin exposes only the intended Graph and authentication tools', () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, '.mcp.json'), 'utf8'));
  assert.deepEqual(
    new Set(manifest.mcpServers['outlook-email'].enabled_tools),
    new Set([...GRAPH_TOOLS, 'login', 'verify-login', 'list-accounts']),
  );
  const plugin = JSON.parse(fs.readFileSync(path.join(root, '.codex-plugin/plugin.json'), 'utf8'));
  assert.equal(plugin.apps, undefined);
  assert.equal(fs.existsSync(path.join(root, '.app.json')), false);
});

test('launcher fails before dependency execution when configuration is missing', (t) => {
  const directory = temporary(t);
  const result = spawnSync('/bin/bash', [path.join(root, 'scripts/start.sh')], {
    env: { ...process.env, OUTLOOK_LOCAL_MCP_DATA_DIR: directory },
    encoding: 'utf8',
    timeout: 5000,
  });
  assert.equal(result.status, 1);
  assert.equal(result.stdout, '');
  assert.match(result.stderr, /configure\.mjs/);
});
