// What an autonomous run does next (decision 0130 items 6-8): the next step of its range, or the reason to stop and hand over.
// A stop is never skipped: the first step of the range that is not done decides, so a human-needed step blocks what follows it.
import path from 'node:path';
import { readPlan } from '../plan.mjs';
import { readLog } from '../telemetry/record.mjs';
import { activeRun, noteStop } from './record.mjs';
import { recordRunSpend } from '../spend/index.mjs';

export const MAX_ATTEMPTS = 2;
export const MAX_DENIALS = 2;

// Dollars spent since the run started, from the telemetry metadata log (records carry `cost`).
export function spentUsd(project, run) {
  const since = Date.parse(run.startedAt);
  return readLog(project).reduce((sum, r) => (Date.parse(r.ts) >= since && typeof r.cost === 'number' ? sum + r.cost : sum), 0);
}

// { step } for the next step to do, { done: true } when the range is finished, { stop: { code, step?, reason } } otherwise.
export function nextInRun(project, { env = process.env, record = true, spendExec } = {}) {
  const run = activeRun(project, { env });
  if (!run) return { stop: { code: 'no-run', reason: 'no run is active' } };
  const stop = (code, reason, step) => {
    const s = { code, ...(step ? { step } : {}), reason };
    if (record) noteStop(project, s, { env });
    return { stop: s };
  };
  if (run.spendCapUsd) recordRunSpend(project, run, undefined, spendExec);
  const spent = spentUsd(project, run);
  if (run.spendCapUsd && spent >= run.spendCapUsd) return stop('spend-cap', `spend $${spent.toFixed(2)} has reached the cap of $${run.spendCapUsd}`);
  const plan = readPlan(path.join(project, run.plan));
  const byId = new Map(plan.steps.map((s) => [s.id, s]));
  for (const id of run.steps) {
    const step = byId.get(id);
    if (!step || ['done', 'moved'].includes(step.state)) continue;
    if (step.human) return stop('human-needed', `step ${id} needs a person: ${step.human}`, id);
    if (step.state === 'blocked') return stop('human-needed', `step ${id} is blocked`, id);
    const attempts = run.counters?.attempts?.[id] ?? 0;
    if (attempts >= MAX_ATTEMPTS) return stop('red-attempts', `step ${id} failed ${attempts} fix attempts`, id);
    const repeated = Object.entries(run.counters?.denials?.[id] ?? {}).find(([, n]) => n >= MAX_DENIALS);
    if (repeated) return stop('repeated-denial', `step ${id} was denied ${repeated[1]} times by ${repeated[0]}`, id);
    const open = step.needs.filter((n) => byId.get(n)?.state !== 'done');
    if (open.length) return stop('needs-open', `step ${id} needs ${open.join(', ')}, which is not done`, id);
    return { step: { id, title: step.title, state: step.state, check: step.check ?? null, doneWhen: step.doneWhen ?? null, ...(step.fields.Issue ? { issue: step.fields.Issue } : {}), attempts } };
  }
  return { done: true };
}
