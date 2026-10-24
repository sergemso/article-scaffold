// go-getter route --class <c> [--context-tokens <n>] [--handoff-tokens <n>] [--cache warm|cold] [--session-model <id>]
//                 [--data-class <public|internal|confidential|restricted>] [--host <id>] [--project <dir>]
//   Where should this step run? Prints the cheapest eligible route by expected total step cost as JSON; `delegateModel` is
//   the value the host's delegation tool accepts for `model` (an alias where the host has a table, else the full id).
// go-getter route --escalate --class <c> --from <tier> --attempts <n> [--host <id>]
//   The next route after a failed verification; a human once the escalation bound is reached.
// go-getter route --headless-flags --host <id>
//   The native spend-cap flag for headless runs of the host, from the adopted cap.
import path from 'node:path';
import { chooseRoute, escalate, routingInputs, TIERS } from '../routing/policy.mjs';
import { recordQuietly } from '../telemetry/record.mjs';
import { delegatedModel, routeRecord } from '../routing/delegate.mjs';
import { packageCapabilities } from '../governance.mjs';

const SPEND_FLAG = { 'claude-code': (usd) => `--max-budget-usd ${usd}`, copilot: (usd) => `--max-ai-credits ${usd}` };

export default function routeCommand({ args }) {
  const opt = { project: process.cwd() };
  const flags = new Set();
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (['--escalate', '--headless-flags'].includes(a)) flags.add(a);
    else if (a.startsWith('--')) opt[a.slice(2)] = args[++i];
    else {
      console.error(`route: unexpected argument "${a}"`);
      return 2;
    }
  }
  const project = path.resolve(opt.project);
  const host = opt.host;
  const inputs = routingInputs(project, host);
  if (!inputs) {
    console.error('route: the cost-routing pack is not adopted here');
    return 2;
  }
  if (flags.has('--headless-flags')) {
    const cap = inputs.policy.spendCapUsd;
    const flag = SPEND_FLAG[host];
    console.log(JSON.stringify({ host, spendCapUsd: cap, flags: cap && flag ? flag(cap) : null, note: flag ? undefined : 'this host has no headless spend cap' }));
    return 0;
  }
  const taskClass = opt.class;
  if (!taskClass) {
    console.error('usage: go-getter route --class <task-class> [--context-tokens <n>] [--cache warm|cold] [--session-model <id>] [--data-class <c>] [--host <id>]');
    return 2;
  }
  const int = (v, d) => (v === undefined ? d : Number.parseInt(v, 10));
  const step = { sessionTokens: int(opt['context-tokens'], 0), handoffTokens: int(opt['handoff-tokens'], undefined), cache: opt.cache ?? 'warm' };
  if (step.handoffTokens === undefined) delete step.handoffTokens;
  const common = { ...inputs, taskClass, ...(opt['data-class'] ? { dataClass: opt['data-class'] } : {}), step, ttl: inputs.policy.cacheTtl.subagent ?? '5m' };
  let route;
  if (flags.has('--escalate')) {
    if (!TIERS.includes(opt.from)) {
      console.error(`route --escalate: --from must be one of ${TIERS.join(', ')}`);
      return 2;
    }
    route = escalate({ ...common, from: opt.from, attempts: int(opt.attempts, 0) });
  } else {
    route = chooseRoute({ ...common, sessionModel: opt['session-model'] ?? null });
  }
  if (route.model) {
    const delegation = host && packageCapabilities()[host]?.routing?.delegation;
    route.delegateModel = delegation ? delegatedModel(delegation, route.model) : route.model;
  }
  recordQuietly(project, routeRecord(host ?? undefined, route, step.handoffTokens));
  console.log(JSON.stringify(route, null, 2));
  return 0;
}
