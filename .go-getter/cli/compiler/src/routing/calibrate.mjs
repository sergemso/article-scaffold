// Routing calibration (decision 0017): reruns the cost model's inputs on the telemetry log and proposes changes as a draft
// decision. It never applies them: only once a human makes the draft active does `loadPolicy` read its values.
// Measured: failure rate per tier (a route's outcome is the verification records of its task class until the next route of
// that class), step shape (records carrying input and output tokens), and idle gaps over the main-session cache lifetime.
import path from 'node:path';
import { existsSync, writeFileSync } from 'node:fs';
import { readArtifacts } from '../artifacts.mjs';
import { stringifyFrontmatter } from '../frontmatter.mjs';
import { nextNumber, setIndexRow } from '../render.mjs';
import { DEFAULT_FAILURE_RATES, DEFAULT_STEP } from './cost.mjs';
import { TIERS } from './policy.mjs';

export const MIN_SAMPLES = 10;
// Smaller differences from the current values are noise, not a proposal.
const RATE_DELTA = 0.05;
const SHAPE_DELTA = 0.2;
const TTL_MS = { '5m': 5 * 60 * 1000, '1h': 60 * 60 * 1000 };
const FAILED = new Set(['fail', 'blocked', 'escalated']);
const RESULT = new Set(['pass', ...FAILED]);

const isOutcome = (r) => (r.event?.startsWith('verify:') || r.event === 'plan:done') && r.taskClass && RESULT.has(r.outcome);
const byTime = (records) => records.map((r, i) => [Date.parse(r.ts), i, r]).filter(([t]) => Number.isFinite(t)).sort((a, b) => a[0] - b[0] || a[1] - b[1]).map(([, , r]) => r);

// { small: { n, fails }, ... }: routes whose outcome is known, per tier of the routed model.
export function failureSamples(records, tiers) {
  const tierOf = (id) => TIERS.find((t) => (tiers[t] ?? []).includes(id));
  const samples = Object.fromEntries(TIERS.map((t) => [t, { n: 0, fails: 0 }]));
  const open = new Map();
  const close = (cls) => {
    const o = open.get(cls);
    if (o?.seen && o.tier) {
      samples[o.tier].n++;
      if (o.failed) samples[o.tier].fails++;
    }
    open.delete(cls);
  };
  for (const r of byTime(records)) {
    if (r.event === 'route' && r.model && r.taskClass) {
      close(r.taskClass);
      open.set(r.taskClass, { tier: tierOf(r.model), seen: false, failed: false });
    } else if (isOutcome(r) && open.has(r.taskClass)) {
      const o = open.get(r.taskClass);
      o.seen = true;
      o.failed ||= FAILED.has(r.outcome);
    }
  }
  for (const cls of [...open.keys()]) close(cls);
  return samples;
}

// Mean tokens per model call and calls per routed step, from records that carry input and output tokens.
export function stepShape(records) {
  const usage = records.filter((r) => r.event !== 'route' && Number.isInteger(r.tokens?.input) && Number.isInteger(r.tokens?.output));
  const routes = records.filter((r) => r.event === 'route' && r.model).length;
  if (!usage.length) return { n: 0 };
  const mean = (k) => Math.round(usage.reduce((s, r) => s + r.tokens[k], 0) / usage.length);
  return { n: usage.length, turns: routes ? Math.max(1, Math.round(usage.length / routes)) : null, newTokens: mean('input'), outputTokens: mean('output') };
}

// Gaps between records longer than the cache lifetime: each resumed work on a cold cache. Keeping the cache warm over a gap
// takes one read per lifetime; it would have paid when those reads cost less than the cold write saves over a warm read.
// Prefix-independent, so the saving is reported per 100k prefix tokens. Interleaved sessions shorten the gaps seen.
export function idleGaps(records, model, ttl) {
  const ttlMs = TTL_MS[ttl] ?? TTL_MS['5m'];
  const read = model.cache_read ?? model.input;
  const write = model[`cache_write_${ttl}`] ?? model.cache_write_5m ?? model.input;
  const times = byTime(records).map((r) => Date.parse(r.ts));
  let gaps = 0;
  let pays = 0;
  let saving = 0;
  for (let i = 1; i < times.length; i++) {
    const gap = times[i] - times[i - 1];
    if (gap <= ttlMs) continue;
    gaps++;
    const keepWarm = Math.floor(gap / ttlMs) * read;
    if (keepWarm < write - read) {
      pays++;
      saving += write - read - keepWarm;
    }
  }
  return { model: model.id, ttl, gaps, keepWarmWouldPay: pays, savingUsdPer100kPrefix: Number(((saving * 1e5) / 1e6).toFixed(4)) };
}

const mostFrequent = (values) => {
  const counts = new Map();
  for (const v of values) counts.set(v, (counts.get(v) ?? 0) + 1);
  return [...counts].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])))[0]?.[0];
};
const round2 = (x) => Math.round(x * 100) / 100;

/**
 * Compares measured values with the policy's current ones. Returns { failureRates, step, idle, changes, proposal }, where
 * `proposal` is the full `routing-calibration` data for a draft decision, or null when nothing differs enough to propose.
 */
export function calibrate({ records, tiers, models, policy, minSamples = MIN_SAMPLES, sessionModel = null }) {
  const currentRates = { ...DEFAULT_FAILURE_RATES, ...policy.failureRates };
  const currentStep = { ...DEFAULT_STEP, ...policy.step };
  const changes = [];

  const samples = failureSamples(records, tiers);
  const rates = { ...currentRates };
  for (const t of TIERS) {
    const { n, fails } = samples[t];
    if (n < minSamples) continue;
    const rate = round2(fails / n);
    if (Math.abs(round2(rate - currentRates[t])) >= RATE_DELTA) {
      rates[t] = rate;
      changes.push(`failure rate ${t}: ${currentRates[t]} -> ${rate} (${fails}/${n} routed steps failed verification)`);
    }
  }

  const shape = stepShape(records);
  const step = { ...currentStep };
  if (shape.n >= minSamples) {
    for (const k of ['turns', 'newTokens', 'outputTokens']) {
      if (shape[k] === null || shape[k] === undefined) continue;
      if (Math.abs(shape[k] - currentStep[k]) / currentStep[k] >= SHAPE_DELTA) {
        step[k] = shape[k];
        changes.push(`step ${k}: ${currentStep[k]} -> ${shape[k]} (${shape.n} model calls)`);
      }
    }
  }

  const ttl = policy.cacheTtl?.main ?? '5m';
  const idleId = sessionModel ?? mostFrequent(records.map((r) => r.model).filter(Boolean));
  const idleModel = models.find((m) => m.id === idleId);
  const idle = idleModel ? idleGaps(records, idleModel, ttl) : null;
  const idleAdvice = Boolean(idle && idle.keepWarmWouldPay >= minSamples);

  const proposal = changes.length
    ? { 'failure-rates': rates, step: { turns: step.turns, 'new-tokens': step.newTokens, 'output-tokens': step.outputTokens } }
    : null;
  return { failureRates: { current: currentRates, samples }, step: { current: currentStep, measured: shape }, idle, idleAdvice, changes, proposal };
}

// Writes the result as a draft decision with its INDEX row; returns its path, or null when there is nothing to propose.
// The draft supersedes the active calibration decision, if any; it is never made active here.
export function writeProposal(project, result, { date, from, to }) {
  if (!result.proposal && !result.idleAdvice) return null;
  const dir = path.join(project, 'docs', 'decisions');
  const id = `${String(nextNumber(dir)).padStart(4, '0')}-routing-calibration`;
  const prior = readArtifacts(project, ['decisions']).find((d) => d.data.status === 'active' && d.data['go-getter']?.['routing-calibration']);
  const title = `Routing uses failure rates and step shape calibrated from telemetry of ${from.slice(0, 10)} to ${to.slice(0, 10)}`;
  const data = {
    id,
    title,
    status: 'draft',
    date,
    tags: ['model-routing', 'cost', 'observability'],
    track: 'product',
    ...(prior ? { supersedes: prior.id } : {}),
    'go-getter': { 'routing-calibration': result.proposal ?? { 'failure-rates': result.failureRates.current, step: { turns: result.step.current.turns, 'new-tokens': result.step.current.newTokens, 'output-tokens': result.step.current.outputTokens } } },
  };
  const lines = result.changes.map((c) => `- ${c}`);
  if (result.idleAdvice) {
    const i = result.idle;
    lines.push(`- idle: ${i.keepWarmWouldPay} of ${i.gaps} gaps over the ${i.ttl} cache lifetime on ${i.model} would have cost less kept warm (saving ${i.savingUsdPer100kPrefix} USD per 100k prefix tokens); reconsider keep-warm advice (decision 0074, withdrawn).`);
  }
  const body = [
    '',
    '## Decision',
    '',
    `Proposed by \`go-getter routing calibrate\` (decision 0017); routing reads the values in this decision's data only once it is active${prior ? ` and ${prior.id} is superseded` : ''}.`,
    '',
    ...lines,
    '',
    '## Why',
    '',
    'Measured on this project\'s routed steps and their verification outcomes; the shipped values are approximations (fact 0025).',
    '',
    '## Tradeoffs considered',
    '',
    '- **Keep the current values**: no change, but routing keeps pricing escalation on guesses.',
    '- **Cost accepted**: a sample of recent work may not reflect future work; rerun calibration as the log grows.',
    '',
  ].join('\n');
  const file = path.join(dir, `${id}.md`);
  writeFileSync(file, stringifyFrontmatter(data, body));
  const index = path.join(dir, 'INDEX.md');
  const csv = (s) => `"${String(s).replace(/"/g, '""')}"`;
  if (existsSync(index)) setIndexRow(index, id, `${id},${csv(title)},${csv(data.tags.join(', '))},draft`);
  return path.relative(project, file);
}
