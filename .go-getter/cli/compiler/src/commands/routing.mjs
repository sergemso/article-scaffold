// go-getter routing calibrate [--project <dir>] [--min-samples <n>] [--session-model <id>] [--dry-run]
//   Reruns the cost model's inputs on the telemetry log and prints what it measured as JSON; when a value differs enough,
//   writes the proposal as a draft decision (never active: a human decides, decision 0017). --dry-run writes nothing.
import path from 'node:path';
import { calibrate, writeProposal, MIN_SAMPLES } from '../routing/calibrate.mjs';
import { loadPolicy, loadRoutingFacts } from '../routing/policy.mjs';
import { readLog } from '../telemetry/record.mjs';

export default function routingCommand({ args }) {
  const [sub, ...rest] = args;
  const opt = { project: process.cwd() };
  let dryRun = false;
  for (let i = 0; i < rest.length; i++) {
    if (rest[i] === '--dry-run') dryRun = true;
    else if (rest[i].startsWith('--')) opt[rest[i].slice(2)] = rest[++i];
    else opt.unexpected = rest[i];
  }
  const minSamples = opt['min-samples'] === undefined ? MIN_SAMPLES : Number.parseInt(opt['min-samples'], 10);
  if (sub !== 'calibrate' || opt.unexpected || !(minSamples > 0)) {
    console.error('usage: go-getter routing calibrate [--project <dir>] [--min-samples <n>] [--session-model <id>] [--dry-run]');
    return 2;
  }
  const project = path.resolve(opt.project);
  const policy = loadPolicy(project);
  if (!policy) {
    console.error('routing calibrate: the cost-routing pack is not adopted here');
    return 2;
  }
  const records = readLog(project);
  const { models, tiers } = loadRoutingFacts(project);
  const result = calibrate({ records, tiers, models, policy, minSamples, sessionModel: opt['session-model'] ?? null });
  const span = records.map((r) => r.ts).filter(Boolean).sort();
  const today = new Date().toISOString().slice(0, 10);
  const draft = dryRun || !span.length ? null : writeProposal(project, result, { date: today, from: span[0], to: span.at(-1) });
  console.log(JSON.stringify({ records: records.length, ...result, draft }, null, 2));
  return 0;
}
