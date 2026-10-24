// The secret patterns shared by tier-2 tool-output redaction and tier-3 scanning (decision 0106). Heuristic: a format
// that is not listed is missed. No entropy detection, and nothing is vendored (guardrail no-runtime-dependencies).

// A private-key block, to the end marker or the end of a truncated output.
const KEY_BLOCK = '-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\\s\\S]*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|$)';

// `redact`: also replaced in tool output. Redaction keeps to specific token formats; a JWT or a labelled assignment
// is reported by scanning only, since redacting every `password = ...` in ordinary output would scramble it.
export const PATTERNS = [
  { kind: 'private-key', source: KEY_BLOCK, redact: true },
  { kind: 'aws', source: '\\b(?:AKIA|ASIA)[0-9A-Z]{16}\\b', redact: true },
  { kind: 'google', source: '\\bAIza[0-9A-Za-z_-]{35}', redact: true },
  { kind: 'github', source: '\\bgh[pousr]_[A-Za-z0-9]{36,}', redact: true },
  { kind: 'github', source: '\\bgithub_pat_[A-Za-z0-9_]{22,}', redact: true },
  { kind: 'gitlab', source: '\\bglpat-[A-Za-z0-9_-]{20,}', redact: true },
  { kind: 'slack', source: '\\bxox[abposr]-[A-Za-z0-9-]{10,}', redact: true },
  { kind: 'npm', source: '\\bnpm_[A-Za-z0-9]{36}', redact: true },
  { kind: 'anthropic', source: '\\bsk-ant-[A-Za-z0-9_-]{20,}', redact: true },
  { kind: 'atlassian', source: '\\bATATT[A-Za-z0-9_=-]{40,}', redact: true },
  { kind: 'stripe', source: '\\bsk_live_[A-Za-z0-9]{20,}', redact: true },
  { kind: 'jwt', source: '\\beyJ[A-Za-z0-9_-]{8,}\\.eyJ[A-Za-z0-9_-]{8,}\\.[A-Za-z0-9_-]{8,}', redact: false },
  // `secret|token|password|passwd|api_key` (after any prefix such as `db_`, with a suffix such as `_value`) followed by `=` or `:` and a quoted or bare
  // value of 16 or more characters that mixes letters and digits and has no `(){}[]$<>`: a variable reference like
  // `process.env.TOKEN_NAME` or a template like `${{ secrets.KEY }}` is not a secret.
  {
    kind: 'assignment',
    source: '(?<![A-Za-z])(?:secret|token|password|passwd|api[_-]?key)[A-Za-z0-9_-]*["\']?\\s*[=:]\\s*["\']?(?=[A-Za-z0-9+/_=.~-]{16,})(?=[^\\s"\']*[A-Za-z])(?=[^\\s"\']*[0-9])[A-Za-z0-9+/_=.~-]+',
    flags: 'i',
    redact: false,
  },
];

const regexp = (p) => new RegExp(p.source, `${p.flags ?? ''}g`);

// The regular expressions output redaction replaces (fresh objects: they are global and carry state).
export const redactionRegexes = () => PATTERNS.filter((p) => p.redact).map((p) => regexp(p));

// Secrets in `text` as non-overlapping [{ kind, index, length }], in order. A specific token format wins over the
// labelled assignment that contains it (`GITHUB_TOKEN=ghp_...` is one `github` finding).
export function findings(text) {
  const found = [];
  const overlaps = (a, b) => a.index < b.index + b.length && b.index < a.index + a.length;
  for (const p of [...PATTERNS.filter((x) => x.kind !== 'assignment'), ...PATTERNS.filter((x) => x.kind === 'assignment')]) {
    for (const m of text.matchAll(regexp(p))) {
      if (!m[0].length) continue;
      const f = { kind: p.kind, index: m.index, length: m[0].length };
      if (!found.some((g) => overlaps(f, g))) found.push(f);
    }
  }
  return found.sort((a, b) => a.index - b.index);
}
