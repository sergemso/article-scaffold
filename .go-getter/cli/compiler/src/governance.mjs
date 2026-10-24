// Governance pack data (decision 0029) read from adopted decisions: restricted-data hosts and prompt logging.
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { readArtifacts } from './artifacts.mjs';
import { loadCapabilities } from './capabilities.mjs';

const PACKAGE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

export const packageCapabilities = (packageRoot = PACKAGE_ROOT) => loadCapabilities(packageRoot);

// The `go-getter.<key>` value of the first active decision that carries it.
export function adoptedData(project, key) {
  const decision = readArtifacts(project, ['decisions']).find((d) => d.data.status === 'active' && d.data['go-getter']?.[key] !== undefined);
  return decision?.data['go-getter'][key];
}

const RULES = {
  'blocking-hook': (caps) => caps.hooks.blockPreTool,
  all: () => true,
  sandbox: (caps) => caps.sandbox,
};

// Hosts permitted near restricted data under the project's rule (default: hosts with a blocking pre-tool hook).
export function restrictedDataHosts(project, caps) {
  const rule = RULES[adoptedData(project, 'restricted-data-hosts')?.rule] ?? RULES['blocking-hook'];
  return Object.keys(caps).filter((host) => rule(caps[host]));
}

// Hosts whose prompt logging `apply` switches off: every host with a setting for it, or only those permitted near restricted data.
export function promptLoggingTargets(project, caps, hosts) {
  const scope = adoptedData(project, 'prompt-logging')?.scope;
  if (scope !== 'all' && scope !== 'restricted-hosts') return [];
  const permitted = scope === 'restricted-hosts' ? new Set(restrictedDataHosts(project, caps)) : null;
  return hosts.filter((h) => caps[h]?.telemetry.promptLogOff && (!permitted || permitted.has(h)));
}

export function setPath(obj, keys, value) {
  const out = structuredClone(obj);
  let node = out;
  for (const k of keys.slice(0, -1)) node = typeof node[k] === 'object' && node[k] !== null ? node[k] : (node[k] = {});
  node[keys[keys.length - 1]] = value;
  return out;
}
