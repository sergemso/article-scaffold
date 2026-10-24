// go-getter run start <plan> [--through N] [--hours H] [--grant <id>]... | status [--json] | next [--json] | attempt <step> | end
// An autonomous run (decision 0130): a person starts it on a plan range; the record is read by the pre-tool hook. `start` and
// `end` change what an agent may do, so a person runs them; the hook refuses an agent's call to either.
import { existsSync } from 'node:fs';
import path from 'node:path';
import { activeRun, lastRun, startRun, endRun, noteEvent, DEFAULT_HOURS } from '../runs/record.mjs';
import { readPlan, repoRoot } from '../plan.mjs';
import { nextInRun } from '../runs/next.mjs';
import { buildReport, reportStep } from '../runs/report.mjs';
import { planIssue, relPlan } from '../trackers/write.mjs';
import { APPROVABLE, isApprovable, normaliseFree } from '../gate.mjs';
import { loadPolicy } from '../routing/policy.mjs';
import { adoptedData } from '../governance.mjs';
import { telemetryConfig } from '../telemetry/record.mjs';
import { packageCapabilities } from '../governance.mjs';
import { detect } from '../detect.mjs';
import { spendCoverage } from '../runs/spend.mjs';

const USAGE = 'usage: go-getter run start <plan> [--through N] [--hours H] [--grant <id>]... | status [--json] | next [--json] | attempt <step> | end';

function parseStart(rest) {
  const o = { grants: [] };
  const positional = [];
  for (let i = 0; i < rest.length; i++) {
    const value = () => (rest[i + 1] !== undefined && !rest[i + 1].startsWith('--') ? rest[++i] : null);
    if (rest[i] === '--through') o.through = value();
    else if (rest[i] === '--hours') o.hours = Number(value());
    else if (rest[i] === '--grant') o.grants.push(value());
    else if (rest[i].startsWith('--')) return null;
    else positional.push(rest[i]);
  }
  if (positional.length !== 1 || o.through === null || o.grants.includes(null) || (o.hours !== undefined && Number.isNaN(o.hours))) return null;
  return { ...o, plan: positional[0] };
}

const describe = (r) => `plan ${r.plan}, steps ${r.steps.join(', ')} (through ${r.through}), started ${r.startedAt}, times out ${r.timeoutAt}${r.spendCapUsd ? `, spend cap $${r.spendCapUsd}` : ''}${r.grants.length ? `, grants: ${r.grants.join(', ')}` : ''}`;

export default async function runCommand({ args }) {
  const [sub, ...rest] = args;
  const project = repoRoot(process.cwd());
  try {
    if (sub === 'status' && rest.every((a) => a === '--json')) {
      const active = activeRun(project);
      if (rest.includes('--json')) console.log(JSON.stringify({ active, last: lastRun(project) }, null, 2));
      else console.log(active ? `run active: ${describe(active)}` : 'no run is active');
      return 0;
    }
    // The next step of the range, or why the run stops and hands over (exit 1). Metadata only.
    if (sub === 'next' && rest.every((a) => a === '--json')) {
      const r = nextInRun(project);
      if (rest.includes('--json')) console.log(JSON.stringify(r, null, 2));
      else if (r.step) console.log(`next: step ${r.step.id} ${r.step.title}${r.step.check ? `\ncheck: ${r.step.check}` : ''}${r.step.doneWhen ? `\ndone-when: ${r.step.doneWhen}` : ''}`);
      else if (r.done) console.log('the run range is finished; a person ends the run with: go-getter run end');
      else console.log(`stop (${r.stop.code}): ${r.stop.reason}; hand over to the user`);
      return r.step ? 0 : r.done ? 0 : 1;
    }
    // One failed fix attempt on a step (red CI or a failing check); two stop the run on that step.
    if (sub === 'attempt' && rest.length === 1) {
      const n = noteEvent(project, 'attempt', rest[0]);
      if (n === null) throw new Error(`no active run has step ${rest[0]}`);
      console.log(`attempt ${n} recorded for step ${rest[0]}`);
      return 0;
    }
    if (sub === 'end' && !rest.length) {
      const done = endRun(project, { reason: 'ended' });
      if (!done) {
        console.log('no run is active');
        return 1;
      }
      console.log(`run ended: ${describe(done)}`);
      // The report goes to the issue of the range's last step after the tracker's secret and personal-data check; without an issue, or
      // when the post is refused, it is printed.
      const { text, steps } = buildReport(project, done);
      const id = reportStep(steps);
      const file = path.resolve(project, done.plan);
      const posted = id ? await planIssue(project, file, relPlan(project, file), 'comment', id, { text }) : null;
      if (posted?.ok) console.log(`report posted: ${posted.message}`);
      else console.log(`${posted ? `report not posted (${posted.error})` : 'report (the plan has no issue to post it on)'}:\n\n${text}`);
      return 0;
    }
    if (sub === 'start') {
      const o = parseStart(rest);
      if (!o) {
        console.error(USAGE);
        return 2;
      }
      const file = path.resolve(project, o.plan);
      if (!existsSync(file)) throw new Error(`no plan at ${o.plan}`);
      const plan = readPlan(file);
      const ids = plan.steps.map((s) => s.id);
      if (o.through !== undefined && !ids.includes(o.through)) throw new Error(`the plan has no step ${o.through}`);
      // The range: the steps not yet done, from the first to --through (default: the last step).
      const last = o.through === undefined ? ids.length - 1 : ids.indexOf(o.through);
      const steps = plan.steps.slice(0, last + 1).filter((s) => ['pending', 'in progress', 'blocked'].includes(s.state)).map((s) => s.id);
      if (!steps.length) throw new Error('no step is left to do in that range');
      // Without --grant, the shapes the project's hitl answer lists (stored as one comma-separated string).
      const grants = normaliseFree((o.grants.length ? o.grants : [].concat(adoptedData(project, 'run-grants') ?? [])).flatMap((g) => String(g).split(',')).map((g) => g.trim()).filter(Boolean));
      const bad = grants.filter((g) => !isApprovable(g));
      if (bad.length) throw new Error(`--grant takes approvable command shapes (${APPROVABLE.join(', ')}, mcp:<server>:<tool>), not ${bad.join(', ')}; tags, releases, publishing and history rewrites always need a human`);
      // The spend cap is read from the telemetry log (runs/next.mjs), so a cap with recording off would never bind.
      const spendCapUsd = loadPolicy(project)?.spendCapUsd ?? null;
      if (spendCapUsd && telemetryConfig(project).recording !== 'metadata-log') throw new Error(`the project sets a spend cap of $${spendCapUsd}, which is read from the telemetry metadata log, and telemetry recording is off; turn on telemetry-recording (metadata-log) or remove the cap`);
      // A host with no spend reader cannot bind the cap (decision 0144): say so plainly and start anyway.
      const coverage = spendCoverage(detect(project).hostAgents, packageCapabilities(), spendCapUsd);
      const record = startRun(project, { plan: path.relative(project, file).split(path.sep).join('/'), steps, through: steps.at(-1), hours: o.hours ?? DEFAULT_HOURS, spendCapUsd, grants, spendMetered: spendCapUsd ? coverage.metered : null });
      if (coverage.notice) console.error(`run: ${coverage.notice}`);
      console.log(`run started: ${describe(record)}`);
      return 0;
    }
  } catch (err) {
    console.error(`run: ${err.message.split('\n')[0]}`);
    return 1;
  }
  console.error(USAGE);
  return 2;
}
