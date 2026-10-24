// Prices a usage count with the project's model price facts (rows as in the `go-getter.models` lists of facts 0011 to 0013,
// USD per million tokens). A model with no row is priced at null: its tokens are still recorded.
import { readArtifacts } from '../artifacts.mjs';

const MTOK = 1e6;

export function priceRows(project) {
  const rows = new Map();
  for (const f of readArtifacts(project, ['facts'])) {
    if (f.data.status !== 'active') continue;
    for (const m of f.data['go-getter']?.models ?? []) if (typeof m.id === 'string' && Number.isFinite(m.input) && Number.isFinite(m.output)) rows.set(m.id, m);
  }
  return rows;
}

// The row for a model id as a host reports it, with or without a trailing date stamp (`-20260101`).
export function rowFor(rows, model) {
  return rows.get(model) ?? rows.get(String(model).replace(/-\d{8}$/, '')) ?? null;
}

// usage: { input, output, cacheRead, cacheWrite5m, cacheWrite1h } token counts. Returns USD, or null with no price row.
export function priceUsage(row, usage) {
  if (!row) return null;
  const write5m = row.cache_write_5m ?? row.input;
  const write1h = row.cache_write_1h ?? write5m;
  const read = row.cache_read ?? row.input;
  const usd = (usage.input ?? 0) * row.input + (usage.output ?? 0) * row.output + (usage.cacheRead ?? 0) * read + (usage.cacheWrite5m ?? 0) * write5m + (usage.cacheWrite1h ?? 0) * write1h;
  return usd / MTOK;
}
