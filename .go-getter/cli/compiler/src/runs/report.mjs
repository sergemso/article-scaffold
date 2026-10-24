// The end-of-run report (decision 0130 item 9): what a run did and why it stopped, from the run record, the plan, git history,
// the telemetry cost and the approvals store. Ids, numbers, links and plan step titles only: no prompt, command or file content.
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { readPlan } from '../plan.mjs';
import { listShapes } from '../secrets/approvals.mjs';
import { originRepo } from '../trackers/github.mjs';
import { cleanGitEnv } from '../git-env.mjs';
import { spentUsd } from './next.mjs';
import { recordRunSpend } from '../spend/index.mjs';

// Pull requests merged since the run started: the `(#N)` a squash merge puts in the subject of a commit on this branch.
function mergedPullRequests(project, since) {
  try {
    const out = execFileSync('git', ['log', '--first-parent', `--since=${since}`, '--format=%s'], { cwd: project, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], env: cleanGitEnv(process.env) });
    return [...new Set(out.split('\n').flatMap((subject) => /\(#([1-9][0-9]*)\)\s*$/.exec(subject)?.[1] ?? []))];
  } catch {
    return [];
  }
}

// Markdown report of a finished run record. `project` is the repository root.
export function buildReport(project, run, { env = process.env, spendExec } = {}) {
  const repo = originRepo(project);
  const link = (kind, n) => (repo ? `[#${n}](https://github.com/${repo}/${kind}/${n})` : `#${n}`);
  const issueLink = (step) => {
    const ref = step.issueRef;
    if (!ref) return '';
    return ref.tracker === 'jira' ? ` (${ref.text})` : ` (${ref.repo ? ref.text : link('issues', ref.key)})`;
  };
  const plan = readPlan(path.join(project, run.plan));
  const inRange = run.steps.map((id) => plan.steps.find((s) => s.id === id)).filter(Boolean);
  const done = inRange.filter((s) => s.state === 'done');
  const open = inRange.filter((s) => s.state !== 'done');
  const reasonFor = (s) => (run.stop?.step === s.id ? `${run.stop.code}: ${run.stop.reason}` : run.stop && !run.stop.step ? `${run.stop.code}: ${run.stop.reason}` : s.human ? `needs a person: ${s.human}` : `not reached (run ${run.endReason})`);
  if (run.spendCapUsd && run.spendMetered !== false) recordRunSpend(project, run, undefined, spendExec);
  const spent = spentUsd(project, run);
  const prs = mergedPullRequests(project, run.startedAt);
  const attempts = Object.entries(run.counters?.attempts ?? {});
  const denials = Object.entries(run.counters?.denials ?? {}).flatMap(([step, per]) => Object.entries(per).map(([id, n]) => `step ${step}: ${id} ×${n}`));
  const remembered = listShapes(project, env).map((e) => e.id);
  const lines = [
    `## Autonomous run report: ${run.plan}`,
    '',
    `Started ${run.startedAt}, ended ${run.endedAt} (${run.endReason}).`,
    '',
    `**Steps done (${done.length}/${inRange.length})**`,
    ...(done.length ? done.map((s) => `- ${s.id} ${s.title}${issueLink(s)}`) : ['- none']),
    '',
    '**Not done**',
    ...(open.length ? open.map((s) => `- ${s.id} ${s.title}: ${reasonFor(s)}`) : ['- none']),
    '',
    `**Pull requests merged:** ${prs.length ? prs.map((n) => link('pull', n)).join(', ') : 'none'}`,
    `**Stops:** ${run.stop ? `${run.stop.code}${run.stop.step ? ` at step ${run.stop.step}` : ''}: ${run.stop.reason}` : 'none'}`,
    `**Denials:** ${denials.length ? denials.join('; ') : 'none'}`,
    `**Fix attempts:** ${attempts.length ? attempts.map(([s, n]) => `step ${s} ×${n}`).join('; ') : 'none'}`,
    run.spendMetered === false ? `**Spend:** not metered on this host; the cap of $${run.spendCapUsd} could not bind` : `**Spend:** $${spent.toFixed(2)}${run.spendCapUsd ? ` of a $${run.spendCapUsd} cap` : ' (no cap)'}`,
    `**Approvals used:** run grants: ${run.grants.length ? run.grants.join(', ') : 'none'}; remembered shapes: ${remembered.length ? remembered.join(', ') : 'none'}`,
  ];
  return { text: `${lines.join('\n')}\n`, steps: inRange };
}

// The step whose issue receives the report: the last step of the range that has one.
export const reportStep = (steps) => [...steps].reverse().find((s) => s.issueRef)?.id ?? null;
