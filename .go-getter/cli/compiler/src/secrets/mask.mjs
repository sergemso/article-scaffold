// PII masking of tool output (decision 0106): which classes a project masks, and the replacement of a text's PII with
// pseudonyms. The configuration is the adopted tier-2 `builtin:redact-pii classes=...` entry; none, no masking.
import { collectEnforcement } from '../enforce.mjs';
import { ALL_CLASSES, piiFindings } from './pii.mjs';

// The classes to mask, or null when the project has not adopted PII masking.
export function piiConfig(project) {
  const entry = collectEnforcement(project).find((e) => e.tier === 2 && e.parsed?.kind === 'builtin' && e.parsed.id === 'redact-pii');
  if (!entry) return null;
  const classes = String(entry.parsed.args.classes ?? '').split(/[\s,]+/).filter((c) => ALL_CLASSES.includes(c));
  return classes.length ? { classes } : null;
}

// The session a payload belongs to, whatever the host calls it (facts 0003-0008, "Session identity"); a project-wide key
// when it carries none, so its map still expires with the 24-hour sweep.
export function sessionKeyOf(payload) {
  for (const k of ['session_id', 'sessionId', 'sessionID', 'conversation_id']) if (typeof payload?.[k] === 'string' && payload[k]) return payload[k];
  return 'project';
}

// `text` with each PII value replaced by `pseudonymizer.name(kind, value)`; `kinds` counts what was replaced.
export function maskPii(text, { classes, pseudonymizer }) {
  const found = piiFindings(text, { classes });
  if (!found.length) return { text, kinds: {} };
  const kinds = {};
  // Names follow first appearance, left to right; the text is then rebuilt from the right so the indexes stay valid.
  const named = found.map((f) => ({ ...f, name: pseudonymizer.name(f.kind, text.slice(f.index, f.index + f.length)) }));
  let out = text;
  for (const f of [...named].reverse()) {
    out = out.slice(0, f.index) + f.name + out.slice(f.index + f.length);
    kinds[f.kind] = (kinds[f.kind] ?? 0) + 1;
  }
  return { text: out, kinds };
}
