import { spawnSync } from 'node:child_process';
const ac = process.argv[2];
const suites = { '30': ['tests/state.test.ts'], '31': ['tests/interaction.test.ts', 'tests/api.test.ts', 'tests/polling.test.ts'] };
if (!suites[ac]) { console.error('Expected AC 30 or 31'); process.exit(2); }
const result = spawnSync(process.execPath, ['node_modules/vitest/vitest.mjs', 'run', ...suites[ac]], { stdio: 'inherit' });
process.exit(result.status ?? 1);
