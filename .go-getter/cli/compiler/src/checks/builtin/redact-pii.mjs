// PII masking of tool output (decision 0106) is a tier-2 guardrail: the post-tool hook replaces email addresses, card
// numbers and IBANs (and the classes a project adds) with per-session pseudonyms where the host can replace output.
// A tier-3 run has nothing to check after the fact.
export default function redactPii() {
  return { ok: true, message: 'enforced by the post-tool hook' };
}
