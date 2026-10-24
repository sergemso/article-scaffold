// Builds the governance inputs of eligibility.mjs from a project's knowledge-base artifacts:
// models from facts carrying `go-getter.models` (price facts, local-model facts), policy from governance decisions.
import { readArtifacts } from '../artifacts.mjs';

const active = (a) => a.data.status === 'active';

export function loadRegistry(project) {
  const models = readArtifacts(project, ['facts'])
    .filter(active)
    .flatMap((f) => f.data['go-getter']?.models ?? [])
    .map((m) => ({ id: m.id, provider: m.provider, local: m.local === true }));
  const decisions = readArtifacts(project, ['decisions']).filter(active);
  const registryOf = decisions.find((d) => d.data['go-getter']?.['model-registry']);
  const classes = decisions.find((d) => d.data['go-getter']?.['data-classes']);
  const confidential = classes?.data['go-getter']['data-classes'].confidential;
  const registry = {
    providers: (registryOf?.data['go-getter']['model-registry'].providers ?? []).map((p) => ({ id: p.id, zdr: p.zdr === true })),
    ...(confidential ? { confidential: { enabled: confidential.enabled !== false, requiresZdr: confidential['requires-zdr'] === true } } : {}),
  };
  return { models, registry };
}
