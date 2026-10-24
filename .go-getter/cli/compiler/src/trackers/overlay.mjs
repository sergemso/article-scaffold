// What every tracker source shares (decisions 0117 and 0119): overlaying an issue's state on the file WorkSource's steps, the
// cache of what was read, and cleaning the text an issue returns. A tracker is an adapter:
//   { id, refOf(step) -> { ref, cacheKey, label } | null, fetch(items) -> Map(cacheKey -> { state, title } | null) }
// `refOf` says whether the step names one of this tracker's issues; `cacheKey` is the issue's identity (null when it cannot be
// told, say a GitHub `#12` in a project with no GitHub origin); `fetch` throws when the tracker cannot be reached and returns
// null for an issue that does not exist. Its state is `open`, `in progress`, `done` or `moved`.
import { mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { STATE_DIR } from '../telemetry/record.mjs';
import { findings } from '../secrets/patterns.mjs';

const TITLE_MAX = 120;
const CACHE_FILE = 'tracker-cache.json';

// Issue text as it may be kept and shown: one line, no control characters, secrets replaced, cut short (decision 0119).
export function cleanTitle(text) {
  let t = String(text ?? '').replace(/[\p{Cc}\p{Zl}\p{Zp}]+/gu, ' ').trim();
  for (const f of findings(t).sort((a, b) => b.index - a.index)) t = `${t.slice(0, f.index)}[redacted]${t.slice(f.index + f.length)}`;
  return t.length > TITLE_MAX ? `${t.slice(0, TITLE_MAX - 1)}…` : t;
}

const cachePath = (project) => path.join(project, STATE_DIR, CACHE_FILE);
export function readCache(project) {
  try {
    const cache = JSON.parse(readFileSync(cachePath(project), 'utf8'));
    return cache?.version === 1 && cache.issues && typeof cache.issues === 'object' ? cache.issues : {};
  } catch {
    return {};
  }
}
export function writeCache(project, issues) {
  try {
    mkdirSync(path.join(project, STATE_DIR), { recursive: true });
    const file = cachePath(project);
    writeFileSync(`${file}.tmp`, `${JSON.stringify({ version: 1, issues }, null, 2)}\n`);
    renameSync(`${file}.tmp`, file);
  } catch {
    // a cache that cannot be written only costs the stale fallback
  }
}

// The state a step shows given its issue's state and the plan file's: the issue decides, and a disagreement is reported
// (`mismatch`), never changed. An open issue cannot be done; a tracker that says in progress is ahead of a pending marker.
export function effective(issueState, fileState) {
  if (issueState === 'done' && fileState !== 'done') return { state: 'done', mismatch: `the issue is closed but the plan marks the step ${fileState}` };
  if (issueState === 'moved' && fileState !== 'moved') return { state: 'moved', mismatch: `the issue was closed as not planned but the plan marks the step ${fileState}` };
  if (issueState === 'open' && fileState === 'done') return { state: 'in progress', mismatch: 'the plan marks the step done but its issue is open' };
  if (issueState === 'in progress' && fileState === 'done') return { state: 'in progress', mismatch: 'the plan marks the step done but its issue is not' };
  if (issueState === 'in progress' && fileState !== 'in progress' && fileState !== 'moved') return { state: 'in progress' };
  return null;
}

// `steps` (plain step data) with each step the adapter claims overlaid with { issueState, state, fileState?, mismatch? }.
// A step with no issue of this tracker is returned as it is, and nothing is fetched when no step has one.
export async function overlay({ project, steps, adapter, now = () => new Date() }) {
  const claimed = new Map();
  for (const s of steps) {
    const found = adapter.refOf(s);
    if (found) claimed.set(s.id, found);
  }
  if (!claimed.size) return steps;
  let live = null;
  let problem;
  try {
    live = await adapter.fetch([...claimed.values()]);
  } catch (err) {
    problem = err?.safe ? String(err.message) : undefined; // only messages written to name no secret are shown
  }
  const cache = readCache(project);
  const stamp = now().toISOString();
  const out = steps.map((s) => {
    const found = claimed.get(s.id);
    if (!found) return s;
    const key = found.cacheKey;
    const read = key && live ? live.get(key) : undefined;
    let issueState;
    if (read) {
      issueState = { tracker: adapter.id, ref: key, state: read.state, title: cleanTitle(read.title), fetchedAt: stamp, stale: false };
      cache[key] = { state: issueState.state, title: issueState.title, fetchedAt: stamp };
    } else if (read === null) {
      issueState = { tracker: adapter.id, ref: key, state: 'unknown', stale: false, error: 'the issue was not found' };
    } else if (key && cache[key]) {
      issueState = { tracker: adapter.id, ref: key, state: cache[key].state, title: cache[key].title, fetchedAt: cache[key].fetchedAt, stale: true, ...(problem ? { error: problem } : {}) };
    } else {
      issueState = { tracker: adapter.id, ref: key ?? found.label, state: 'unknown', stale: true, ...(problem ? { error: problem } : {}) };
    }
    const result = { ...s, issueState };
    const shown = effective(issueState.state, s.state);
    if (shown) Object.assign(result, { state: shown.state, fileState: s.state, ...(shown.mismatch ? { mismatch: shown.mismatch } : {}) });
    return result;
  });
  if (live) writeCache(project, cache);
  return out;
}
