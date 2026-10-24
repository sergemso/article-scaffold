// `go-getter secret run` (decision 0107): runs a command with a `use` secret in its environment, or as a temporary file,
// without the model seeing the content. It runs only commands the project approved for that secret, and scrubs the
// child's output of the values and of the shared secret patterns before printing it. The content is never printed, put
// in an argument, logged or recorded in telemetry.
import { spawn } from 'node:child_process';
import { StringDecoder } from 'node:string_decoder';
import { chmodSync, mkdtempSync, readdirSync, readFileSync, realpathSync, rmSync, statSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { matchesAny } from '../glob.mjs';
import { restrictedModes, restrictedPatterns } from '../hook.mjs';
import { redactionRegexes } from './patterns.mjs';
import { useCommands, parseRunArgs, sharedApproved, USAGE } from './use.mjs';
import { approved as personallyApproved, add as approve, takePending } from './approvals.mjs';

export { useCommands };

export const REDACTED = '[redacted by go-getter]';
// A value shorter than this (`true`, `3000`) is left in the output: scrubbing it would scramble ordinary text.
const MIN_VALUE = 8;
// A line longer than this is flushed in pieces, keeping a tail as long as the longest value so none is cut in two.
const MAX_PENDING = 1024 * 1024;
const COPY_PREFIX = 'gg-secret-';
const STALE_COPY_MS = 24 * 60 * 60 * 1000;

// The KEY=VALUE entries of a dotenv file: comments, `export `, single and double quotes, and a quoted value over several
// lines. Returns [[key, value]] in file order.
export function dotenvEntries(text) {
  const entries = [];
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const m = /^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/.exec(lines[i]);
    if (!m) continue;
    const [, key, rest] = m;
    const quote = rest[0] === '"' || rest[0] === "'" ? rest[0] : null;
    if (quote) {
      let body = rest.slice(1);
      while (!body.includes(quote) && i + 1 < lines.length) body += `\n${lines[++i]}`;
      const end = body.indexOf(quote);
      let value = end === -1 ? body : body.slice(0, end);
      if (quote === '"') value = value.replace(/\\n/g, '\n').replace(/\\"/g, '"').replace(/\\\\/g, '\\');
      entries.push([key, value]);
    } else {
      entries.push([key, rest.replace(/\s+#.*$/, '').trim()]);
    }
  }
  return entries;
}

// Scrubs `text` of every value (longest first) and of the shared secret patterns.
export function scrub(text, values) {
  let out = text;
  for (const v of [...values].sort((a, b) => b.length - a.length)) out = out.split(v).join(REDACTED);
  for (const re of redactionRegexes()) out = out.replace(re, REDACTED);
  return out;
}

// Streams a command's output a line at a time, scrubbed: a value never spans lines, so a complete line is safe to scrub on
// its own, and a command that runs for a while (a dev server) shows its output as it goes.
function lineScrubber(values, write) {
  const decoder = new StringDecoder('utf8');
  const keep = Math.max(64, ...[...values].map((v) => v.length));
  let pending = '';
  return {
    push(chunk) {
      pending += decoder.write(chunk);
      let at;
      while ((at = pending.indexOf('\n')) !== -1) {
        write(`${scrub(pending.slice(0, at), values)}\n`);
        pending = pending.slice(at + 1);
      }
      if (pending.length > MAX_PENDING) {
        write(scrub(pending.slice(0, pending.length - keep), values));
        pending = pending.slice(pending.length - keep);
      }
    },
    end() {
      pending += decoder.end();
      if (pending) write(scrub(pending, values));
      pending = '';
    },
  };
}

// Removes copies a hard kill left behind (a signal we cannot catch): our own `gg-secret-*` directories older than a day.
function sweepStaleCopies() {
  try {
    for (const name of readdirSync(os.tmpdir())) {
      if (!name.startsWith(COPY_PREFIX)) continue;
      const dir = path.join(os.tmpdir(), name);
      const st = statSync(dir);
      if (st.isDirectory() && st.uid === process.getuid?.() && Date.now() - st.mtimeMs > STALE_COPY_MS) rmSync(dir, { recursive: true, force: true });
    }
  } catch {
    // best effort
  }
}

// Why a call is refused, or null. A command may use a restricted path when the project's shared list names it (for a `use` path),
// when the user approved it and its code is unchanged (decision 0126), or when the pre-tool hook just asked the person and left
// a pending record, which is then promoted to an approval. Never names a value.
function refusal(project, rel, words) {
  if (!matchesAny(rel, restrictedPatterns(project))) return `"${rel}" is not a restricted path of this project, so there is nothing to pass to a command`;
  const text = words.join(' ');
  if (sharedApproved(project, rel, text, restrictedModes(project))) return null;
  if (personallyApproved(project, words, rel)) return null;
  if (takePending(project, words, rel)) {
    approve(project, words, rel, { host: process.env.GO_GETTER_HOST });
    return null;
  }
  return `"${text}" is not approved to use "${rel}". Run it through the agent host so the person is asked once (it is remembered while the command's code is unchanged), or a person runs: go-getter approvals add ${rel} -- ${text}`;
}

// Runs the command, writing its scrubbed output through `out` and `err` as it arrives; resolves { code }, or { refused }
// with the reason (and runs nothing).
export async function runSecret(project, args, { env = process.env, out = (t) => process.stdout.write(t), err = (t) => process.stderr.write(t) } = {}) {
  const parsed = parseRunArgs(args);
  if (parsed.error) return { refused: `${parsed.error}\n${USAGE}`, usage: true };
  const given = parsed.from ?? parsed.file;
  let real;
  let rel;
  try {
    const root = realpathSync(project);
    real = realpathSync(path.resolve(project, given));
    if (real !== root && !real.startsWith(`${root}${path.sep}`)) return { refused: `"${given}" is outside the project` };
    if (!statSync(real).isFile()) return { refused: `"${given}" is not a file` };
    rel = path.relative(root, real).split(path.sep).join('/');
  } catch {
    return { refused: `"${given}" cannot be read` };
  }
  const why = refusal(project, rel, parsed.command);
  if (why) return { refused: why };

  // Signals are caught before anything is created, so a copy on disk is always removed: a signal that arrives before the
  // command starts stops the run, and one that arrives later is passed to the command, whose exit ends the run.
  let child = null;
  let aborted = null;
  const relay = (signal) => () => {
    if (child) child.kill(signal);
    else aborted = signal;
  };
  const handlers = { SIGINT: relay('SIGINT'), SIGTERM: relay('SIGTERM') };
  for (const [sig, h] of Object.entries(handlers)) process.on(sig, h);

  let tempDir = null;
  try {
    const content = readFileSync(real, 'utf8');
    const childEnv = { ...env };
    const values = new Set();
    if (parsed.from) {
      for (const [key, value] of dotenvEntries(content)) {
        childEnv[key] = value;
        if (value.length >= MIN_VALUE) values.add(value);
        // A value over several lines is scrubbed line by line too, since output is scrubbed a line at a time.
        if (value.includes('\n')) for (const line of value.split('\n').map((l) => l.trim())) if (line.length >= MIN_VALUE) values.add(line);
      }
    } else {
      sweepStaleCopies();
      tempDir = mkdtempSync(path.join(os.tmpdir(), COPY_PREFIX));
      chmodSync(tempDir, 0o700);
      const copy = path.join(tempDir, path.basename(real));
      writeFileSync(copy, content, { mode: 0o600 });
      chmodSync(copy, 0o600);
      childEnv[parsed.env ?? `${path.basename(real).toUpperCase().replace(/[^A-Z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'SECRET'}_FILE`] = copy;
      if (content.trim().length >= MIN_VALUE) values.add(content.trim());
      for (const line of content.split(/\r?\n/).map((l) => l.trim())) if (line.length >= 16) values.add(line);
    }
    if (aborted) return { code: aborted === 'SIGINT' ? 130 : 143 };

    return await new Promise((resolve) => {
      try {
        child = spawn(parsed.command[0], parsed.command.slice(1), { cwd: project, env: childEnv, stdio: ['ignore', 'pipe', 'pipe'], shell: false });
      } catch (e) {
        resolve({ refused: `cannot run "${parsed.command[0]}": ${e.code ?? 'error'}` });
        return;
      }
      if (aborted) child.kill(aborted);
      const stdout = lineScrubber(values, out);
      const stderr = lineScrubber(values, err);
      child.stdout.on('data', (d) => stdout.push(d));
      child.stderr.on('data', (d) => stderr.push(d));
      child.on('error', (e) => resolve({ refused: `cannot run "${parsed.command[0]}": ${e.code ?? 'error'}` }));
      child.on('close', (code, signal) => {
        stdout.end();
        stderr.end();
        resolve({ code: code ?? (signal ? 128 : 1) });
      });
    });
  } finally {
    for (const [sig, h] of Object.entries(handlers)) process.off(sig, h);
    if (tempDir) rmSync(tempDir, { recursive: true, force: true });
  }
}
