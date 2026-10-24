// Expected total step cost (decision 0016, guardrail routing-uses-total-step-cost). Pure: no I/O.
// A step is `turns` model calls. Each call sends the prefix (`contextTokens`), which the cache holds after the first call;
// the first call pays the cache state's rate: read when the cache is warm, write (priced by TTL) when it is cold.
// Per-token list price is never the criterion: a pricier model in a warm session can cost less than a cheaper one that
// must be handed the context and start a cold cache.
// Prices are USD per million tokens, rows as in the `go-getter.models` lists of the price facts.
const MTOK = 1e6;

export const DEFAULT_STEP = { turns: 6, newTokens: 1500, outputTokens: 800 };

// Probability that a result from a tier fails its verification bar. Approximate until calibrated (decision 0017).
export const DEFAULT_FAILURE_RATES = { small: 0.3, medium: 0.15, large: 0.05 };

// Price of one prefix token on the first call: cache read when warm, cache write when cold. Providers that list no
// write price (cache writes billed as plain input) fall back to the input price.
export function prefixRate(model, { cache, ttl = '5m' }) {
  if (cache === 'warm') return model.cache_read ?? model.input;
  return model[`cache_write_${ttl}`] ?? model.cache_write_5m ?? model.input;
}

// Cost in USD of one step on one model, no escalation. `uncached: true` prices the prefix at the plain input rate on every call.
export function stepCost(model, { contextTokens, newTokens = DEFAULT_STEP.newTokens, outputTokens = DEFAULT_STEP.outputTokens, turns = DEFAULT_STEP.turns, cache = 'cold', ttl = '5m', uncached = false }) {
  const read = uncached ? model.input : (model.cache_read ?? model.input);
  const first = uncached ? model.input : prefixRate(model, { cache, ttl });
  const prefix = contextTokens * first + contextTokens * read * (turns - 1);
  const perTurn = newTokens * model.input + outputTokens * model.output;
  return (prefix + perTurn * turns) / MTOK;
}

// Expected cost of delegating to `model` and, with probability `failRate(tier)`, redoing the step one tier up,
// at most `escalations` more times (beyond the bound a failure goes to a human, whose cost is not counted here).
// `ladder`: the models to escalate to, cheapest per tier first, ordered by rising tier: [{model, tier}, ...].
// A delegate starts a cold cache: it is handed `handoffTokens` as its prefix.
export function expectedDelegationCost(model, tier, { ladder, step, failureRates = DEFAULT_FAILURE_RATES, escalations = 2, ttl = '5m' }) {
  const base = stepCost(model, { ...step, contextTokens: step.handoffTokens, cache: 'cold', ttl });
  const next = ladder.find((rung) => rung.rank > tier.rank);
  if (escalations <= 0 || !next) return base;
  const redo = expectedDelegationCost(next.model, next, { ladder, step, failureRates, escalations: escalations - 1, ttl });
  return base + (failureRates[tier.name] ?? 0) * redo;
}

// Expected cost of staying in the current session on `model`: the session's cache is warm, nothing is handed off.
// A failure re-runs the step on the delegation ladder one tier up.
export function expectedStayCost(model, tier, { ladder, step, failureRates = DEFAULT_FAILURE_RATES, escalations = 2, ttl = '5m' }) {
  const base = stepCost(model, { ...step, contextTokens: step.sessionTokens, cache: step.cache ?? 'warm', ttl });
  const next = ladder.find((rung) => rung.rank > tier.rank);
  if (escalations <= 0 || !next) return base;
  const redo = expectedDelegationCost(next.model, next, { ladder, step, failureRates, escalations: escalations - 1, ttl });
  return base + (failureRates[tier.name] ?? 0) * redo;
}
