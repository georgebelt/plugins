#!/usr/bin/env node
import { parseArgs } from 'node:util';
import { dataDirectory, readSettings, saveSettings } from './settings.mjs';

try {
  const { values } = parseArgs({
    options: {
      email: { type: 'string' },
      'client-id': { type: 'string' },
      check: { type: 'boolean' },
    },
  });
  const directory = dataDirectory();
  let settings;
  if (values.email !== undefined || values['client-id'] !== undefined) {
    if (!values.email || !values['client-id']) {
      throw new Error('Supply both --email and --client-id when changing the Outlook account or app.');
    }
    settings = saveSettings(directory, { email: values.email, clientId: values['client-id'] });
  } else {
    settings = readSettings(directory);
  }
  console.log(`Local Outlook configuration OK for ${settings.email}.`);
  console.log('Uses your own Microsoft application and the personal-account authority (consumers).');
  console.log('Complete sign-in with scripts/start.sh --login, then verify with scripts/start.sh --verify-login.');
  console.log('This check does not establish mailbox access.');
} catch (error) {
  console.error(`Outlook setup: ${error.code ? 'Cannot access the private configuration directory.' : error.message}`);
  process.exitCode = 1;
}
