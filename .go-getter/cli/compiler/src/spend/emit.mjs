// Shared by the spend readers: sums usage per model and writes one telemetry record per model (counts, a model id, a number).
import path from 'node:path';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { STATE_DIR, record } from '../telemetry/record.mjs';
import { FIELDS } from '../telemetry/schema.mjs';
import { priceUsage, rowFor } from './price.mjs';

const STATE = path.join(STATE_DIR, 'spend.json');

export function readSpendState(project) {
  try {
    return JSON.parse(readFileSync(path.join(project, STATE), 'utf8'));
  } catch {
    return {};
  }
}

export function writeSpendState(project, state) {
  mkdirSync(path.join(project, STATE_DIR), { recursive: true });
  writeFileSync(path.join(project, STATE), JSON.stringify(state));
}

export const newTotals = () => new Map();

// usage: { input, output, cacheRead, cacheWrite5m, cacheWrite1h }. `reported` is a USD figure the host itself gave, used when
// above zero; otherwise the usage is priced from the price facts, and a model with no row adds tokens only.
export function addUsage(totals, rows, model, usage, reported = 0) {
  const id = FIELDS.model(model) ? model : 'unknown';
  const acc = totals.get(id) ?? { usage: { input: 0, output: 0, cacheRead: 0, cacheWrite5m: 0, cacheWrite1h: 0 }, cost: 0, priced: true };
  for (const k of Object.keys(acc.usage)) acc.usage[k] += usage[k] ?? 0;
  const usd = reported > 0 ? reported : priceUsage(rowFor(rows, id), usage);
  if (usd === null) acc.priced = false;
  else acc.cost += usd;
  totals.set(id, acc);
}

export function emitTotals(project, host, totals, { now = new Date() } = {}) {
  let records = 0;
  for (const [model, acc] of totals) {
    const { input, output, cacheRead, cacheWrite5m, cacheWrite1h } = acc.usage;
    const rec = { event: 'spend', host, ...(model === 'unknown' ? {} : { model }), tokens: { input, cacheRead, cacheWrite: cacheWrite5m + cacheWrite1h, output } };
    if (acc.priced) rec.cost = Number(acc.cost.toFixed(6));
    if (record(project, rec, { now })) records++;
  }
  return records;
}
