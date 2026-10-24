// Tier 3: host settings files that exist have prompt logging switched off where the project's governance decision requires it.
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { packageCapabilities, promptLoggingTargets } from '../../governance.mjs';

export default function promptLoggingOff({ project }) {
  const caps = packageCapabilities();
  const problems = [];
  for (const host of promptLoggingTargets(project, caps, Object.keys(caps))) {
    const { file, key } = caps[host].telemetry.promptLogOff;
    const settings = path.join(project, file);
    if (!existsSync(settings)) continue;
    let value = JSON.parse(readFileSync(settings, 'utf8'));
    for (const k of key) value = value?.[k];
    if (value !== false) problems.push(`${file} does not set ${key.join('.')} to false`);
  }
  return problems.length ? { ok: false, message: `${problems.join('; ')}; run "go-getter apply"` } : { ok: true };
}
