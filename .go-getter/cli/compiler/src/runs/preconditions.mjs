// Preconditions of an outward command shape, checked at each use (decision 0130 item 3). They answer from the hosting
// provider's CLI (GitHub's `gh`), read-only. A check that cannot be answered (offline, no pull request) fails closed: the
// command falls back to asking a person.
//   pr-merge: the pull request is open, its base is the default branch, every check passes, and, in a run, the pull request
//             names (Refs: #N) the issue of a step in the run's range.
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import { readPlan } from '../plan.mjs';
import { parseSimpleCommand } from '../invocation.mjs';

const defaultGh = (project) => (args) => {
  const r = spawnSync('gh', args, { cwd: project, encoding: 'utf8', timeout: 30_000 });
  return r.status === 0 ? { ok: true, out: r.stdout } : { ok: false, out: `${r.stdout ?? ''}${r.stderr ?? ''}` };
};

// The pull request a `gh pr merge ...` command names: a number, a URL or a branch, else the current branch's (null).
export function mergeTarget(command) {
  const parsed = parseSimpleCommand(String(command).trim());
  const words = parsed.simple ? parsed.words : String(command).trim().split(/\s+/);
  const at = words.findIndex((w, i) => w === 'merge' && words[i - 1] === 'pr');
  if (at < 0) return undefined;
  const flagsWithValue = new Set(['-b', '--body', '-F', '--body-file', '-t', '--subject', '-A', '--author-email', '--match-head-commit', '-R', '--repo']);
  for (let i = at + 1; i < words.length; i++) {
    if (flagsWithValue.has(words[i])) i++;
    else if (!words[i].startsWith('-')) return words[i];
  }
  return null;
}

const json = (r) => {
  try {
    return r.ok ? JSON.parse(r.out) : null;
  } catch {
    return null;
  }
};

function rangeIssues(project, run) {
  const plan = readPlan(path.resolve(project, run.plan));
  return new Set(plan.steps.filter((s) => run.steps.includes(s.id) && s.issueRef?.tracker === 'github').map((s) => String(s.issueRef.key)));
}

// { ok: true } or { ok: false, reason }. `run` is the active run when it is what grants the use, else null.
export function checkShape({ project, id, command, run = null, gh = defaultGh(project) }) {
  if (id !== 'pr-merge') return { ok: true };
  const target = mergeTarget(command);
  const ref = target ? [target] : [];
  const pr = json(gh(['pr', 'view', ...ref, '--json', 'number,state,baseRefName,body,title,isDraft']));
  if (!pr) return { ok: false, reason: 'the pull request could not be read (offline, or none for this branch)' };
  if (pr.state !== 'OPEN' || pr.isDraft) return { ok: false, reason: `pull request #${pr.number} is not open and ready` };
  const repo = json(gh(['repo', 'view', '--json', 'defaultBranchRef']));
  const base = repo?.defaultBranchRef?.name;
  if (!base) return { ok: false, reason: 'the default branch could not be read' };
  if (pr.baseRefName !== base) return { ok: false, reason: `pull request #${pr.number} targets ${pr.baseRefName}, not the default branch ${base}` };
  const checks = json(gh(['pr', 'checks', ...ref, '--json', 'name,bucket']));
  if (!Array.isArray(checks)) return { ok: false, reason: `the checks of pull request #${pr.number} could not be read` };
  if (!checks.length) return { ok: false, reason: `pull request #${pr.number} has no checks to wait for` };
  const bad = checks.filter((c) => !['pass', 'skipping'].includes(c.bucket));
  if (bad.length) return { ok: false, reason: `checks are not green on pull request #${pr.number}: ${bad.map((c) => `${c.name} (${c.bucket})`).join(', ')}` };
  if (run) {
    const issues = rangeIssues(project, run);
    const named = [...`${pr.title}\n${pr.body ?? ''}`.matchAll(/#(\d+)/g)].map((m) => m[1]);
    if (!named.some((n) => issues.has(n))) return { ok: false, reason: `pull request #${pr.number} names no issue of a step in the run's range (${[...issues].map((n) => `#${n}`).join(', ') || 'none'})` };
  }
  return { ok: true };
}
