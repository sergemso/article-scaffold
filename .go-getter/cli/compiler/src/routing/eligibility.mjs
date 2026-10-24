// Governance eligibility (decision 0018, guardrail routing-governance-before-cost): which models may receive a data class.
// Pure: no I/O. Routing calls this before any cost comparison; an empty result goes to a human, never to a fallback.
export const DATA_CLASSES = ['public', 'internal', 'confidential', 'restricted'];

// model: { id, provider, local? }. registry: { providers: [{ id, zdr? }], confidential?: { enabled, requiresZdr } }.
function allows(model, dataClass, registry) {
  const approved = (registry.providers ?? []).find((p) => p.id === model.provider);
  const confidential = registry.confidential ?? { enabled: true, requiresZdr: false };
  switch (dataClass) {
    case 'public':
      return true;
    case 'internal':
      return model.local === true || Boolean(approved);
    case 'confidential':
      // Without a confidential class the data is handled as restricted, the stricter side.
      if (!confidential.enabled) return model.local === true;
      return model.local === true || Boolean(approved && (!confidential.requiresZdr || approved.zdr === true));
    case 'restricted':
      return model.local === true;
    default:
      return false;
  }
}

export function eligibleModels({ dataClass, models, registry = {} }) {
  return models.filter((m) => allows(m, dataClass, registry));
}

// `human` is true when nothing is eligible: the step goes to a person.
export function eligibility(input) {
  const eligible = eligibleModels(input);
  return { models: eligible, human: eligible.length === 0 };
}
