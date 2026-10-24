// Watcher noise control (plan A.3, decision 0070): `go-getter watch` wraps an agent-started watch command so that
// each output line does not wake a model turn. It reports state changes, collapses duplicates and bursts, caps
// notifications per hour with one notice and ends with a summary; `--until done` prints only the final result.
import { spawn } from 'node:child_process';
import path from 'node:path';
import { adoptedData, packageCapabilities } from './governance.mjs';
import { readArtifacts } from './artifacts.mjs';

const HOUR_MS = 60 * 60 * 1000;
const TAIL_LINES = 15;
const COMMAND_CHARS = 80;
// Starting values for calibration (0017). `key` decides what counts as the same state.
export const LEVELS = {
  quiet: { windowMs: 60_000, perHour: 6, key: stateKey },
  normal: { windowMs: 10_000, perHour: 30, key: stateKey },
  verbose: { windowMs: 0, perHour: Infinity, key: (line) => line },
};
export const DEFAULT_LEVEL = 'quiet';

const ANSI = /\x1b\[[0-?]*[ -/]*[@-~]/g;
const clean = (line) => line.replace(ANSI, '').trimEnd();
// Counters, timestamps and durations change on every poll without changing the state they report.
export function stateKey(line) {
  return line.replace(/\d+/g, '#').replace(/\s+/g, ' ').trim().toLowerCase();
}

// Flag first, then the adopted `go-getter.watcher-noise` decision, then the plugin default.
export function resolveLevel(project, flag) {
  const level = flag ?? adoptedData(project, 'watcher-noise') ?? DEFAULT_LEVEL;
  if (!Object.hasOwn(LEVELS, level)) throw new Error(`unknown noise level "${level}" (quiet, normal, verbose)`);
  return level;
}

export function formatDuration(ms) {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`;
  return `${Math.floor(s / 3600)}h ${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}m`;
}

// A line-fed watcher. `write` receives whole line groups (one call per notification); clock and timers are
// injectable for tests.
export function createWatcher({ level = DEFAULT_LEVEL, until = false, command = '', write, now = Date.now, setTimer = setTimeout, clearTimer = clearTimeout }) {
  const { windowMs, perHour, key } = LEVELS[level];
  const started = now();
  const tail = [];
  const sent = [];
  let lines = 0, states = 0, notifications = 0, seenKey = null, emittedKey = null, lastEmitAt = -Infinity;
  let pending = null, timer = null, noticeSent = false, last = null;

  const arm = (ms) => {
    if (!timer) timer = setTimer(() => { timer = null; flush(); }, Math.max(0, ms));
  };
  function flush() {
    if (pending === null) return;
    const t = now();
    if (t < lastEmitAt + windowMs) return arm(lastEmitAt + windowMs - t);
    while (sent.length && sent[0] <= t - HOUR_MS) sent.shift();
    if (sent.length >= perHour) {
      if (!noticeSent) {
        write(`watch: ${perHour} notifications this hour (${level}); holding further output until the run ends or the hour frees a slot`);
        noticeSent = true;
      }
      return arm(sent[0] + HOUR_MS - t);
    }
    write(pending);
    emittedKey = key(pending);
    lastEmitAt = t;
    sent.push(t);
    notifications += 1;
    noticeSent = false;
    pending = null;
  }

  return {
    line(raw) {
      const text = clean(String(raw));
      if (!text.trim()) return;
      lines += 1;
      last = text;
      tail.push(text);
      if (tail.length > TAIL_LINES) tail.shift();
      if (until) return;
      const k = key(text);
      if (k !== seenKey) states += 1;
      seenKey = k;
      if (k === emittedKey) {
        pending = null; // back to the reported state: nothing new to say
        return;
      }
      pending = text;
      flush();
    },
    // Ends the watch and writes the result group. Returns the outcome.
    finish({ code = null, signal = null, error = null } = {}) {
      if (timer) clearTimer(timer);
      timer = null;
      const ok = code === 0 && !signal && !error;
      const exit = error ? error : signal ? `signal ${signal}` : `exit ${code}`;
      const cmd = command.length > COMMAND_CHARS ? `${command.slice(0, COMMAND_CHARS - 1)}…` : command;
      const counts = until ? '' : `; ${lines} lines, ${states} states, ${notifications} notified`;
      const group = [`watch: ${ok ? 'ok' : 'failed'} in ${formatDuration(now() - started)} (${exit}${counts})${cmd ? `: ${cmd}` : ''}`];
      if (!ok) group.push(...tail.map((l) => `  ${l}`));
      else if (!until && last !== null && key(last) !== emittedKey) group.push(`  last: ${last}`);
      write(group.join('\n'));
      return { ok, lines, states, notifications };
    },
  };
}

// Splits a stream into lines and feeds them to `onLine`; returns a function that flushes the remainder.
function lineReader(stream, onLine) {
  let buf = '';
  stream.setEncoding('utf8');
  stream.on('data', (chunk) => {
    buf += chunk;
    const parts = buf.split(/\r?\n|\r/);
    buf = parts.pop();
    for (const p of parts) onLine(p);
  });
  return () => {
    if (buf) onLine(buf);
    buf = '';
  };
}

// Runs `argv` (one argument runs through the shell) under a watcher; resolves to the exit code to return.
export function runWatch(argv, { level, until, write = (text) => process.stdout.write(`${text}\n`) }) {
  const command = argv.join(' ');
  const watcher = createWatcher({ level, until, command, write });
  return new Promise((resolve) => {
    const child = argv.length === 1 ? spawn(argv[0], { shell: true, stdio: ['ignore', 'pipe', 'pipe'] }) : spawn(argv[0], argv.slice(1), { stdio: ['ignore', 'pipe', 'pipe'] });
    const ends = [lineReader(child.stdout, watcher.line), lineReader(child.stderr, watcher.line)];
    const forward = (sig) => child.kill(sig);
    process.on('SIGINT', forward).on('SIGTERM', forward);
    let done = false;
    const finish = (result, exitCode) => {
      if (done) return;
      done = true;
      process.off('SIGINT', forward).off('SIGTERM', forward);
      for (const end of ends) end();
      watcher.finish(result);
      resolve(exitCode);
    };
    child.on('error', (err) => finish({ error: err.code ?? err.message }, 127));
    child.on('close', (code, signal) => finish({ code, signal }, signal ? 1 : code));
  });
}

// Tier 2 (decision 0070, fact 0026): a pre-tool hook wraps the host watcher tool's command in `go-getter watch` once
// the project has adopted the `watches-use-the-wrapper` guardrail. Returns { rewrite: { input } } or null.
export const WRAPPER_GUARDRAIL = 'watches-use-the-wrapper';
const WRAPPED = /(^|[\s/'"])go-getter['"]?\s+watch(\s|$)/;
const shellQuote = (s) => `'${s.replace(/'/g, `'\\''`)}'`;

export function wrapWatch(project, host, payload, { capabilities = packageCapabilities() } = {}) {
  const watcher = capabilities[host]?.hooks.watcher;
  if (!watcher || payload.tool_name !== watcher.tool) return null;
  const input = payload.tool_input;
  const command = input?.[watcher.field];
  if (typeof command !== 'string' || !command.trim() || WRAPPED.test(command)) return null;
  if (!readArtifacts(project, ['guardrails']).some((g) => g.id === WRAPPER_GUARDRAIL && g.data.status === 'active')) return null;
  const runner = path.join(project, '.go-getter', 'bin', 'go-getter');
  return { rewrite: { input: { ...input, [watcher.field]: `sh ${shellQuote(runner)} watch -- ${shellQuote(command)}` } } };
}
