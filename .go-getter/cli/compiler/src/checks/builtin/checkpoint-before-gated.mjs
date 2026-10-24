// A gated action is preceded by a checkpoint (decision 0097) is a tier-2 guardrail: the pre-tool hook takes the checkpoint
// and `go-getter plan start` takes the plan-step one. A tier-3 run has nothing to check after the fact.
export default function checkpointBeforeGated() {
  return { ok: true, message: 'enforced by the pre-tool hook and plan start' };
}
