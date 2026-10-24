// Verification gate (plan 5.5, decision 0031): runs the adopted checks of a task class and gates "done" on them.
// Configuration comes from adopted decisions (`go-getter.verify-scope`, `verify-<check>-command`, `verify-where`, `verify-review-bar`, `verify-gate`);
// every check is recorded as one metadata line (event `verify:<check>`, never its output).
import path from 'node:path';
import { spawnSync, execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { adoptedData } from './governance.mjs';
import { CHECKS } from './detect.mjs';
import { runTier3 } from './enforce.mjs';
import { ciStatus, formatStatus, pushedHead } from './ci.mjs';
import { recordQuietly, STATE_DIR } from './telemetry/record.mjs';

export const CLASSES = ['explore', 'plan', 'implement', 'review', 'debug'];
// Classes whose result is code: they run the project's own commands. Review has its own bar.
const CODE_CLASSES = new Set(['implement', 'debug']);
const DEFAULT_MAX_ESCALATIONS = 2;
const TIMEOUT_MS = 10 * 60 * 1000;
const TAIL_LINES = 15;

// `export GO_GETTER_COVERAGE_BAR=...; ` for the coverage command: the bar kind, and the minimum for a threshold.
function coverageEnv(project) {
  const bar = String(adoptedData(project, 'verify-coverage-bar') ?? 'command').trim();
  const min = String(adoptedData(project, 'verify-coverage-min') ?? '').trim();
  const vars = [`GO_GETTER_COVERAGE_BAR=${bar}`, ...(bar === 'threshold' && /^\d{1,3}$/.test(min) ? [`GO_GETTER_COVERAGE_MIN=${min}`] : [])];
  return `export ${vars.join(' ')}; `;
}

// The test command of the "affected tests" scope takes the place of the test command.
// Each check runs where the machine profile places it (decision 0071): `commands` are the `local` and `both` checks
// the gate runs, `ci` the `ci` and `both` checks CI runs. A profile adopted before 0071 has no placement: all local.
export function verifyConfig(project) {
  const scope = adoptedData(project, 'verify-scope') ?? null;
  const command = (key) => String(adoptedData(project, key) ?? '').trim();
  let commands = Object.fromEntries(CHECKS.map((c) => [c, command(`verify-${c}-command`)]));
  if (scope === 'tests-only') commands = { test: commands.test };
  if (scope === 'affected-tests') commands = { test: command('verify-affected-command') };
  // The coverage command gets its bar as environment variables (decision 0129):
  // exported first so the command can use them in its own arguments.
  if (commands.coverage) commands = { ...commands, coverage: `${coverageEnv(project)}${commands.coverage}` };
  const placement = adoptedData(project, 'verify-where') ?? {};
  const profile = adoptedData(project, 'verify-profile') ?? null;
  // A profile adopted before coverage was a check has no placement for it: it follows the profile (slow checks run in CI).
  const where = (name) => placement[name] ?? (name === 'coverage' && ['thin', 'ci-only'].includes(profile) ? 'ci' : 'local');
  const pick = (places) => Object.fromEntries(Object.entries(commands).filter(([name, v]) => v && places.includes(where(name))));
  const escalations = Number.parseInt(adoptedData(project, 'max-escalations'), 10);
  return {
    adopted: scope !== null,
    scope,
    profile: adoptedData(project, 'verify-profile') ?? null,
    commands: pick(['local', 'both']),
    ci: pick(['ci', 'both']),
    reviewBar: adoptedData(project, 'verify-review-bar') ?? 'none',
    gate: adoptedData(project, 'verify-gate') ?? 'report',
    maxEscalations: Number.isInteger(escalations) && escalations >= 0 ? escalations : DEFAULT_MAX_ESCALATIONS,
  };
}

// The checks a class must pass: [{name, command}] (command) or [{name, guardrails: true}] (conform bar).
export function checksFor(config, taskClass) {
  if (CODE_CLASSES.has(taskClass)) return Object.entries(config.commands).map(([name, command]) => ({ name, command }));
  if (taskClass === 'review' && config.reviewBar === 'verdict-conform') return [{ name: 'guardrails', guardrails: true }];
  return [];
}

const tail = (text) => text.trim().split('\n').slice(-TAIL_LINES).join('\n');

async function runCheck(project, check) {
  if (check.guardrails) {
    const failed = (await runTier3(project)).filter((r) => !r.ok);
    return { ok: failed.length === 0, output: failed.map((f) => `${f.guardrail}: ${f.message ?? f.check}`).join('\n') };
  }
  const res = spawnSync(check.command, { cwd: project, shell: true, encoding: 'utf8', timeout: TIMEOUT_MS });
  const ok = res.status === 0;
  return { ok, output: ok ? '' : tail(`${res.stdout ?? ''}\n${res.stderr ?? ''}${res.error ? `\n${res.error.message}` : ''}`) };
}

// Runs every check of the class and records one telemetry line per check. Returns {ok, results: [{name, ok, output}]}.
export async function verify(project, taskClass, { host } = {}) {
  const config = verifyConfig(project);
  const results = [];
  for (const check of checksFor(config, taskClass)) {
    const { ok, output } = await runCheck(project, check);
    results.push({ name: check.name, ok, output });
    recordQuietly(project, { event: `verify:${check.name}`, ...(host ? { host } : {}), taskClass, outcome: ok ? 'pass' : 'fail' });
  }
  return { ok: results.every((r) => r.ok), results };
}

// --- Stop gate -------------------------------------------------------------------------------------------------

const BLOCKS = path.join(STATE_DIR, 'verify-blocks.json');
const DAY = 86400000;

function readBlocks(project) {
  try {
    return JSON.parse(readFileSync(path.join(project, BLOCKS), 'utf8'));
  } catch {
    return {};
  }
}

function writeBlocks(project, blocks, now) {
  const live = Object.fromEntries(Object.entries(blocks).filter(([, v]) => now - v.ts < DAY));
  try {
    mkdirSync(path.join(project, STATE_DIR), { recursive: true });
    writeFileSync(path.join(project, BLOCKS), `${JSON.stringify(live)}\n`);
  } catch {
    // state is best effort: without it the gate degrades to blocking at most once per stop
  }
}

// "Done" only needs gating when the working tree holds changes to check; a question-and-answer session is not gated.
function hasChanges(project) {
  try {
    const out = execFileSync('git', ['status', '--porcelain', '--', '.', `:(exclude)${STATE_DIR}`], { cwd: project, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
    return out.trim().length > 0;
  } catch {
    return false;
  }
}

const sessionKey = (payload) => String(payload.session_id ?? payload.conversation_id ?? 'default').slice(0, 64);

// Decision for a host's stop event: {block, reason} or {block: false, escalated?: true, handover?: true, reason?}.
// A tree with changes is gated on the local implement checks; a clean tree pushed as it is, on the CI checks (0071).
// Either blocks at most `maxEscalations` times per session, then hands over to a human.
export async function evaluateStop(project, payload, { host, now = Date.now() } = {}) {
  const config = verifyConfig(project);
  if (config.gate !== 'block') return { block: false };
  if (!hasChanges(project)) return ciGate(project, config, payload, { host, now });
  const key = sessionKey(payload);
  const blocks = readBlocks(project);
  const { ok, results } = await verify(project, 'implement', { host });
  if (ok) {
    delete blocks[key];
    writeBlocks(project, blocks, now);
    return { block: false };
  }
  const failed = results.filter((r) => !r.ok);
  return escalate(project, config, blocks, key, failed.map((f) => `${f.name} failed:\n${f.output}`).join('\n\n'), { host, now, what: 'fix the failing checks' });
}

const CI_GREEN = 'ci:green';

// CI decides "done" only when the project places checks in CI and HEAD is pushed; a commit seen green is not asked again.
function ciGate(project, config, payload, { host, now }) {
  const head = Object.keys(config.ci).length ? pushedHead(project) : null;
  const blocks = readBlocks(project);
  if (!head || blocks[CI_GREEN]?.sha === head.sha) return { block: false };
  const status = ciStatus(project, head);
  const key = sessionKey(payload);
  if (status.state === 'unknown') return { block: false };
  if (status.state === 'pending') {
    return { block: false, handover: true, reason: `go-getter verification gate: CI is still running for ${head.branch}; the step is done only when it is green. Wait with \`go-getter watch --until done -- go-getter ci status --wait\`.` };
  }
  recordQuietly(project, { event: 'verify:ci', ...(host ? { host } : {}), taskClass: 'implement', outcome: status.state === 'success' ? 'pass' : 'fail' });
  if (status.state === 'success') {
    delete blocks[key];
    blocks[CI_GREEN] = { sha: head.sha, ts: now };
    writeBlocks(project, blocks, now);
    return { block: false };
  }
  return escalate(project, config, blocks, key, formatStatus(status), { host, now, what: 'fix the failing CI jobs, push, then wait with `go-getter watch --until done -- go-getter ci status --wait`' });
}

function escalate(project, config, blocks, key, detail, { host, now, what }) {
  const count = blocks[key]?.count ?? 0;
  if (count >= config.maxEscalations) {
    delete blocks[key];
    writeBlocks(project, blocks, now);
    recordQuietly(project, { event: 'verify:gate', ...(host ? { host } : {}), taskClass: 'implement', outcome: 'escalated', escalations: count });
    return { block: false, escalated: true, reason: `go-getter verification gate: checks still fail after ${count} attempts; handing over to a human.\n${detail}` };
  }
  blocks[key] = { count: count + 1, ts: now };
  writeBlocks(project, blocks, now);
  recordQuietly(project, { event: 'verify:gate', ...(host ? { host } : {}), taskClass: 'implement', outcome: 'blocked', escalations: count });
  return { block: true, reason: `go-getter verification gate: not done yet, ${what} (attempt ${count + 1} of ${config.maxEscalations}).\n${detail}` };
}

// Host answer to a stop event. Cursor continues the agent through a follow-up message; the others read exit 2.
export function respondStop(host, decision) {
  if (decision.block) {
    if (host === 'cursor') return { code: 0, stdout: JSON.stringify({ followup_message: decision.reason }), stderr: '' };
    return { code: 2, stdout: '', stderr: decision.reason };
  }
  return { code: 0, stdout: '', stderr: decision.escalated || decision.handover ? decision.reason : '' };
}
