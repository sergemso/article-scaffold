// Shared tier-2 hook runtime: every host's pre-tool hook calls `go-getter hook pre-tool --host <id>`.
// Evaluates the project's tier-2 guardrail entries against the tool call and answers in the host's format.
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import os from 'node:os';
import { collectEnforcement } from './enforce.mjs';
import { matchesAny } from './glob.mjs';
import { FIELDS } from './telemetry/schema.mjs';
import { patternsOf } from './checks/builtin/deny-path.mjs';
import { adoptedData, packageCapabilities } from './governance.mjs';
import { driftNudge } from './manifest.mjs';
import { matchGated, gateArgs, isRegexExtra } from './gate.mjs';
import { goGetterCommand, goGetterCall } from './invocation.mjs';
import { shellOperands, commandWords } from './shell.mjs';
import { parseRunArgs, sharedApproved } from './secrets/use.mjs';
import { approved as personallyApproved, addPending, storeDir, relativeSecretPath, addPendingShape, takePendingShape, addShape } from './secrets/approvals.mjs';
import { shapeAllowance, trackerWriteInRun } from './runs/shapes.mjs';
import { activeRun, noteEvent } from './runs/record.mjs';
import { readPlan } from './plan.mjs';
import { mcpDenial, mcpCall, isReadTool, mcpShapeId, secretKinds } from './mcp.mjs';
import { MCP_SHAPE } from './gate.mjs';
import { fileSet } from './secrets/fileset.mjs';
import { checkpointBeforeCommand } from './checkpoint-trigger.mjs';
import { redactionRegexes } from './secrets/patterns.mjs';
import { piiConfig, sessionKeyOf, maskPii } from './secrets/mask.mjs';
import { createPseudonymizer, cleanupSession, sweepPseudonyms } from './secrets/pseudonyms.mjs';

const METADATA = new Set(['session_id', 'transcript_path', 'cwd', 'hook_event_name', 'permission_mode', 'model', 'model_id', 'model_params', 'conversation_id', 'generation_id', 'cursor_version', 'workspace_roots', 'user_email', 'turn_id', 'tool_use_id', 'agent_id', 'agent_type', 'prompt_id', 'scratchpad_dir', 'effort']);

// Prose fields of the tools go-getter knows, by kind: they carry text for a model or a file body, never a path to reach.
// Every other field of a known tool is still scanned, so an unexpected field only adds false positives.
const PROSE = {
  file: ['content', 'contents', 'file_text', 'old_string', 'new_string', 'oldString', 'newString', 'old_str', 'new_str', 'edits'],
  shell: ['description'],
  search: ['pattern'],
  fetch: ['prompt'],
  websearch: ['query'],
  delegate: ['prompt', 'description', 'message', 'summary'],
  ask: ['questions'],
  skill: ['args'],
  todo: ['todos'],
  memory: ['fact'],
};
// Tool names (lowercased) of every host the shared runtime serves, mapped to their kind. A name not listed is unknown:
// all of its input is scanned. Shell commands stay tokenised whole, so a restricted name anywhere in one is denied.
// Codex, Cursor and Copilot names are confirmed by fact 0031; their argument field names mostly are not.
const TOOLS = {
  // file read, write and edit tools; `apply_patch` carries its patch (paths included) in `command`, scanned whole
  read: 'file', write: 'file', edit: 'file', multiedit: 'file', notebookedit: 'file', read_file: 'file', write_file: 'file',
  replace: 'file', read_many_files: 'file', view: 'file', create: 'file', str_replace_editor: 'file', delete: 'file',
  apply_patch: 'file',
  // shell tools
  bash: 'shell', shell: 'shell', run_shell_command: 'shell', powershell: 'shell',
  // content search: the pattern is a regex over file bodies; the path, glob and include fields are scanned
  grep: 'search', search_file_content: 'search', grep_search: 'search', rg: 'search',
  // web fetch and web search
  webfetch: 'fetch', web_fetch: 'fetch', websearch: 'websearch', google_web_search: 'websearch', web_search: 'websearch',
  // delegation to another agent
  agent: 'delegate', task: 'delegate', spawn_agent: 'delegate', sendmessage: 'delegate',
  // questions put to the user and skill arguments are text, not paths a tool opens (the `skill` name is still scanned)
  askuserquestion: 'ask', skill: 'skill',
  todowrite: 'todo', write_todos: 'todo', update_todo: 'todo', save_memory: 'memory',
};

const toolName = (payload) => {
  const name = payload.tool_name ?? payload.toolName;
  return typeof name === 'string' ? name : undefined;
};

// The tool input: the host's input field (Copilot sends `toolArgs` as JSON text), else the payload without metadata.
function toolInput(payload) {
  const input = payload.tool_input ?? payload.toolInput ?? payload.args ?? payload.toolArgs;
  if (typeof input === 'string') {
    try {
      return JSON.parse(input);
    } catch {
      return input;
    }
  }
  return input ?? Object.fromEntries(Object.entries(payload).filter(([k]) => !METADATA.has(k)));
}

// Strings a tool call could use to reach a path: the input values of the tool, minus the prose fields of a known tool,
// split into shell-ish tokens. An unknown tool has every input value scanned.
export function candidatePaths(payload, project) {
  let source = toolInput(payload);
  const kind = TOOLS[toolName(payload)?.toLowerCase()];
  if (kind && source && typeof source === 'object' && !Array.isArray(source)) {
    source = Object.fromEntries(Object.entries(source).filter(([k]) => !PROSE[kind].includes(k)));
  }
  // A shell command is read for what it really names (decision 0126); one that cannot be read is scanned as text, below.
  let operands = null;
  if (kind === 'shell') {
    const command = shellText(payload);
    operands = typeof command === 'string' ? shellOperands(command) : null;
    if (operands && source && typeof source === 'object' && !Array.isArray(source)) source = Object.fromEntries(Object.entries(source).filter(([k]) => k !== 'command' && k !== 'cmd'));
    else if (operands && typeof source === 'string') source = undefined;
  }
  const strings = [];
  const walk = (v) => {
    if (typeof v === 'string') strings.push(v);
    else if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === 'object') Object.values(v).forEach(walk);
  };
  walk(source);
  const tokens = new Set();
  for (const raw of operands ?? []) {
    const rel = path.isAbsolute(raw) && project ? path.relative(project, raw) : raw;
    tokens.add(rel.replace(/^\.\//, ''));
  }
  for (const s of strings) {
    for (const raw of s.split(/[\s"'`;|&<>()=,]+/)) {
      if (!raw) continue;
      const rel = path.isAbsolute(raw) && project ? path.relative(project, raw) : raw;
      tokens.add(rel.replace(/^\.\//, ''));
    }
  }
  return [...tokens];
}

// Access modes of restricted patterns (decision 0072) from `go-getter.restricted-modes` ("use:<pattern>, sink:<pattern>").
// A pattern not listed, or listed under both modes, is `deny`.
export function restrictedModes(project) {
  const modes = new Map();
  for (const entry of String(adoptedData(project, 'restricted-modes') ?? '').split(',')) {
    const m = /^(use|sink):(\S+)$/.exec(entry.trim());
    if (m) modes.set(m[2], modes.has(m[2]) && modes.get(m[2]) !== m[1] ? 'deny' : m[1]);
  }
  return modes;
}

// A path's mode: `deny` if a restricted pattern it matches is `deny` or its patterns disagree.
function modeOf(file, patterns, modes) {
  const found = new Set(patterns.filter((p) => matchesAny(file, [p])).map((p) => modes.get(p) ?? 'deny'));
  return found.size === 1 ? [...found][0] : 'deny';
}

// The access mode of a project file (a path relative to the project root): `deny` unless every restricted pattern it
// matches is `use` (or every one is `sink`). A file no restricted pattern matches is `deny` too: it is not a secret to pass.
export function pathMode(project, file) {
  const patterns = restrictedPatterns(project).filter((p) => matchesAny(file, [p]));
  return patterns.length ? modeOf(file, patterns, restrictedModes(project)) : 'deny';
}

// `run` or `put` when the call is a shell command that is exactly one simple command running `go-getter secret run|put <args>`, from
// wherever go-getter is installed (the project runner, a user-level install, npx, `node <entry>`; decision 0126): no pipe,
// list, redirect, substitution or expansion, so nothing else runs in it, and quoted arguments are fine. Never a substring match.
const SECRET_MODE = { run: 'use', put: 'sink' };
export function secretSubcommand(payload, project = process.cwd()) {
  if (TOOLS[toolName(payload)?.toLowerCase()] !== 'shell') return undefined;
  const command = toolInput(payload)?.command;
  if (typeof command !== 'string') return undefined;
  const call = goGetterCommand(command, { cwd: project });
  const [group, sub] = call?.args ?? [];
  return group === 'secret' && Object.hasOwn(SECRET_MODE, sub) ? sub : undefined;
}

// The secret path and the command of a `go-getter secret run` call, or null: { path, words }.
function runCall(command, project) {
  const call = goGetterCommand(command, { cwd: project });
  const [group, sub, ...rest] = call?.args ?? [];
  if (group !== 'secret' || sub !== 'run') return null;
  const parsed = parseRunArgs(rest);
  if (parsed.error) return null;
  try {
    return { path: relativeSecretPath(project, parsed.from ?? parsed.file), words: parsed.command };
  } catch {
    return null;
  }
}

// What a `go-getter secret run|put` call may name: paths of its mode in its command. Null for any other call. For `run`, the
// secret path itself is allowed only when the command is approved to use it (the project's shared list for a `use` path, or the
// user's own approval while the command's code is unchanged, decision 0126); an unapproved first use is asked or handed over.
function exemption(project, payload) {
  const sub = secretSubcommand(payload, project);
  if (!sub) return null;
  const command = toolInput(payload).command;
  const modes = restrictedModes(project);
  const call = sub === 'run' ? runCall(command, project) : null;
  const approved = Boolean(call && (sharedApproved(project, call.path, call.words.join(' '), modes) || personallyApproved(project, call.words, call.path)));
  return { mode: SECRET_MODE[sub], modes, names: new Set(candidatePaths({ tool_name: 'bash', tool_input: { command } }, project)), call, approved };
}

// Hosts with a native ask rule prompt the human themselves (decision 0094), so the hook gates only the others (and, on every host, the `/regex/` extras, which have no native rule).
let capabilities;
const hasNativeAsk = (host) => Boolean((capabilities ??= packageCapabilities())[host]?.permissions?.ask);
// Whether the host's pre-tool hook can ask the person to approve a call (facts 0003 to 0008): only where the capability says so.
const canPrompt = (host) => Boolean((capabilities ??= packageCapabilities())[host]?.hooks?.askPreTool);

// The command of a shell tool call as text: a Codex-style argv of `sh -c <script>` is its script.
function shellCommand(payload) {
  if (TOOLS[toolName(payload)?.toLowerCase()] !== 'shell') return undefined;
  const input = toolInput(payload);
  const command = typeof input === 'string' ? input : input?.command ?? input?.cmd;
  if (Array.isArray(command)) return /^-\w*c$/.test(command[1] ?? '') ? String(command.at(-1)) : command.join(' ');
  return typeof command === 'string' ? command : undefined;
}

// A shell call's command as text for reading it word by word: a Codex-style argv keeps its words (each quoted), except
// `sh -c <script>`, which is its script.
function shellText(payload) {
  if (TOOLS[toolName(payload)?.toLowerCase()] !== 'shell') return undefined;
  const input = toolInput(payload);
  const command = typeof input === 'string' ? input : input?.command ?? input?.cmd;
  if (!Array.isArray(command)) return typeof command === 'string' ? command : undefined;
  if (/^-\w*c$/.test(command[1] ?? '')) return String(command.at(-1));
  return command.map((w) => `'${String(w).replace(/'/g, `'\\''`)}'`).join(' ');
}

// `{ command, class }` when a `gate-command` entry gates this call on this host, else null. Without a known host the call
// is not gated: whether the host prompts natively cannot be told. A host with native ask rules prompts for the catalog and
// the prefix extras; a `/regex/` extra has no native rule there, so the hook gates only those.
function gatedCommand(entry, payload, host) {
  if (!host) return null;
  const command = shellCommand(payload);
  if (!command) return null;
  const args = gateArgs(entry.parsed.args);
  let hit;
  try {
    hit = matchGated(command, hasNativeAsk(host) ? { classes: [], extra: args.extra.filter(isRegexExtra) } : args)[0];
  } catch {
    return null; // an invalid pattern gates nothing here rather than breaking every shell call; `apply` rejects it
  }
  return hit ? { command: command.length > 200 ? `${command.slice(0, 200)}…` : command, class: hit.class } : null;
}

// A gate-command entry's go-getter subcommands (`plan issue create`) are gated by what a call runs (decision 0126), whichever way
// go-getter is installed or typed. A host whose hook can ask gets a prompt; a host with native ask rules relies on the globs apply
// wrote for the usual spellings; any other host hands over. Null when the call is not one of them.
function identityGate(project, entry, payload, host) {
  if (!host) return null;
  const subs = gateArgs(entry.parsed.args).goGetter;
  const command = shellCommand(payload);
  if (!subs.length || typeof command !== 'string') return null;
  const decide = (text, sub) => {
    if (canPrompt(host)) return { deny: false, ask: true, reason: `go-getter ${sub} writes outside this machine: approve "${text}"?` };
    if (hasNativeAsk(host)) return null;
    return { deny: true, reason: `blocked by guardrail ${entry.guardrail}: "${text}" is an outward command and needs a human; ask the user to run it themselves` };
  };
  const parsed = commandWords(command);
  if (!parsed) {
    // unreadable: the conservative reading of the text
    const sub = subs.find((x) => new RegExp(x.split(' ').join('\\s+')).test(command));
    return sub ? decide(command.length > 200 ? `${command.slice(0, 200)}…` : command, sub) : null;
  }
  for (const words of parsed) {
    const call = goGetterCall(words, { cwd: project });
    const sub = call && subs.find((x) => x.split(' ').every((w, i) => call.args[i] === w));
    if (sub && ['plan issue comment', 'plan issue close'].includes(sub) && trackerWriteInRun(project, call.args)) continue; // a step of the active run
    if (sub) return decide(words.join(' '), sub);
  }
  return null;
}

// A `use` path may be named only by a call that is exactly `go-getter secret run`, and a `sink` path only by one that is
// exactly `go-getter secret put` (decisions 0072 and 0107); every other call that names one is denied like a `deny` path.
// Why a call may not change or open the user's approvals or run record, or null: only a person adds or revokes an approval or starts or ends a run (a forged approval would let
// any command use a secret), and the store is not for tools to open.
function approvalsStoreRefusal(project, payload) {
  const command = shellCommand(payload);
  if (typeof command === 'string') {
    for (const words of commandWords(command) ?? []) {
      const call = goGetterCall(words, { cwd: project });
      if (call?.args[0] === 'approvals' && ['add', 'allow', 'revoke'].includes(call.args[1])) return `blocked: go-getter approvals ${call.args[1]} changes what an agent may do without asking, so a person runs it; ask the user to run it themselves`;
      // A run changes what an agent may do without asking (decision 0130): a person starts and ends it.
      if (call?.args[0] === 'run' && ['start', 'end'].includes(call.args[1])) return `blocked: go-getter run ${call.args[1]} changes what an agent may do without asking, so a person runs it; ask the user to run it themselves`;
    }
  }
  const store = storeDir();
  for (const token of candidatePaths(payload, project)) {
    const abs = token.startsWith('~/') ? path.join(os.homedir(), token.slice(2)) : path.resolve(project, token);
    if (abs === store || abs.startsWith(`${store}${path.sep}`)) return 'blocked: the approvals store is changed by a person only; go-getter approvals list shows it';
  }
  return null;
}

// The first use of a secret by a command that is not approved: ask the person where the host can (leaving a pending record that
// `secret run` promotes if the person says yes), otherwise hand over.
function firstUse(project, call, host, guardrail) {
  const text = call.words.join(' ');
  if (!canPrompt(host)) {
    return { deny: true, reason: `blocked by guardrail ${guardrail}: "${text}" is not approved to use ${call.path}; ask the user to approve it by running: go-getter approvals add ${call.path} -- ${text}` };
  }
  let files = [];
  try {
    addPending(project, call.words, call.path);
    files = fileSet(call.words, project).files;
  } catch {
    // a pending record that cannot be written means the run will be refused, which is safe
  }
  const shown = files.slice(0, 6).join(', ') + (files.length > 6 ? `, and ${files.length - 6} more` : '');
  return { deny: false, ask: true, reason: `go-getter would run "${text}" with ${call.path} in its environment (values are scrubbed from its output and never shown to the agent).${files.length ? ` It runs ${files.length} file${files.length === 1 ? '' : 's'}: ${shown}.` : ''} Approving also remembers it until those files change.` };
}

// Outward shapes a remembered approval or an active run may allow (decision 0130). Null when this call is not governed that way
// (another command is gated too, the host cannot ask, or no shape is grantable): the ordinary gate applies. `{ allow: true }`
// when every outward command in the call is a grantable shape that is allowed now; otherwise, on a host whose hook can ask, a
// prompt naming why (first use of the shape, or the precondition that failed).
function shapeGate(project, entry, payload, host) {
  if (!host) return null;
  const command = shellCommand(payload);
  const args = gateArgs(entry.parsed.args);
  if (typeof command !== 'string' || !command || !args.grantable.length) return null;
  let hits;
  try {
    hits = matchGated(command, { classes: args.classes, extra: args.extra, free: args.free, provider: args.provider });
  } catch {
    return null;
  }
  if (!hits.length || hits.some((h) => !args.grantable.includes(h.id))) return null;
  const verdicts = hits.map((h) => ({ id: h.id, ...shapeAllowance(project, h.id, command) }));
  if (verdicts.every((v) => v.allowed)) return { allow: true };
  if (!canPrompt(host)) return null;
  const text = command.length > 200 ? `${command.slice(0, 200)}…` : command;
  const failed = verdicts.find((v) => v.reason);
  if (failed) return { deny: false, ask: true, reason: `go-getter: "${text}" is allowed without asking, but ${failed.reason}. Approve this one?` };
  // First use: remember the shape if the person says yes (the post-tool hook promotes it once the call ran).
  for (const v of verdicts.filter((x) => x.firstUse)) {
    try {
      addPendingShape(project, v.id, command);
    } catch {
      // not remembered: the person is asked again next time, which is safe
    }
  }
  const ids = verdicts.filter((v) => v.firstUse).map((v) => v.id).join(', ');
  return { deny: false, ask: true, reason: `go-getter: approve "${text}"? Approving remembers ${ids} for this project until revoked (go-getter approvals revoke), and its preconditions (green checks, default branch, a step of the run) are checked at each use.` };
}

// MCP tool classes (decision 0138 item 2). A tool the project marked read is free; any other tool is a write, decided like an outward
// shape: a run's grant or a remembered approval allows it, else the person is asked where the hook can ask and told what to run where
// it cannot. Applies only to an entry with a `reads` argument and a host that shows the server (fact 0036).
function mcpClassGate(project, entry, name, host) {
  if (entry.parsed.args?.reads === undefined) return null;
  const call = mcpCall(name);
  if (!call?.server || isReadTool(call, entry.parsed.args)) return null;
  const id = mcpShapeId(call);
  const text = `${call.server} ${call.tool}`;
  if (!MCP_SHAPE.test(id)) return { deny: true, reason: `blocked by guardrail ${entry.guardrail}: MCP tool "${text}" has a name go-getter cannot approve once; mark it read or ask the user to use it another way` };
  const verdict = shapeAllowance(project, id, name);
  if (verdict.allowed) return null;
  if (host && canPrompt(host)) {
    try {
      addPendingShape(project, id, name);
    } catch {
      // not remembered: the person is asked again next time, which is safe
    }
    return { deny: false, ask: true, reason: `go-getter: MCP tool "${text}" is not marked read. Approving remembers ${id} for this project until revoked (go-getter approvals revoke ${id}); the server must stay on the allowlist.` };
  }
  return { deny: true, reason: `blocked by guardrail ${entry.guardrail}: MCP tool "${text}" is not marked read and needs a human; ask the user to mark it read in the project's answer or to run: go-getter approvals allow ${id}` };
}

// After a call the hook asked about has run, the person said yes: remember its shape.
function promoteShapes(project, payload) {
  const command = shellCommand(payload) ?? (mcpCall(toolName(payload))?.server ? toolName(payload) : undefined);
  if (typeof command !== 'string' || !command) return;
  for (let id = takePendingShape(project, command); id; id = takePendingShape(project, command)) addShape(project, id, {});
}

// A denial inside a run is counted against the step in progress, by guardrail id (decision 0130 item 8); best effort.
function recordDenial(project, result) {
  try {
    const run = activeRun(project);
    if (!run) return;
    const plan = readPlan(path.join(project, run.plan));
    const current = plan.steps.find((s) => run.steps.includes(s.id) && s.state === 'in progress') ?? plan.steps.find((s) => run.steps.includes(s.id) && s.state === 'pending');
    if (current) noteEvent(project, 'denial', current.id, /guardrail ([a-z0-9-]+)/.exec(result.reason ?? '')?.[1] ?? 'hook');
  } catch {
    // counting must never change the decision
  }
}

export function evaluatePreTool(project, payload, host) {
  const result = decidePreTool(project, payload, host);
  if (result.deny) recordDenial(project, result);
  return result;
}

function decidePreTool(project, payload, host) {
  let exempt;
  const forged = approvalsStoreRefusal(project, payload);
  if (forged) return { deny: true, reason: forged };
  const enforcement = collectEnforcement(project);
  checkpointBeforeCommand(project, enforcement, shellCommand(payload), host); // best effort, before the decision, never changes it
  for (const e of enforcement) {
    if (e.tier !== 2 || e.parsed?.kind !== 'builtin') continue;
    if (e.parsed.id === 'gate-command') {
      const shaped = shapeGate(project, e, payload, host);
      if (shaped && !shaped.allow) return shaped;
      const gated = shaped?.allow ? null : gatedCommand(e, payload, host);
      if (gated) return { deny: true, reason: `blocked by guardrail ${e.guardrail}: "${gated.command}" is an ${gated.class} command and needs a human; ask the user to run it themselves` };
      const byIdentity = identityGate(project, e, payload, host);
      if (byIdentity) return byIdentity;
      continue;
    }
    if (e.parsed.id === 'mcp-scan') {
      if (!mcpCall(toolName(payload))) continue;
      const kinds = secretKinds(toolInput(payload));
      if (kinds.length) return { deny: true, reason: `blocked by guardrail ${e.guardrail}: the arguments of this MCP call contain a secret (${kinds.join(', ')}); remove it and pass it another way` };
      continue;
    }
    if (e.parsed.id === 'mcp-allow') {
      const why = mcpDenial(toolName(payload), e.parsed.args);
      if (why) return { deny: true, reason: `blocked by guardrail ${e.guardrail}: ${why}` };
      const classed = mcpClassGate(project, e, toolName(payload), host);
      if (classed) return classed;
      continue;
    }
    if (e.parsed.id === 'deny-path') {
      const patterns = patternsOf(e.parsed.args);
      const hits = candidatePaths(payload, project).filter((p) => matchesAny(p, patterns));
      if (hits.length && exempt === undefined) exempt = exemption(project, payload);
      const allowed = (p) => {
        if (!exempt || !exempt.names.has(p)) return false;
        // the secret itself: only for an approved command, and never a path whose mode is sink (written, not read)
        if (exempt.call && p === exempt.call.path) return exempt.approved && modeOf(p, patterns, exempt.modes) !== 'sink';
        return modeOf(p, patterns, exempt.modes) === exempt.mode;
      };
      const hit = hits.find((p) => !allowed(p));
      if (hit && exempt?.call && hit === exempt.call.path && modeOf(hit, patterns, exempt.modes) !== 'sink' && hits.every((h) => h === hit || allowed(h))) return firstUse(project, exempt.call, host, e.guardrail);
      if (hit) return { deny: true, reason: `blocked by guardrail ${e.guardrail}: ${toolName(payload) ?? 'tool call'} names "${hit}", a denied path` };
    }
  }
  return { deny: false };
}

// Tier-2 tool-output redaction (decision 0072): `go-getter hook post-tool` replaces secrets in a tool result with
// REDACTED where the host can replace output (capability hooks.rewriteOutput). Heuristic, like every hook layer.
export const REDACTED = '[redacted by go-getter]';
// A value shorter than this (`true`, `3000`) is left alone: redacting it would scramble ordinary output.
const MIN_VALUE = 8;
const MAX_FILE = 256 * 1024;
const SKIP_DIRS = new Set(['.git', 'node_modules']);

// Restricted patterns of the adopted tier-2 deny-path guardrails.
export function restrictedPatterns(project) {
  return collectEnforcement(project)
    .filter((e) => e.tier === 2 && e.parsed?.kind === 'builtin' && e.parsed.id === 'deny-path')
    .flatMap((e) => patternsOf(e.parsed.args));
}

// Values of the `KEY=value` lines of every restricted file in the project. All modes count: the model sees no value of a
// `use` or `sink` file either, since `secret run` scrubs a command's output and `secret put` prints none.
export function restrictedValues(project, patterns = restrictedPatterns(project)) {
  const values = new Set();
  if (!patterns.length) return values;
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
        continue;
      }
      if (!ent.isFile() || !matchesAny(path.relative(project, abs), patterns)) continue;
      try {
        if (statSync(abs).size > MAX_FILE) continue;
        for (const line of readFileSync(abs, 'utf8').split(/\r?\n/)) {
          const m = /^\s*(?:export\s+)?[A-Za-z_][A-Za-z0-9_.-]*\s*=\s*(.*?)\s*$/.exec(line);
          if (!m) continue;
          const value = m[1].replace(/^(["'])(.*)\1$/, '$2');
          if (value.length >= MIN_VALUE) values.add(value);
        }
      } catch {
        // an unreadable file has no values to leak
      }
    }
  };
  walk(project);
  return values;
}

// Redacts one string: restricted values first (longest first, so a value inside another goes with it), then patterns.
export function redactText(text, values) {
  let count = 0;
  let out = text;
  for (const v of [...values].sort((a, b) => b.length - a.length)) {
    const parts = out.split(v);
    count += parts.length - 1;
    out = parts.join(REDACTED);
  }
  for (const re of redactionRegexes()) {
    out = out.replace(re, () => {
      count++;
      return REDACTED;
    });
  }
  return { text: out, count };
}

// Redacts every string in a tool result, keeping its shape so the host accepts it as a replacement: restricted values and
// secret patterns become REDACTED; where the project masks PII (decision 0106), email, card numbers, IBANs and the
// classes it adds become per-session pseudonyms. `masked` counts what was replaced per kind, never what it was.
export function evaluatePostTool(project, payload) {
  try {
    promoteShapes(project, payload);
  } catch {
    // remembering is best effort
  }
  const response = payload.tool_response ?? payload.toolResponse ?? payload.tool_output ?? payload.toolResult;
  const values = restrictedValues(project);
  const pii = piiConfig(project);
  const masked = {};
  let redactions = 0;
  let pseudonymizer = null;
  const walk = (v) => {
    if (typeof v === 'string') {
      const r = redactText(v, values);
      redactions += r.count;
      if (r.count) masked.secret = (masked.secret ?? 0) + r.count;
      if (!pii) return r.text;
      pseudonymizer ??= createPseudonymizer(project, sessionKeyOf(payload));
      const m = maskPii(r.text, { classes: pii.classes, pseudonymizer });
      for (const [kind, n] of Object.entries(m.kinds)) {
        masked[kind] = (masked[kind] ?? 0) + n;
        redactions += n;
      }
      return m.text;
    }
    if (Array.isArray(v)) return v.map(walk);
    if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, walk(x)]));
    return v;
  };
  let output;
  try {
    output = walk(response);
  } finally {
    pseudonymizer?.close();
  }
  if (pii) sweepPseudonyms(project);
  return { output, redactions, masked, mcp: Boolean(mcpCall(toolName(payload))) };
}

// A session ended: its pseudonym map goes (a host that never sends this leaves the 24-hour sweep).
export function evaluateSessionEnd(project, payload) {
  cleanupSession(project, sessionKeyOf(payload));
  return { ended: true };
}

// Host-specific post-tool answer: replace the result only when something was redacted. Only hosts with
// hooks.rewriteOutput get this hook installed; any other host answers nothing.
// Shapes (fact 0031): Claude Code and Copilot replace the result in place; Codex and Gemini CLI replace it with the
// text of a block decision's reason; the Kilo plugin sets `output.output` from `{ output }`.
export function respondPostTool(host, result) {
  const none = { code: 0, stdout: '', stderr: '' };
  if (!result.redactions) return none;
  const text = (v) => (typeof v === 'string' ? v : JSON.stringify(v));
  const answer = (value) => ({ code: 0, stdout: JSON.stringify(value), stderr: '' });
  const out = result.output;
  if (host === 'claude-code') {
    const key = result.mcp ? 'updatedMCPToolOutput' : 'updatedToolOutput';
    return answer({ hookSpecificOutput: { hookEventName: 'PostToolUse', [key]: out } });
  }
  if (host === 'copilot') return answer({ modifiedResult: { resultType: 'success', textResultForLlm: text(out?.textResultForLlm ?? out) } });
  if (host === 'codex') return answer({ decision: 'block', reason: text(out) });
  if (host === 'gemini-cli') return answer({ decision: 'deny', reason: text(out?.llmContent ?? out) });
  if (host === 'kilo') return answer({ output: text(out) });
  // Cursor replaces MCP results only (fact 0031); the shape of its post-tool input is unconfirmed.
  if (host === 'cursor') return result.mcp ? answer({ updated_mcp_tool_output: out }) : none;
  return none;
}

// Host-specific answer: exit 2 + stderr where that blocks; Copilot reads a JSON decision.
export function respond(host, decision) {
  if (decision.ask && host === 'claude-code') {
    return { code: 0, stdout: JSON.stringify({ hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'ask', permissionDecisionReason: decision.reason } }), stderr: '' };
  }
  if (!decision.deny) return { code: 0, stdout: '', stderr: '' };
  if (host === 'copilot') return { code: 0, stdout: JSON.stringify({ permissionDecision: 'deny', permissionDecisionReason: decision.reason }), stderr: '' };
  return { code: 2, stdout: '', stderr: decision.reason };
}

// Session start: run vendored nudge scripts (POSIX sh, plain-text output) in the project; failures are silent.
export const NUDGES = ['capture-nudge.sh', 'lint-nudge.sh'];
// Nudge output enters context on every session start (decision 0070), so it has a fixed line budget.
export const NUDGE_LINE_BUDGET = 20;

export function capLines(text, budget = NUDGE_LINE_BUDGET) {
  const lines = text ? text.split('\n') : [];
  if (lines.length <= budget) return text;
  return [...lines.slice(0, budget - 1), `… ${lines.length - budget + 1} more nudge lines cut`].join('\n');
}

export function sessionNudges(packageRoot, project) {
  const lines = [];
  for (const script of NUDGES) {
    const file = path.join(packageRoot, 'src/hooks', script);
    if (!existsSync(file)) continue;
    try {
      const out = execFileSync('sh', [file], { cwd: project, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], timeout: 10000 }).trim();
      if (out) lines.push(out);
    } catch {
      // a nudge must never block a session
    }
  }
  try {
    const drift = driftNudge(project, packageRoot);
    if (drift) lines.push(drift);
  } catch {
    // a nudge must never block a session
  }
  return capLines(lines.join('\n'));
}

// Token and cost fields a host's hook payload carries (decision 0087). Only Claude Code documents any: a resumed
// session-start brings the context size, whether its prompt cache likely expired, and the estimated cache-write cost.
export function payloadUsage(payload) {
  const n = payload.context_tokens;
  if (!Number.isInteger(n) || n < 0) return {};
  const expired = payload.prompt_cache_likely_expired === true;
  const usage = { tokens: expired ? { cacheWrite: n } : { cacheRead: n } };
  if (expired && FIELDS.cost(payload.estimated_cache_write_usd)) usage.cost = payload.estimated_cache_write_usd;
  return usage;
}

// Telemetry record for a hook event: metadata the host's payload carries (model, effort, tokens, cost), never tool
// input or output. A post-tool event adds only the count of redactions.
export function hookRecord(event, host, payload, decision, redactions, masked) {
  const rec = { event };
  if (host) rec.host = host;
  const model = typeof payload.model === 'string' ? payload.model : payload.model?.id;
  if (FIELDS.model(model)) rec.model = model;
  if (FIELDS.effort(payload.effort)) rec.effort = payload.effort;
  Object.assign(rec, payloadUsage(payload));
  if (decision) rec.outcome = decision.deny ? 'denied' : 'allowed';
  if (FIELDS.redactions(redactions)) rec.redactions = redactions;
  if (FIELDS.masked(masked)) rec.masked = masked;
  return rec;
}
