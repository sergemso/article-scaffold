// Plan reader (decision 0069, plan A.2): parses a Markdown plan's steps deterministically and offers the next ones.
// A step is `### <id> <title> — [<marker>]` followed by field lines: one metadata line `Class: … · Needs: … · Check: …`
// and text lines such as `Do:` and `Done-when:`. Every field is optional; other lines are prose and ignored.
// `start` and `done` write only a step's marker; the file WorkSource (trackers/file-source.mjs) also sets a marker and appends steps.
import path from 'node:path';
import { readdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { execFileSync, spawnSync } from 'node:child_process';
import { CLASSES } from './verify.mjs';
import { TIERS, EFFORTS } from './routing/policy.mjs';
import { DATA_CLASSES } from './routing/eligibility.mjs';
import { newWorktree } from './worktree.mjs';
import { parseRef, refId } from './trackers/refs.mjs';
import { recordQuietly } from './telemetry/record.mjs';
import { checkpointBeforeStep } from './checkpoint-trigger.mjs';
import { cleanGitEnv } from './git-env.mjs';

export const MARKERS = { ' ': 'pending', '~': 'in progress', x: 'done', '!': 'blocked', '>': 'moved' };
export const STATE_MARKER = Object.fromEntries(Object.entries(MARKERS).map(([marker, state]) => [state, marker]));
export const PLAN_DIR = path.join('docs', 'plans');
const META = { Class: CLASSES, Effort: EFFORTS, Tier: TIERS, Data: DATA_CLASSES, Needs: null, Check: null, Issue: null, Human: null };
// Dotted alphanumeric (`7.1`, `L.7`), with a hyphen allowed between groups for a tracker key (`PROJ-123`).
export const ID = /^[0-9A-Za-z]+([.-][0-9A-Za-z]+)*$/;
const HEADING = /^###\s+(\S+)\s+(.+?)\s+—\s+\[(.)\]\s*(.*)$/;
const PARALLEL = '‖';
const MAX_OPTIONS = 4;

const stripTicks = (s) => s.replace(/^`(.*)`$/, '$1');

export function parsePlan(text, file = 'plan') {
  const steps = [];
  const problems = [];
  let step = null;
  text.split('\n').forEach((line, i) => {
    const at = `${file}:${i + 1}`;
    if (/^#{1,2}\s/.test(line) || /^---\s*$/.test(line)) {
      step = null;
      return;
    }
    if (line.startsWith('### ')) {
      const m = HEADING.exec(line);
      if (!m) {
        problems.push(`${at}: heading is not a step (\`### <id> <title> — [<marker>]\`)`);
        step = null;
        return;
      }
      const [, id, rawTitle, marker, rest] = m;
      if (!ID.test(id)) problems.push(`${at}: step id "${id}" is not a dotted alphanumeric id (a hyphen is allowed between groups)`);
      if (!(marker in MARKERS)) problems.push(`${at}: step ${id} has unknown marker [${marker}]`);
      const parallel = rawTitle.endsWith(PARALLEL) || rest.includes(PARALLEL);
      const title = rawTitle.endsWith(PARALLEL) ? rawTitle.slice(0, -1).trimEnd() : rawTitle;
      step = { id, title, marker, state: MARKERS[marker], parallel, line: i + 1, class: 'implement', needs: [], fields: {} };
      steps.push(step);
      return;
    }
    if (!step) return;
    const meta = /^(\w+):\s/.exec(line);
    if (meta && meta[1] in META) {
      for (const segment of line.split(/\s+·\s+/)) {
        const kv = /^(\w+):\s*(.*)$/.exec(segment.trim());
        if (!kv || !(kv[1] in META)) {
          problems.push(`${at}: step ${step.id} has unknown field "${segment.trim()}"`);
          continue;
        }
        const [, key, value] = kv;
        if (key in step.fields) problems.push(`${at}: step ${step.id} repeats ${key}`);
        step.fields[key] = value;
        if (META[key] && !META[key].includes(value)) problems.push(`${at}: step ${step.id} has unknown ${key} "${value}" (${META[key].join(', ')})`);
        if (key === 'Class') step.class = value;
        else if (key === 'Effort') step.effort = value;
        else if (key === 'Tier') step.tier = value;
        else if (key === 'Data') step.data = value;
        else if (key === 'Check') step.check = stripTicks(value);
        else if (key === 'Human') step.human = value;
        else if (key === 'Issue') {
          const ref = parseRef(value);
          if (!ref) problems.push(`${at}: step ${step.id} has a malformed Issue "${value}" (#123, owner/repo#123, PROJ-123 or an issue URL)`);
          else step.issueRef = ref;
        } else if (key === 'Needs') step.needs = value === 'none' ? [] : value.split(/\s*,\s*/).filter(Boolean);
      }
      return;
    }
    const field = /^([A-Z][A-Za-z]*(?:-[a-z]+)*):\s+(.*)$/.exec(line);
    if (field) {
      step.fields[field[1]] = field[2];
      if (field[1] === 'Done-when') step.doneWhen = field[2];
    }
  });
  return { file, steps, problems: [...problems, ...graphProblems(steps, file)] };
}

// Duplicate ids, duplicate issues, unknown Needs ids and dependency cycles.
function graphProblems(steps, file) {
  const problems = [];
  const byId = new Map();
  for (const s of steps) {
    if (byId.has(s.id)) problems.push(`${file}:${s.line}: step id ${s.id} is used twice`);
    else byId.set(s.id, s);
  }
  const issues = new Map();
  for (const s of steps) {
    if (!s.issueRef) continue;
    const id = refId(s.issueRef);
    if (issues.has(id)) problems.push(`${file}:${s.line}: step ${s.id} names issue ${s.issueRef.text}, already the issue of step ${issues.get(id)}`);
    else issues.set(id, s.id);
  }
  for (const s of steps) for (const n of s.needs) if (!byId.has(n)) problems.push(`${file}:${s.line}: step ${s.id} needs unknown step ${n}`);
  const state = new Map(); // id -> 'visiting' | 'done'
  const visit = (s, trail) => {
    if (state.get(s.id) === 'done') return;
    if (state.get(s.id) === 'visiting') {
      const cycle = [...trail.slice(trail.indexOf(s.id)), s.id];
      problems.push(`${file}:${s.line}: dependency cycle ${cycle.join(' -> ')}`);
      return;
    }
    state.set(s.id, 'visiting');
    for (const n of s.needs) if (byId.has(n)) visit(byId.get(n), [...trail, s.id]);
    state.set(s.id, 'done');
  };
  for (const s of byId.values()) visit(s, []);
  return problems;
}

export function readPlan(file) {
  return parsePlan(readFileSync(file, 'utf8'), file);
}

// Every Markdown plan under docs/plans and docs/plans/archive.
export function planFiles(root) {
  const files = [];
  for (const dir of [PLAN_DIR, path.join(PLAN_DIR, 'archive')]) {
    const abs = path.join(root, dir);
    if (!existsSync(abs)) continue;
    for (const name of readdirSync(abs).sort()) if (name.endsWith('.md') && name !== 'INDEX.md') files.push(path.join(dir, name));
  }
  return files;
}

// The plan a command acts on: the argument, or the only active plan in docs/plans.
export function resolvePlan(root, arg) {
  if (arg) return path.resolve(root, arg);
  const active = planFiles(root).filter((f) => path.dirname(f) === PLAN_DIR);
  if (active.length === 1) return path.join(root, active[0]);
  throw new Error(active.length ? `several plans in ${PLAN_DIR}; name one (${active.join(', ')})` : `no plan in ${PLAN_DIR}`);
}

export function planStatus(plan) {
  const counts = Object.fromEntries(Object.values(MARKERS).map((m) => [m, 0]));
  for (const s of plan.steps) counts[s.state]++;
  return {
    file: plan.file,
    total: plan.steps.length,
    counts,
    steps: plan.steps.map(({ id, title, state, mismatch, issueState, issue }) => ({ id, title, status: state, ...(issue ? { issue } : {}), ...(mismatch ? { mismatch } : {}), ...(issueState?.stale ? { stale: issueState.fetchedAt ?? true } : {}) })),
  };
}

// Pending steps whose Needs are all done, in plan order, at most 4. `parallel` marks an option the plan
// declares parallel (`‖`) when another option is also declared parallel.
export function nextSteps(plan, max = MAX_OPTIONS) {
  const done = new Set(plan.steps.filter((s) => s.state === 'done').map((s) => s.id));
  const ready = plan.steps.filter((s) => s.state === 'pending' && s.needs.every((n) => done.has(n))).slice(0, max);
  const parallelCount = ready.filter((s) => s.parallel).length;
  return ready.map((s, i) => ({
    option: i + 1,
    id: s.id,
    title: s.title,
    class: s.class,
    parallel: s.parallel && parallelCount > 1,
    doneWhen: s.doneWhen ?? null,
    ...(s.issue ? { issue: s.issue } : {}),
  }));
}

export function formatStatus(status) {
  const c = status.counts;
  const lines = [`${status.file}: ${c.done}/${status.total} done, ${c['in progress']} in progress, ${c.blocked} blocked, ${c.moved} moved, ${c.pending} pending`];
  for (const s of status.steps) {
    const note = [s.mismatch ? `mismatch: ${s.mismatch}` : null, s.stale ? `issue state ${s.stale === true ? 'unknown' : `as of ${s.stale}`}, stale` : null].filter(Boolean).join('; ');
    if (s.status !== 'done' || s.mismatch) lines.push(`[${STATE_MARKER[s.status]}] ${s.id} ${s.title}${s.issue ? ` ${s.issue}` : ''}${note ? ` (${note})` : ''}`);
  }
  return lines.join('\n');
}

export function formatNext(options) {
  if (!options.length) return 'no step is ready: every pending step needs one that is not done';
  return options
    .map((o) => `${o.option}. ${o.id} ${o.title}${o.issue ? ` ${o.issue}` : ''} (${o.class})${o.parallel ? ` ${PARALLEL}` : ''}${o.doneWhen ? `\n   Done-when: ${o.doneWhen}` : ''}`)
    .join('\n');
}

// The plan's text with `Issue: <reference>` as the first line of a step's block (the heading's next line).
export function setIssueField(text, step, reference) {
  const lines = text.split('\n');
  lines.splice(step.line, 0, `Issue: ${reference}`);
  return lines.join('\n');
}

// What a step says, as the body of its issue: its prose lines (`Do:`, `Done-when:`, notes), without the metadata line, a
// bare `Issue:` or `Check:` (a command stays in the plan, 0119).
export function stepBody(text, step) {
  const lines = text.split('\n');
  const out = [];
  for (let i = step.line; i < lines.length; i++) {
    const line = lines[i];
    if (/^#{1,3}\s/.test(line) || /^---\s*$/.test(line)) break;
    if (/^(Class|Effort|Tier|Data|Needs|Check|Issue):\s/.test(line)) continue;
    out.push(line);
  }
  return out.join('\n').trim();
}

// --- start and done ----------------------------------------------------------------------------------------------

const CHECK_TIMEOUT_MS = 30 * 60 * 1000;
const TAIL_LINES = 20;

// Rewrites only the marker of one step's heading line.
export function setMarker(text, step, marker) {
  const lines = text.split('\n');
  lines[step.line - 1] = lines[step.line - 1].replace(/(\s—\s+)\[.\]/, `$1[${marker}]`);
  return lines.join('\n');
}

export function repoRoot(dir) {
  try {
    return execFileSync('git', ['rev-parse', '--show-toplevel'], { cwd: dir, env: cleanGitEnv(process.env), encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
  } catch {
    return dir;
  }
}

function findStep(file, id) {
  const plan = parsePlan(readFileSync(file, 'utf8'), file);
  if (plan.problems.length) throw new Error(`the plan does not parse: ${plan.problems[0]}`);
  const step = plan.steps.find((s) => s.id === id);
  if (!step) throw new Error(`no step ${id} in ${file}`);
  return { plan, step };
}

const writeMarker = (file, id, marker) => writeFileSync(file, setMarker(readFileSync(file, 'utf8'), findStep(file, id).step, marker));

// Sets a pending or blocked step to `[~]` once its Needs are done. With `worktree` (a slug) it first creates the task's
// worktree (`go-getter worktree new`) and sets the marker in that worktree's copy of the plan, so it lands with the step's branch.
export function startStep(cwd, file, id, { worktree, states } = {}) {
  const { plan, step } = findStep(file, id);
  if (step.marker === 'x' || step.marker === '>') throw new Error(`step ${id} is ${MARKERS[step.marker]}`);
  if (step.marker === '~' && !worktree) return { changed: false, file };
  // `states` (step id -> state) comes from the work source, so a step whose issue is still open is not done.
  const open = step.needs.filter((n) => (states?.get(n) ?? plan.steps.find((s) => s.id === n)?.state) !== 'done');
  if (open.length) throw new Error(`step ${id} needs ${open.join(', ')}, not done yet`);
  let target = file;
  let made;
  if (worktree) {
    made = newWorktree(cwd, worktree);
    const copy = path.join(made.path, path.relative(repoRoot(path.dirname(file)), file));
    if (existsSync(copy)) target = copy;
  }
  checkpointBeforeStep(repoRoot(cwd), id);
  writeMarker(target, id, '~');
  return { changed: true, file: target, worktree: made };
}

// Runs the step's Check from the repository root and sets `[x]` only when it passes; records one telemetry line
// (event `plan:done`, the step's class, pass or fail), never the check's output.
export function doneStep(cwd, file, id) {
  const { step } = findStep(file, id);
  if (step.marker === 'x') return { ok: true, changed: false, output: '' };
  if (step.marker === '>') throw new Error(`step ${id} is moved to another plan`);
  if (!step.check) throw new Error(`step ${id} has no Check; add one or set the marker by hand`);
  const root = repoRoot(cwd);
  const res = spawnSync(step.check, { cwd: root, shell: true, encoding: 'utf8', timeout: CHECK_TIMEOUT_MS });
  const ok = res.status === 0;
  recordQuietly(root, { event: 'plan:done', taskClass: step.class, outcome: ok ? 'pass' : 'fail' });
  if (ok) writeMarker(file, id, 'x');
  const output = ok ? '' : `${res.stdout ?? ''}\n${res.stderr ?? ''}${res.error ? `\n${res.error.message}` : ''}`.trim().split('\n').slice(-TAIL_LINES).join('\n');
  return { ok, changed: ok, check: step.check, output };
}
