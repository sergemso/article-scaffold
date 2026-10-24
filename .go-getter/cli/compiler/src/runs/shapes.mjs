// Whether an outward command shape may run without asking now (decision 0130): a remembered approval of the shape, or the
// active run granting it, and in both cases the shape's preconditions hold at this use.
import path from 'node:path';
import { shapeApproved } from '../secrets/approvals.mjs';
import { isApprovable } from '../gate.mjs';
import { resolvePlan } from '../plan.mjs';
import { activeRun } from './record.mjs';
import { checkShape } from './preconditions.mjs';

// { allowed: true, by: 'run' | 'remembered' }, or { allowed: false, firstUse: true } when nothing grants the shape yet, or
// { allowed: false, reason } when a grant exists but a precondition fails.
export function shapeAllowance(project, id, command, { gh, env = process.env } = {}) {
  const run = activeRun(project, { env });
  // Only approvable shapes: whatever a record says, tags, releases, publishing and repository settings are never allowed here.
  const inRun = Boolean(run?.grants.includes(id)) && isApprovable(id);
  if (!isApprovable(id)) return { allowed: false, never: true };
  if (!inRun && !shapeApproved(project, id, env)) return { allowed: false, firstUse: true };
  const check = checkShape({ project, id, command, run: inRun ? run : null, ...(gh ? { gh } : {}) });
  return check.ok ? { allowed: true, by: inRun ? 'run' : 'remembered' } : { allowed: false, reason: check.reason };
}

// Whether `go-getter plan issue <verb> <step> [plan]` writes to a step of the active run (decision 0130 item 5): `comment` and
// `close` on a step in the run's range are free; `create`, any other step and any other plan still ask.
export function trackerWriteInRun(project, args, { env = process.env } = {}) {
  const run = activeRun(project, { env });
  if (!run) return false;
  const rest = args.slice(2).filter((a, i) => !(i === 0 && a === '--dry-run'));
  const [verb, ...more] = rest;
  if (!['comment', 'close'].includes(verb)) return false;
  const positional = [];
  for (const a of more) {
    if (a.startsWith('--')) break;
    positional.push(a);
  }
  const [step, plan] = positional;
  if (!step || !run.steps.includes(step)) return false;
  try {
    const file = resolvePlan(project, plan);
    return path.relative(project, file).split(path.sep).join('/') === run.plan;
  } catch {
    return false;
  }
}
