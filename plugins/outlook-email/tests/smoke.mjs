import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import readline from 'node:readline';
import { buildInvocation, GRAPH_TOOLS } from '../scripts/settings.mjs';

// Fake app and account, disposable storage, no Microsoft sign-in or Graph calls.
const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'outlook-mcp-smoke-'));
const settings = {
  email: 'smoke@example.test',
  clientId: '11111111-2222-3333-4444-555555555555',
};
let child;
let errors;
try {
  const invocation = buildInvocation(directory, settings, process.env);
  fs.mkdirSync(invocation.cwd, { recursive: true, mode: 0o700 });
  // Test isolation only: never touch the user's OS credential store.
  invocation.env.MS365_MCP_USE_KEYTAR = '0';

  const permissions = spawnSync(invocation.command, [...invocation.args, '--list-permissions'], {
    cwd: invocation.cwd, env: invocation.env, encoding: 'utf8', timeout: 120000,
  });
  assert.equal(permissions.status, 0, permissions.stderr);
  const diagnostics = JSON.parse(permissions.stdout);
  assert.deepEqual(new Set(diagnostics.permissions), new Set(['User.Read', 'Mail.ReadWrite']));
  assert.deepEqual(diagnostics.disabledTools, []);
  console.log('PASS: pinned server requests exactly User.Read and Mail.ReadWrite.');

  const pinned = spawnSync(invocation.command, invocation.args, {
    cwd: invocation.cwd, env: invocation.env, input: '', encoding: 'utf8', timeout: 45000,
  });
  assert.notEqual(pinned.status, 0);
  assert.equal(pinned.stdout, '');
  assert.match(pinned.stderr, /expected|pinned/i);
  console.log('PASS: configured mailbox must be authorized before MCP starts.');

  // Discover the filtered schema without credentials. Removing the pin is
  // confined to this offline test; production always passes it.
  const args = [...invocation.args];
  args.splice(args.indexOf('--expected-username'), 2);
  errors = fs.openSync(path.join(directory, 'server.log'), 'w', 0o600);
  child = spawn(invocation.command, args, {
    cwd: invocation.cwd,
    env: invocation.env,
    stdio: ['pipe', 'pipe', errors],
    detached: true,
  });
  const pending = new Map();
  let nextId = 1;
  readline.createInterface({ input: child.stdout }).on('line', (line) => {
    const message = JSON.parse(line);
    const entry = pending.get(message.id);
    if (entry) {
      clearTimeout(entry.timer);
      pending.delete(message.id);
      entry.resolve(message);
    }
  });
  function request(method, params = {}) {
    const id = nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { pending.delete(id); reject(new Error(`Timed out: ${method}`)); }, 45000);
      pending.set(id, { resolve, timer });
      child.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', id, method, params })}\n`);
    });
  }
  const initialized = await request('initialize', {
    protocolVersion: '2024-11-05',
    capabilities: {},
    clientInfo: { name: 'outlook-plugin-smoke', version: '1.0' },
  });
  assert.ok(initialized.result);
  child.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' })}\n`);
  const tools = (await request('tools/list')).result.tools;
  const expected = new Set([...GRAPH_TOOLS, 'login', 'logout', 'verify-login', 'list-accounts', 'select-account', 'remove-account']);
  assert.deepEqual(new Set(tools.map((tool) => tool.name)), expected);
  for (const name of ['send-mail', 'send-draft-message', 'delete-mail-message', 'graph-batch']) {
    const denied = await request('tools/call', { name, arguments: {} });
    assert.ok(denied.error || denied.result?.isError, `${name} must be rejected`);
  }
  console.log(`PASS: MCP handshake, ${tools.length} filtered tools, and sending/deletion/batch calls rejected.`);
  console.log('No Microsoft account login or mailbox access was performed.');
} finally {
  if (child?.pid) {
    try { process.kill(-child.pid, 'SIGTERM'); } catch {}
  }
  if (errors !== undefined) fs.closeSync(errors);
  fs.rmSync(directory, { recursive: true, force: true });
}
