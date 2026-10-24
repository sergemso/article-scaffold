// Spend of the sessions a host keeps in its own store (fact 0037): the host's `session list` and `export` give a cost and token
// counts per assistant message. Read at a step boundary (`run next`, the report), not per tool call: each call starts the host
// (about two seconds). A watermark per session (the completion time of the last message counted) keeps a message from counting
// twice. Fails open: a missing command or unexpected output records nothing.
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { telemetryConfig } from '../telemetry/record.mjs';
import { priceRows } from './price.mjs';
import { addUsage, emitTotals, newTotals, readSpendState, writeSpendState } from './emit.mjs';

const COMMANDS = { opencode: 'opencode', kilo: 'kilo' };
const count = (v) => (Number.isFinite(v) && v > 0 ? Math.trunc(v) : 0);

const defaultExec = (cmd, args) => execFileSync(cmd, args, { encoding: 'utf8', timeout: 30_000, maxBuffer: 256 * 1024 * 1024, stdio: ['ignore', 'pipe', 'ignore'] });
const json = (text) => JSON.parse(text.slice(text.search(/[[{]/)));

// Sums the assistant messages completed since `since` (ISO time) in sessions of this project and records them.
export function recordSessionSpend(project, host, since, { exec = defaultExec, now = new Date() } = {}) {
  const cmd = COMMANDS[host];
  if (!cmd || telemetryConfig(project).recording !== 'metadata-log') return { records: 0, sessions: 0 };
  const from = Date.parse(since);
  const root = path.resolve(project);
  let list;
  try {
    list = json(exec(cmd, ['session', 'list', '--format', 'json', '-n', '50']));
  } catch {
    return { records: 0, sessions: 0 };
  }
  const mine = (Array.isArray(list) ? list : []).filter((s) => typeof s?.id === 'string' && s.updated >= from && typeof s.directory === 'string' && (s.directory === root || s.directory.startsWith(root + path.sep)));
  const state = readSpendState(project);
  const rows = priceRows(project);
  const totals = newTotals();
  let sessions = 0;
  for (const s of mine) {
    let exported;
    try {
      exported = json(exec(cmd, ['export', s.id]));
    } catch {
      continue;
    }
    const key = `${host}:${s.id}`;
    let mark = state[key] ?? 0;
    for (const m of exported?.messages ?? []) {
      const info = m?.info;
      const done = info?.time?.completed;
      if (info?.role !== 'assistant' || !Number.isFinite(done) || done <= mark || info.time.created < from) continue;
      const t = info.tokens ?? {};
      addUsage(totals, rows, info.modelID, { input: count(t.input), output: count(t.output) + count(t.reasoning), cacheRead: count(t.cache?.read), cacheWrite5m: count(t.cache?.write) }, Number.isFinite(info.cost) ? info.cost : 0);
      state[key] = Math.max(state[key] ?? 0, done);
    }
    sessions++;
  }
  const records = emitTotals(project, host, totals, { now });
  if (sessions) writeSpendState(project, state);
  return { records, sessions };
}
