import { spawn } from 'node:child_process';
import path from 'node:path';
import { dataDirectory, readSettings, privateDirectory, buildInvocation } from './settings.mjs';

try {
  if (Number(process.versions.node.split('.')[0]) < 22) {
    throw new Error('Node.js 22 or newer is required.');
  }
  const modes = new Map([
    [undefined, 'serve'],
    ['--login', 'login'],
    ['--verify-login', 'verify'],
    ['--list-permissions', 'scopes'],
  ]);
  if (process.argv.length > 3 || !modes.has(process.argv[2])) {
    throw new Error('Use start.sh with no arguments, --login, --verify-login, or --list-permissions.');
  }
  const directory = dataDirectory();
  const invocation = buildInvocation(directory, readSettings(directory), process.env, modes.get(process.argv[2]));
  privateDirectory(directory);
  privateDirectory(path.join(directory, 'accounts'));
  privateDirectory(invocation.cwd);
  const child = spawn(invocation.command, invocation.args, {
    cwd: invocation.cwd,
    env: invocation.env,
    stdio: 'inherit',
    shell: false,
  });
  for (const signal of ['SIGINT', 'SIGTERM']) {
    process.on(signal, () => child.kill(signal));
  }
  child.on('error', () => {
    console.error('Outlook Local MCP could not launch npx. Install Node.js 22+ and npm.');
    process.exitCode = 1;
  });
  child.on('exit', (code, signal) => {
    process.exitCode = code ?? (signal ? 1 : 0);
  });
} catch (error) {
  console.error(`Outlook Local MCP: ${error.code ? 'Cannot access the private configuration directory.' : error.message}`);
  process.exitCode = 1;
}
