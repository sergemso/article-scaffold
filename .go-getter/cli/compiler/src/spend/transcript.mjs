// Reads the spend a host wrote to its transcript (fact 0037) and records it as telemetry: counts, a model id and a number,
// never the transcript text. Incremental: a byte offset per transcript is kept in the gitignored state directory, and a
// message the host wrote in several lines (one per content block, same usage) counts once. Fails open: a line that does not
// parse or has another shape is skipped and counted, never an error for the hook.
import path from 'node:path';
import { createHash } from 'node:crypto';
import { closeSync, existsSync, openSync, readSync, statSync } from 'node:fs';
import { telemetryConfig } from '../telemetry/record.mjs';
import { priceRows } from './price.mjs';
import { addUsage, emitTotals, newTotals, readSpendState, writeSpendState } from './emit.mjs';

const KEEP_IDS = 64;
const count = (v) => (Number.isInteger(v) && v >= 0 ? v : 0);

// Per-host line parsers: a transcript line (parsed JSON) to { id, model, usage } or null when it carries no usage.
export const PARSERS = {
  'claude-code': (o) => {
    const m = o?.type === 'assistant' ? o.message : null;
    const u = m?.usage;
    if (!u || typeof m.id !== 'string') return null;
    const cc = u.cache_creation;
    const write = count(u.cache_creation_input_tokens);
    const write1h = cc ? count(cc.ephemeral_1h_input_tokens) : 0;
    const write5m = cc ? count(cc.ephemeral_5m_input_tokens) : write;
    return { id: m.id, model: m.model, usage: { input: count(u.input_tokens), output: count(u.output_tokens), cacheRead: count(u.cache_read_input_tokens), cacheWrite5m: write5m, cacheWrite1h: write1h } };
  },
};

// Sums the new usage lines of one transcript and writes one telemetry record per model. Returns { records, skipped }.
export function recordTranscriptSpend(project, host, transcriptPath, { now = new Date() } = {}) {
  const parse = PARSERS[host];
  if (!parse || typeof transcriptPath !== 'string' || !path.isAbsolute(transcriptPath)) return { records: 0, skipped: 0 };
  if (telemetryConfig(project).recording !== 'metadata-log' || !existsSync(transcriptPath)) return { records: 0, skipped: 0 };
  const key = createHash('sha256').update(transcriptPath).digest('hex').slice(0, 16);
  const state = readSpendState(project);
  const prior = state[key] ?? { offset: 0, ids: [] };
  const size = statSync(transcriptPath).size;
  const from = size < prior.offset ? 0 : prior.offset;
  if (size === from) return { records: 0, skipped: 0 };
  const buf = Buffer.alloc(size - from);
  const fd = openSync(transcriptPath, 'r');
  try {
    readSync(fd, buf, 0, buf.length, from);
  } finally {
    closeSync(fd);
  }
  const text = buf.toString('utf8');
  const end = text.lastIndexOf('\n') + 1; // a half-written last line is read next time
  const seen = new Set(from === prior.offset ? prior.ids : []);
  const rows = priceRows(project);
  const totals = newTotals();
  let skipped = 0;
  for (const line of text.slice(0, end).split('\n')) {
    if (!line) continue;
    let entry;
    try {
      entry = parse(JSON.parse(line));
    } catch {
      skipped++;
      continue;
    }
    if (!entry || seen.has(entry.id)) continue;
    seen.add(entry.id);
    addUsage(totals, rows, entry.model, entry.usage);
  }
  const records = emitTotals(project, host, totals, { now });
  state[key] = { offset: from + Buffer.byteLength(text.slice(0, end)), ids: [...seen].slice(-KEEP_IDS) };
  writeSpendState(project, state);
  return { records, skipped };
}
