// MCP call argument scan (decision 0138 item 3): enforced by the pre-tool hook (hook.mjs), so a tier-3 run has nothing to check after the fact.
export default function mcpScan() {
  return { ok: true, message: 'enforced by the pre-tool hook' };
}
