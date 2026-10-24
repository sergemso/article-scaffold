import { findings } from './secrets/patterns.mjs';

// How a host shows an MCP call to a hook (fact 0036) and the server allowlist of decision 0138.
// `mcp__<server>__<tool>` (Claude Code, Codex) carries the server; Cursor's `MCP:<tool>` does not; other hosts are unconfirmed.

// { server, tool } for `mcp__<server>__<tool>`, { server: null, tool } for `MCP:<tool>`, else null.
export function mcpCall(toolName) {
  if (typeof toolName !== 'string') return null;
  const m = /^mcp__(.+?)__(.+)$/.exec(toolName);
  if (m) return { server: m[1], tool: m[2] };
  const c = /^MCP:(.+)$/.exec(toolName);
  return c ? { server: null, tool: c[1] } : null;
}

// Claude Code renames a configured server (anything outside letters, digits, `_` and `-` becomes `_`); both sides are compared
// after the same renaming and without case.
export const normaliseServer = (name) => String(name).replace(/[^A-Za-z0-9_-]/g, '_').toLowerCase();

// The servers of a `builtin:mcp-allow servers="a, b"` entry, normalised.
export const allowedServers = (args = {}) => String(args.servers ?? '').split(',').map((s) => s.trim()).filter(Boolean).map(normaliseServer);

// The tools a project marked read, as `server:tool` normalised, from `reads="srv:tool, ..."`.
export const readTools = (args = {}) => String(args.reads ?? '').split(',').map((s) => s.trim()).filter(Boolean).map((s) => {
  const at = s.indexOf(':');
  return `${normaliseServer(s.slice(0, at))}:${s.slice(at + 1)}`;
});
export const isReadTool = (call, args) => readTools(args).includes(`${normaliseServer(call.server)}:${call.tool}`);
// The approval shape id of a write tool.
export const mcpShapeId = (call) => `mcp:${normaliseServer(call.server)}:${call.tool}`;

// The kinds of secret in an MCP call's input, never the text. `input` is the tool input as the host sent it.
export function secretKinds(input) {
  const text = typeof input === 'string' ? input : JSON.stringify(input ?? null);
  return [...new Set(findings(text).map((f) => f.kind))];
}

// A denial reason for a call to a server that is not listed, or null (allowed, or the host does not show the server).
export function mcpDenial(toolName, args) {
  const call = mcpCall(toolName);
  if (!call || call.server === null) return null;
  return allowedServers(args).includes(normaliseServer(call.server)) ? null : `MCP server "${call.server}" is not on the project's allowlist; ask the user to add it to the hitl pack's mcp-servers answer (go-getter reconfigure hitl)`;
}
