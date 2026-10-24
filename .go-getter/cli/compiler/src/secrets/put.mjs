// `go-getter secret put` (decision 0107): writes a `sink` path from stdin or from a command the project declared for that
// path, without the model reading the value back. The file gets mode 0600 through a temporary file in the same directory
// and a rename, so a failing source leaves an existing file as it was. Only a byte count is printed.
import { spawn } from 'node:child_process';
import { chmodSync, closeSync, fsyncSync, lstatSync, mkdirSync, openSync, realpathSync, renameSync, rmSync, writeSync } from 'node:fs';
import { StringDecoder } from 'node:string_decoder';
import path from 'node:path';
import { adoptedData } from '../governance.mjs';
import { matchesAny } from '../glob.mjs';
import { pathMode, restrictedModes } from '../hook.mjs';
import { scrub } from './run.mjs';

const MAX_VALUE = 1024 * 1024;
const SOURCE_TIMEOUT_MS = 30_000;
const USAGE = 'usage: go-getter secret put <path> (--stdin | --from-command <source>)';

// "<pattern>|<name>|<command>" entries of the `sink-sources` answer: the commands declared for each sink pattern.
export function sinkSources(project) {
  const out = [];
  for (const entry of String(adoptedData(project, 'sink-sources') ?? '').split(/,\s+/)) {
    const [pattern, name, ...rest] = entry.split('|');
    const command = rest.join('|').trim();
    if (pattern?.trim() && name?.trim() && command) out.push({ pattern: pattern.trim(), name: name.trim(), command });
  }
  return out;
}

function parseArgs(args) {
  const [target, ...rest] = args;
  if (!target || target.startsWith('--')) return { error: 'a path to write comes first' };
  const opts = {};
  for (let i = 0; i < rest.length; i++) {
    if (rest[i] === '--stdin') opts.stdin = true;
    else if (rest[i] === '--from-command' && rest[i + 1] && !rest[i + 1].startsWith('--')) opts.source = rest[++i];
    else return { error: `unknown or incomplete argument "${rest[i]}"` };
  }
  if (Boolean(opts.stdin) === Boolean(opts.source)) return { error: 'give exactly one of --stdin and --from-command' };
  return { target, ...opts };
}

// The project-relative form of `target`, or a reason it cannot be written: it must resolve inside the project, through no
// symlink, and not be a directory.
function resolveTarget(project, target) {
  const root = realpathSync(project);
  const abs = path.resolve(project, target);
  const rel = path.relative(path.resolve(project), abs).split(path.sep).join('/');
  if (!rel || rel.startsWith('..') || path.isAbsolute(rel)) return { reason: `"${target}" is outside the project` };
  // Every existing part of the path must be a plain directory or file inside the project (no symlink to elsewhere).
  let at = root;
  for (const part of rel.split('/')) {
    at = path.join(at, part);
    let st;
    try {
      st = lstatSync(at);
    } catch {
      break; // the rest does not exist yet
    }
    if (st.isSymbolicLink()) return { reason: `"${target}" passes through a symbolic link` };
  }
  try {
    if (lstatSync(abs).isDirectory()) return { reason: `"${target}" is a directory` };
  } catch {
    // does not exist yet
  }
  return { abs, rel };
}

function readStdin(stream) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    stream.on('data', (d) => {
      size += d.length;
      if (size > MAX_VALUE) reject(new Error(`the value is larger than ${MAX_VALUE} bytes`));
      else chunks.push(d);
    });
    stream.on('end', () => resolve(Buffer.concat(chunks)));
    stream.on('error', reject);
  });
}

// Runs a declared source command (split on spaces, no shell) and returns its standard output.
function runSource(project, command) {
  return new Promise((resolve, reject) => {
    const [bin, ...argv] = command.split(/\s+/);
    let child;
    try {
      child = spawn(bin, argv, { cwd: project, stdio: ['ignore', 'pipe', 'pipe'], shell: false });
    } catch (e) {
      reject(new Error(`cannot run the source: ${e.code ?? 'error'}`));
      return;
    }
    const out = [];
    const err = [];
    let size = 0;
    const timer = setTimeout(() => child.kill('SIGKILL'), SOURCE_TIMEOUT_MS);
    child.stdout.on('data', (d) => {
      size += d.length;
      if (size > MAX_VALUE) child.kill('SIGKILL');
      else out.push(d);
    });
    child.stderr.on('data', (d) => err.push(d));
    child.on('error', (e) => {
      clearTimeout(timer);
      reject(new Error(`cannot run the source: ${e.code ?? 'error'}`));
    });
    child.on('close', (code, signal) => {
      clearTimeout(timer);
      if (size > MAX_VALUE) return reject(new Error(`the source produced more than ${MAX_VALUE} bytes`));
      if (code !== 0) {
        // The source's own error text helps (item not found), scrubbed of secret patterns and cut short.
        const decoder = new StringDecoder('utf8');
        const text = scrub(decoder.write(Buffer.concat(err)) + decoder.end(), new Set()).trim().slice(0, 300);
        return reject(new Error(`the source failed (${signal ? `signal ${signal}` : `exit ${code}`})${text ? `: ${text}` : ''}`));
      }
      resolve(Buffer.concat(out));
    });
  });
}

// Writes `value` to `abs` with mode 0600 via a temporary file in the same directory and a rename.
function writeAtomically(abs, value) {
  mkdirSync(path.dirname(abs), { recursive: true, mode: 0o700 });
  const tmp = `${abs}.${process.pid}.${Date.now()}.tmp`;
  let fd;
  try {
    fd = openSync(tmp, 'wx', 0o600);
    writeSync(fd, value);
    fsyncSync(fd);
    closeSync(fd);
    fd = undefined;
    chmodSync(tmp, 0o600);
    renameSync(tmp, abs);
  } catch (e) {
    if (fd !== undefined) closeSync(fd);
    rmSync(tmp, { force: true });
    throw e;
  }
}

// Resolves { wrote, bytes }, or { refused } with the reason (and writes nothing). `stdin` is read only for --stdin.
export async function putSecret(project, args, { stdin = process.stdin } = {}) {
  const parsed = parseArgs(args);
  if (parsed.error) return { refused: `${parsed.error}\n${USAGE}`, usage: true };
  let resolved;
  try {
    resolved = resolveTarget(project, parsed.target);
  } catch {
    return { refused: `"${parsed.target}" cannot be resolved` };
  }
  if (resolved.reason) return { refused: resolved.reason };
  const { abs, rel } = resolved;
  const mode = pathMode(project, rel);
  if (mode !== 'sink') return { refused: `"${rel}" is not a sink path (its mode is ${mode}); only a path listed as sink:<pattern> in the restricted-modes answer can be written` };

  let value;
  try {
    if (parsed.stdin) {
      value = await readStdin(stdin);
    } else {
      const modes = restrictedModes(project);
      const declared = sinkSources(project).filter((s) => modes.get(s.pattern) === 'sink' && matchesAny(rel, [s.pattern]));
      if (!declared.length) return { refused: `no source is declared for "${rel}": add "<pattern>|<name>|<command>" to the sink-sources answer (a human decides where a secret may come from)` };
      const source = declared.find((s) => s.name === parsed.source);
      if (!source) return { refused: `"${parsed.source}" is not a source declared for "${rel}"; declared: ${declared.map((s) => `"${s.name}"`).join(', ')}` };
      value = await runSource(project, source.command);
    }
  } catch (e) {
    return { refused: e.message };
  }
  if (!value.length) return { refused: 'the source produced no value; nothing was written' };
  try {
    writeAtomically(abs, value);
  } catch (e) {
    return { refused: `cannot write "${rel}": ${e.code ?? 'error'}` };
  }
  return { wrote: rel, bytes: value.length };
}
