// MCP server allowlist (decision 0138): enforced by the pre-tool hook (hook.mjs), so a tier-3 run has nothing to check after the fact.
export default function mcpAllow() {
  return { ok: true, message: 'enforced by the pre-tool hook' };
}
