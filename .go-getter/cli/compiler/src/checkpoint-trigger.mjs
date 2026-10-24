// When checkpoints are taken (decision 0097): the tier-2 `builtin:checkpoint-before-gated` guardrail entries name the
// triggers (`gated-action`, `plan-step`) and how many checkpoints to keep (`keep=<n>` or `keep=all`). Taking one is best
// effort: it never changes the decision of the hook or the outcome of the step it runs before.
import { collectEnforcement } from './enforce.mjs';
import { createCheckpoint, DEFAULT_KEEP } from './checkpoint.mjs';
import { matchGated, GATE_CLASSES, gateArgs } from './gate.mjs';
import { recordQuietly } from './telemetry/record.mjs';

export const TRIGGERS = ['gated-action', 'plan-step'];
const ID = 'checkpoint-before-gated';
const list = (s) => String(s ?? '').split(',').map((x) => x.trim()).filter(Boolean);

// { triggers: Set, keep } merged over the project's entries, or null when none is adopted.
export function checkpointConfig(enforcement) {
  const mine = enforcement.filter((e) => e.tier === 2 && e.parsed?.kind === 'builtin' && e.parsed.id === ID);
  if (!mine.length) return null;
  const triggers = new Set(mine.flatMap((e) => list(e.parsed.args?.triggers ?? 'gated-action')).filter((t) => TRIGGERS.includes(t)));
  const keeps = mine.map((e) => (e.parsed.args?.keep === 'all' ? Infinity : Number(e.parsed.args?.keep ?? DEFAULT_KEEP))).filter((n) => Number.isInteger(n) && n > 0 || n === Infinity);
  return { triggers, keep: keeps.length ? Math.max(...keeps) : DEFAULT_KEEP };
}

// The id of the first gated command `command` matches (the full catalog on every host minus the commands the project frees, plus its extras), or null.
function gatedId(enforcement, command) {
  const gates = enforcement.filter((e) => e.tier === 2 && e.parsed?.kind === 'builtin' && e.parsed.id === 'gate-command').map((e) => gateArgs(e.parsed.args));
  const extra = gates.flatMap((g) => g.extra);
  const free = gates.length ? gates[0].free.filter((id) => gates.every((g) => g.free.includes(id))) : []; // freed by every gate
  return matchGated(command, { classes: GATE_CLASSES, extra, free, provider: gates[0]?.provider })[0]?.id ?? null;
}

function take(project, trigger, label, host, keep) {
  const made = createCheckpoint(project, { label, keep });
  if (made) recordQuietly(project, { event: 'checkpoint', ...(host ? { host } : {}), trigger, outcome: 'pass' });
  return made;
}

// Before a shell command that is gated, when `gated-action` is a trigger. Returns the checkpoint or null; never throws.
export function checkpointBeforeCommand(project, enforcement, command, host) {
  try {
    const config = checkpointConfig(enforcement);
    if (!config?.triggers.has('gated-action') || typeof command !== 'string') return null;
    const id = gatedId(enforcement, command);
    return id ? take(project, 'gated-action', id.replace(/^extra:/, 'extra'), host, config.keep) : null;
  } catch {
    return null;
  }
}

// Before a plan step starts, when `plan-step` is a trigger. Never throws.
export function checkpointBeforeStep(project, stepId) {
  try {
    const enforcement = collectEnforcement(project);
    const config = checkpointConfig(enforcement);
    return config?.triggers.has('plan-step') ? take(project, 'plan-step', `step ${stepId}`, undefined, config.keep) : null;
  } catch {
    return null;
  }
}
