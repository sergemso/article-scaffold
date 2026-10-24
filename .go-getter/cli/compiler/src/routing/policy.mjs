// Routing policy (decisions 0016, 0020, 0032): which (model, effort) a step goes to, and what happens when it fails.
// Order is fixed by guardrails: governance eligibility first (routing-governance-before-cost), then the cheapest sufficient
// tier by expected total step cost (routing-uses-total-step-cost), then bounded escalation that ends at a human
// (routing-escalation-bounded). `chooseRoute` and `escalate` are pure; the loaders read adopted knowledge-base artifacts.
import { readArtifacts } from '../artifacts.mjs';
import { adoptedData } from '../governance.mjs';
import { eligibleModels } from './eligibility.mjs';
import { loadRegistry } from './registry.mjs';
import { DEFAULT_FAILURE_RATES, DEFAULT_STEP, expectedDelegationCost, expectedStayCost, stepCost } from './cost.mjs';

export const TIERS = ['small', 'medium', 'large'];
export const EFFORTS = ['low', 'medium', 'high'];
export const DEFAULT_DATA_CLASS = 'internal';
// The prefix a freshly spawned agent starts with when only its brief and definition are handed over.
export const DEFAULT_HANDOFF_TOKENS = 4000;

const active = (a) => a.data.status === 'active';
const rankOf = (name) => TIERS.indexOf(name);

// Price rows (facts carrying `go-getter.models`) and the tier / host tables (fact 0024).
export function loadRoutingFacts(project) {
  const facts = readArtifacts(project, ['facts']).filter(active);
  const models = facts.flatMap((f) => f.data['go-getter']?.models ?? []).filter((m) => m.input !== undefined && m.output !== undefined);
  const tierFact = facts.find((f) => f.data['go-getter']?.['model-tiers']);
  return {
    models,
    tiers: tierFact?.data['go-getter']['model-tiers'] ?? {},
    hostProviders: tierFact?.data['go-getter']['host-providers'] ?? {},
  };
}

// The adopted cost-routing answers, or null when the pack is not adopted.
export function loadPolicy(project) {
  const startTiers = adoptedData(project, 'routing-start-tiers');
  if (!startTiers) return null;
  const escalations = Number.parseInt(adoptedData(project, 'max-escalations'), 10);
  const cap = Number.parseFloat(adoptedData(project, 'headless-spend-cap-usd'));
  const ttl = adoptedData(project, 'cache-ttl');
  const calibration = adoptedData(project, 'routing-calibration');
  return {
    classes: adoptedData(project, 'routing-classes') ?? {},
    startTiers,
    efforts: adoptedData(project, 'routing-efforts') ?? {},
    maxEscalations: Number.isInteger(escalations) && escalations >= 0 ? escalations : 2,
    spendCapUsd: Number.isFinite(cap) && cap > 0 ? cap : null,
    cacheTtl: ttl && typeof ttl === 'object' ? { main: ttl.main ?? null, subagent: ttl.subagent ?? null } : { main: null, subagent: null },
    ...calibrated(calibration),
  };
}

// Failure rates and step shape of an active `routing-calibration` decision (decision 0017); invalid values are ignored.
function calibrated(data) {
  if (!data || typeof data !== 'object') return {};
  const rate = (v) => typeof v === 'number' && v >= 0 && v <= 1;
  const size = (v) => Number.isInteger(v) && v > 0;
  const rates = Object.fromEntries(TIERS.filter((t) => rate(data['failure-rates']?.[t])).map((t) => [t, data['failure-rates'][t]]));
  const keys = { turns: 'turns', 'new-tokens': 'newTokens', 'output-tokens': 'outputTokens' };
  const step = Object.fromEntries(Object.entries(keys).filter(([k]) => size(data.step?.[k])).map(([k, v]) => [v, data.step[k]]));
  return { failureRates: rates, step };
}

// Task classes sharing a routing class (fast/strong grouping) are routed together; the group needs the strongest member's tier and effort.
export function routingClass(policy, taskClass) {
  return policy.classes[taskClass] ?? taskClass;
}

function members(policy, taskClass) {
  const group = routingClass(policy, taskClass);
  return Object.keys(policy.startTiers).filter((c) => routingClass(policy, c) === group);
}

export function startTier(policy, taskClass) {
  if (!(taskClass in policy.startTiers)) return null;
  return TIERS[Math.max(...members(policy, taskClass).map((c) => rankOf(policy.startTiers[c])))];
}

export function effortFor(policy, taskClass) {
  const known = members(policy, taskClass).map((c) => EFFORTS.indexOf(policy.efforts[c])).filter((i) => i >= 0);
  return known.length ? EFFORTS[Math.max(...known)] : null;
}

// Ladder of delegation targets, one rung per tier (cheapest base cost first inside a tier), rising by tier.
function buildLadder(eligible, tiers, step, ttl) {
  const tierName = (id) => TIERS.find((t) => (tiers[t] ?? []).includes(id));
  const rungs = [];
  for (const [rank, name] of TIERS.entries()) {
    const inTier = eligible.filter((m) => tierName(m.id) === name);
    if (!inTier.length) continue;
    const cost = (m) => stepCost(m, { ...step, contextTokens: step.handoffTokens, cache: 'cold', ttl });
    const model = [...inTier].sort((a, b) => cost(a) - cost(b) || a.id.localeCompare(b.id))[0];
    rungs.push({ model, name, rank });
  }
  return rungs;
}

// Candidate models: priced, in some tier, run by the host, and allowed for the data class. Eligibility comes before any cost.
function candidates({ models, tiers, hostProviders, dataClass, registry }) {
  const tiered = new Set(TIERS.flatMap((t) => tiers[t] ?? []));
  const pool = models.filter((m) => tiered.has(m.id) && (!hostProviders || hostProviders.includes(m.provider)));
  return eligibleModels({ dataClass, models: pool, registry });
}

const summary = (rung, extra) => ({ model: rung.model.id, provider: rung.model.provider, tier: rung.name, ...extra });

/**
 * Chooses where a step runs. `step`: { sessionTokens, handoffTokens, turns?, newTokens?, outputTokens?, cache? } (tokens
 * of the current session's prefix and of what a delegate must be handed). Returns { action: 'stay' | 'delegate' | 'human', ... }.
 */
export function chooseRoute({ taskClass, dataClass = DEFAULT_DATA_CLASS, models, tiers, hostProviders = null, registry = {}, policy, step, sessionModel = null, ttl = '5m', failureRates = { ...DEFAULT_FAILURE_RATES, ...policy.failureRates } }) {
  const start = startTier(policy, taskClass);
  if (!start) return { action: 'human', reason: `no routing class for "${taskClass}"`, taskClass, dataClass };
  const eligible = candidates({ models, tiers, hostProviders, dataClass, registry });
  if (!eligible.length) return { action: 'human', reason: `no eligible model for data class "${dataClass}"`, taskClass, dataClass };
  const full = { ...DEFAULT_STEP, ...policy.step, handoffTokens: DEFAULT_HANDOFF_TOKENS, sessionTokens: 0, ...step };
  const ladder = buildLadder(eligible, tiers, full, ttl);
  const common = { ladder, step: full, failureRates, escalations: policy.maxEscalations, ttl };
  const startRank = rankOf(start);
  const options = ladder
    .filter((rung) => rung.rank >= startRank)
    .map((rung) => summary(rung, { action: 'delegate', expectedCost: expectedDelegationCost(rung.model, rung, common) }));
  // Staying in the warm session is an option only for a session model that is eligible and strong enough.
  const sessionRung = sessionModel && eligible.find((m) => m.id === sessionModel);
  const sessionTier = sessionRung && TIERS.findIndex((t) => (tiers[t] ?? []).includes(sessionModel));
  if (sessionRung && sessionTier >= startRank) {
    const rung = { model: sessionRung, name: TIERS[sessionTier], rank: sessionTier };
    options.push(summary(rung, { action: 'stay', expectedCost: expectedStayCost(sessionRung, rung, common) }));
  }
  // A tie keeps the warm session: a handoff is never free.
  options.sort((a, b) => a.expectedCost - b.expectedCost || (a.action === b.action ? 0 : a.action === 'stay' ? -1 : 1));
  const best = options[0];
  return { ...best, effort: effortFor(policy, taskClass), taskClass, dataClass, options };
}

/**
 * The next route after a failed verification: one tier up on the delegation ladder. After `policy.maxEscalations`
 * escalations, or with no stronger eligible tier, the step goes to a human and is never retried further.
 */
export function escalate({ taskClass, dataClass = DEFAULT_DATA_CLASS, models, tiers, hostProviders = null, registry = {}, policy, step, from, attempts, ttl = '5m' }) {
  if (attempts >= policy.maxEscalations) return { action: 'human', reason: `escalation bound of ${policy.maxEscalations} reached`, taskClass, dataClass, attempts };
  const eligible = candidates({ models, tiers, hostProviders, dataClass, registry });
  const full = { ...DEFAULT_STEP, ...policy.step, handoffTokens: DEFAULT_HANDOFF_TOKENS, sessionTokens: 0, ...step };
  const next = buildLadder(eligible, tiers, full, ttl).find((rung) => rung.rank > rankOf(from));
  if (!next) return { action: 'human', reason: `no stronger eligible tier above "${from}"`, taskClass, dataClass, attempts };
  return { ...summary(next, { action: 'delegate' }), effort: effortFor(policy, taskClass), taskClass, dataClass, attempts: attempts + 1 };
}

// Everything the pure functions need for `host`, read from the project's adopted artifacts. Null when cost-routing is not adopted.
export function routingInputs(project, host) {
  const policy = loadPolicy(project);
  if (!policy) return null;
  const facts = loadRoutingFacts(project);
  // Without governance adopted there are no data classes to enforce: every model is eligible (public).
  const governed = adoptedData(project, 'model-registry') !== undefined;
  return { policy, models: facts.models, tiers: facts.tiers, hostProviders: facts.hostProviders[host] ?? null, registry: loadRegistry(project).registry, dataClass: governed ? DEFAULT_DATA_CLASS : 'public' };
}

// The model and effort compiled into a role's agent definition for `host`: the cheapest eligible start-tier model for internal data.
export function compiledDefault(project, host, role, { effortControl = true } = {}) {
  const inputs = routingInputs(project, host);
  if (!inputs || !inputs.hostProviders?.length) return null;
  const route = chooseRoute({ ...inputs, taskClass: role['task-class'], step: {} });
  if (route.action !== 'delegate') return null;
  return { model: route.model, provider: route.provider, effort: effortControl ? route.effort : null };
}
