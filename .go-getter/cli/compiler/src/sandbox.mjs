// Snippets for the hosts' own secret levers (facts 0027, 0031), built from the adopted restricted paths and `use` patterns.
// Prints text only: nothing is written, and `apply` does not use it.
import path from 'node:path';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { matchesAny } from './glob.mjs';
import { restrictedModes, restrictedPatterns } from './hook.mjs';

const MAX_FILE = 256 * 1024;
const SKIP_DIRS = new Set(['.git', 'node_modules']);

// Variable names (never values) of the KEY=value lines of the restricted files in the project.
export function restrictedNames(project, patterns) {
  const names = new Set();
  const walk = (dir) => {
    let entries;
    try {
      entries = readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const ent of entries) {
      const abs = path.join(dir, ent.name);
      if (ent.isDirectory()) {
        if (!SKIP_DIRS.has(ent.name)) walk(abs);
      } else if (ent.isFile() && matchesAny(path.relative(project, abs), patterns)) {
        try {
          if (statSync(abs).size > MAX_FILE) continue;
          for (const line of readFileSync(abs, 'utf8').split(/\r?\n/)) {
            const m = /^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=/.exec(line);
            if (m) names.add(m[1]);
          }
        } catch {
          // an unreadable file has no names to list
        }
      }
    }
  };
  if (patterns.length) walk(project);
  return [...names].sort();
}

const json = (value) => JSON.stringify(value, null, 2);

// kind -> (inputs) -> snippet text, or null when nothing is restricted for that lever.
const BUILDERS = {
  'credentials-deny': ({ deny, names }) => (deny.length + names.length
    ? json({ sandbox: { credentials: { deny: [...deny.map((p) => ({ file: p })), ...names.map((n) => ({ env: n }))] } } })
    : null),
  'credentials-mask': ({ use }) => (use.length ? json({ sandbox: { credentials: { mask: use.map((p) => ({ file: p })) } } }) : null),
  'profile-deny-glob': ({ deny }) => (deny.length ? ['[permissions.restricted.filesystem]', ...deny.map((p) => `"${p}" = "deny"`)].join('\n') : null),
  'env-redaction': ({ names }) => (names.length ? json({ security: { environmentVariableRedaction: { enabled: true, blocked: names } } }) : null),
  'secret-env-vars': ({ names }) => (names.length ? `--secret-env-vars=${names.join(',')}` : null),
};

// The labelled snippets for one project: one block per host lever, or a line saying the host has none.
export function sandboxReport(project, caps, hosts) {
  const patterns = restrictedPatterns(project);
  const modes = restrictedModes(project);
  const mode = (p) => modes.get(p) ?? 'deny';
  const deny = patterns.filter((p) => mode(p) !== 'use');
  const use = patterns.filter((p) => mode(p) === 'use');
  const names = restrictedNames(project, patterns);
  const out = [];
  for (const host of hosts) {
    const levers = caps[host].secretLevers ?? [];
    if (!levers.length) {
      out.push(`${host}: no credential lever documented (facts 0027, 0031)`);
      continue;
    }
    for (const lever of levers) {
      const mark = lever.confirmed ? 'confirmed' : 'not confirmed';
      const label = `${host}: ${lever.kind} (${lever.scope}) [${mark}, fact ${lever.fact}]`;
      const body = BUILDERS[lever.kind]({ deny, use, names });
      out.push([label, body ?? '(nothing restricted to list)', ...(lever.note ? [`note: ${lever.note}`] : [])].join('\n'));
    }
  }
  return out.join('\n\n');
}
