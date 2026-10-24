// Guardrail node-floor-is-oldest-supported-lts: engines.node must be ">=<oldest LTS line not past end of life>".
import { readFileSync } from 'node:fs';
import path from 'node:path';

export const SCHEDULE_URL = 'https://raw.githubusercontent.com/nodejs/Release/main/schedule.json';

export function oldestSupportedLts(schedule, today) {
  const lines = Object.entries(schedule)
    .filter(([, v]) => v.lts && v.lts <= today && v.end > today)
    .map(([k]) => Number(k.replace(/^v/, '')))
    .filter(Number.isFinite)
    .sort((a, b) => a - b);
  return lines[0] ?? null;
}

export function floorFromEngines(range) {
  const m = /^>=\s*(\d+)(?:\.0(?:\.0)?)?$/.exec(range?.trim() ?? '');
  return m ? Number(m[1]) : null;
}

export default async function checkNodeFloor({ root }) {
  const pkg = JSON.parse(readFileSync(path.join(root, 'package.json'), 'utf8'));
  const floor = floorFromEngines(pkg.engines?.node);
  if (floor === null) {
    console.error(`check node-floor: engines.node must look like ">=N", got ${JSON.stringify(pkg.engines?.node)}`);
    return 1;
  }
  let schedule;
  try {
    const res = await fetch(SCHEDULE_URL, { signal: AbortSignal.timeout(15000) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    schedule = await res.json();
  } catch (err) {
    if (process.env.GO_GETTER_OFFLINE) {
      console.warn(`check node-floor: schedule unavailable (${err.message}); skipped because GO_GETTER_OFFLINE is set`);
      return 0;
    }
    console.error(`check node-floor: cannot fetch ${SCHEDULE_URL}: ${err.message} (set GO_GETTER_OFFLINE=1 to skip)`);
    return 1;
  }
  const today = new Date().toISOString().slice(0, 10);
  const expected = oldestSupportedLts(schedule, today);
  if (expected !== floor) {
    console.error(`check node-floor: engines.node is >=${floor} but the oldest supported LTS on ${today} is ${expected}; update package.json and fact 0010`);
    return 1;
  }
  console.log(`check node-floor: ok (>=${floor})`);
  return 0;
}
