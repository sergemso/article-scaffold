// go-getter eval [promptfoo args]: run the behavior evals (evals/promptfooconfig.yaml) with the pinned dev dependency.
// The cases are deterministic (scripted answers, no model, no API key); promptfoo is a devDependency only.
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';

export default function evalCommand({ root, args }) {
  const bin = path.join(root, 'node_modules/.bin/promptfoo');
  if (!existsSync(bin)) {
    console.error('eval: promptfoo is not installed; run "npm install" first');
    return 2;
  }
  const config = path.join(root, 'evals/promptfooconfig.yaml');
  const run = spawnSync(bin, ['eval', '-c', config, '--no-cache', '--no-progress-bar', ...args], {
    cwd: root,
    stdio: 'inherit',
    env: { ...process.env, PROMPTFOO_DISABLE_TELEMETRY: '1', PROMPTFOO_DISABLE_UPDATE: '1' },
  });
  return run.status ?? 1;
}
