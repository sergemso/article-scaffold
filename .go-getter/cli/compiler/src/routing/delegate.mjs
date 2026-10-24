// Delegation-time router (decision 0020, layer 2): a pre-tool hook on the host's delegation tool picks the cheapest eligible
// model by expected total step cost and rewrites the delegated model. Hosts without a rewrite lever get no router (advisory).
import { statSync } from 'node:fs';
import { readRoster } from '../agents.mjs';
import { packageCapabilities } from '../governance.mjs';
import { chooseRoute, routingInputs, DEFAULT_HANDOFF_TOKENS } from './policy.mjs';
import { FIELDS } from '../telemetry/schema.mjs';

const TTL_MS = { '5m': 5 * 60 * 1000, '1h': 60 * 60 * 1000 };
const CHARS_PER_TOKEN = 4;

const modelOf = (payload) => (typeof payload.model === 'string' ? payload.model : payload.model?.id ?? null);

// Session prefix size and cache warmth from the transcript file: its size approximates the prefix, its last write the last request.
export function sessionEstimate(payload, ttl, now) {
  try {
    const stat = statSync(payload.transcript_path);
    return { sessionTokens: Math.round(stat.size / CHARS_PER_TOKEN), cache: now - stat.mtimeMs < (TTL_MS[ttl] ?? TTL_MS['5m']) ? 'warm' : 'cold' };
  } catch {
    return null;
  }
}

// The value the host's delegation tool accepts for a model id: the id itself, or the alias of the first manifest
// `models` entry whose prefix it starts with (Claude Code: the family alias); null when no entry matches.
export function delegatedModel(delegation, id) {
  if (!delegation.models) return id;
  return delegation.models.find((m) => id.startsWith(m.prefix))?.alias ?? null;
}

/**
 * For a tool call that delegates to a routed role: { deny, reason } when no eligible model exists (a human decides),
 * { rewrite: { input }, route, handoffTokens } with the delegated model set, { route } when staying in the session is cheaper,
 * { advisory, route } when the host cannot take the routed model (the agent file's compiled default applies),
 * or null when the call is not a routed delegation (other tool, not adopted, unknown role, explicit model).
 */
export function routeDelegation(project, host, payload, { now = Date.now(), capabilities = packageCapabilities() } = {}) {
  const delegation = capabilities[host]?.routing.delegation;
  if (!delegation || payload.tool_name !== delegation.tool) return null;
  const input = payload.tool_input ?? payload.toolInput ?? payload.args;
  if (!input || typeof input !== 'object' || input.model) return null; // the delegator chose a model explicitly
  const role = readRoster(project)?.roles.find((r) => r.id === (input.subagent_type ?? input.agent_type ?? input.agent ?? input.name));
  const inputs = role && routingInputs(project, host);
  if (!inputs) return null;

  const session = sessionEstimate(payload, inputs.policy.cacheTtl.main ?? '5m', now);
  const sessionModel = session ? modelOf(payload) : null;
  const prompt = typeof input.prompt === 'string' ? input.prompt : '';
  const handoffTokens = DEFAULT_HANDOFF_TOKENS + Math.round(prompt.length / CHARS_PER_TOKEN);
  const route = chooseRoute({
    ...inputs,
    taskClass: role['task-class'],
    sessionModel,
    ttl: inputs.policy.cacheTtl.subagent ?? '5m',
    step: { sessionTokens: session?.sessionTokens ?? 0, cache: session?.cache ?? 'cold', handoffTokens },
  });
  if (route.action === 'human') return { deny: true, reason: `go-getter routing: ${route.reason}; a human decides which model may take this step`, route, handoffTokens };
  if (route.action === 'stay') return { route, handoffTokens };
  const model = delegatedModel(delegation, route.model);
  if (!model) return { advisory: `go-getter routing (advisory): ${host} takes no value for ${route.model}; the agent file's model applies`, route, handoffTokens };
  return { rewrite: { input: { ...input, model } }, route, handoffTokens };
}

// Metadata for the telemetry line of a routed delegation: model, effort, class, handoff size, expected cost; never the brief.
export function routeRecord(host, route, handoffTokens) {
  const rec = { event: 'route', ...(host ? { host } : {}), taskClass: route.taskClass };
  if (route.action === 'human') return { ...rec, outcome: 'escalated' };
  if (FIELDS.model(route.model)) rec.model = route.model;
  if (route.effort) rec.effort = route.effort;
  if (Number.isFinite(route.expectedCost)) rec.cost = Number(route.expectedCost.toFixed(6));
  if (Number.isInteger(handoffTokens)) rec.tokens = { input: handoffTokens };
  return rec;
}

// Host answer to a rewritten delegation: Claude Code and Codex read `hookSpecificOutput.updatedInput`, Cursor `updated_input`.
export function respondRewrite(host, rewrite) {
  const style = packageCapabilities()[host].routing.delegation.update;
  const body = style === 'updated_input'
    ? { permission: 'allow', updated_input: rewrite.input }
    : { hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'allow', updatedInput: rewrite.input } };
  return { code: 0, stdout: JSON.stringify(body), stderr: '' };
}
