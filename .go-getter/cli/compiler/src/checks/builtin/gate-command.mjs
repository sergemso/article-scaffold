// Gated commands (decision 0094) are a tier-2 guardrail: the hosts' native ask rules, written by apply, and the pre-tool
// hook enforce it. A tier-3 run has nothing to check after the fact.
export default function gateCommand() {
  return { ok: true, message: 'enforced by host ask rules and the pre-tool hook' };
}
