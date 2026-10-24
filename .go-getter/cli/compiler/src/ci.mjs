// CI status (plan B.2c, decision 0071): the result of the latest CI run of a branch, read through the `gh` CLI
// (GitHub Actions only, no dependency). Without `gh`, a login or any run, the state is `unknown`.
import { execFileSync } from 'node:child_process';

const TAIL_LINES = 15;
const TIMEOUT_MS = 60 * 1000;
// Conclusions that do not fail a job; anything else completed (failure, cancelled, timed_out…) does.
const PASSING = new Set(['success', 'skipped', 'neutral']);
export const STATES = ['success', 'failure', 'pending', 'unknown'];

function gh(project, args) {
  return execFileSync('gh', args, { cwd: project, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], timeout: TIMEOUT_MS });
}

function git(project, args) {
  try {
    return execFileSync('git', args, { cwd: project, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
  } catch {
    return null;
  }
}

export const currentBranch = (project) => {
  const branch = git(project, ['rev-parse', '--abbrev-ref', 'HEAD']);
  return branch && branch !== 'HEAD' ? branch : null;
};

// The branch and commit whose CI says whether the work is done, or null when HEAD is not pushed as it is.
export function pushedHead(project) {
  const upstream = git(project, ['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}']);
  const head = git(project, ['rev-parse', 'HEAD']);
  if (!upstream || !head || git(project, ['rev-parse', '@{u}']) !== head) return null;
  return { branch: upstream.slice(upstream.indexOf('/') + 1), sha: head };
}

const jobState = (job) => (job.status !== 'completed' ? 'pending' : PASSING.has(job.conclusion) ? 'success' : 'failure');

// Log lines read `<job>\t<step>\t<line>`; only the line is kept, and only the last 15.
function failedTail(project, job) {
  try {
    const lines = gh(project, ['run', 'view', '--job', String(job.databaseId), '--log-failed']).trimEnd().split('\n');
    return lines.slice(-TAIL_LINES).map((l) => l.split('\t').slice(2).join('\t') || l).join('\n');
  } catch {
    return '';
  }
}

// {state, branch, sha?, jobs: [{name, state, tail?}]}. With `sha`, only runs of that commit count, and a branch
// whose runs are all of older commits is pending; without it, the latest run's commit is used.
export function ciStatus(project, { branch = currentBranch(project), sha } = {}) {
  if (!branch) return { state: 'unknown', branch, jobs: [] };
  let runs;
  try {
    runs = JSON.parse(gh(project, ['run', 'list', '--branch', branch, '--limit', '20', '--json', 'databaseId,headSha,status,conclusion,workflowName']));
  } catch {
    return { state: 'unknown', branch, jobs: [] };
  }
  if (!runs.length) return { state: 'unknown', branch, jobs: [] };
  const head = sha ?? runs[0].headSha;
  const current = runs.filter((r) => r.headSha === head);
  if (!current.length) return { state: 'pending', branch, sha: head, jobs: [] };
  const jobs = [];
  for (const run of current) {
    let runJobs;
    try {
      runJobs = JSON.parse(gh(project, ['run', 'view', String(run.databaseId), '--json', 'jobs'])).jobs ?? [];
    } catch {
      return { state: 'unknown', branch, sha: head, jobs: [] };
    }
    for (const job of runJobs) {
      const state = jobState(job);
      jobs.push({ name: job.name, state, ...(state === 'failure' ? { tail: failedTail(project, job) } : {}) });
    }
    // a run that has not created its jobs yet is still pending
    if (!runJobs.length) jobs.push({ name: run.workflowName, state: run.status === 'completed' ? (PASSING.has(run.conclusion) ? 'success' : 'failure') : 'pending' });
  }
  const state = jobs.some((j) => j.state === 'failure') ? 'failure' : jobs.some((j) => j.state === 'pending') ? 'pending' : 'success';
  return { state, branch, sha: head, jobs };
}

// One line per job, a failed job followed by its log tail.
export function formatStatus(status) {
  const lines = [`ci ${status.state} ${status.branch ?? '(no branch)'}${status.sha ? ` ${status.sha.slice(0, 7)}` : ''}`];
  for (const job of status.jobs) {
    lines.push(`${job.state === 'failure' ? 'FAIL' : job.state === 'pending' ? 'pending' : 'pass'} ${job.name}`);
    if (job.tail) lines.push(job.tail.replace(/^/gm, '  '));
  }
  return lines.join('\n');
}
