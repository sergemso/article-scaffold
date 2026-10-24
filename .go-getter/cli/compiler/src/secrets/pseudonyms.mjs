// Per-session pseudonyms for masked PII (decision 0106): the same value gets the same name within a session
// (`[email-1]`, `[email-2]`). The map holds `{ salt, hash(salt, kind, value) -> n }` and never a value, in a 0600 file in
// the restricted state directory; a session's file is deleted when its session ends, and any file untouched for 24
// hours is swept (a host may never send an end event, or the process may be killed). Hooks run as separate processes,
// possibly in parallel, so a lock file held for a masking pass keeps two of them from handing out the same number.
import { createHash, randomBytes } from 'node:crypto';
import { chmodSync, closeSync, mkdirSync, openSync, readFileSync, readdirSync, renameSync, rmSync, statSync, utimesSync, writeFileSync } from 'node:fs';
import path from 'node:path';

export const MAX_AGE_MS = 24 * 60 * 60 * 1000;
export const PSEUDONYM_DIR = path.join('.go-getter', 'state', 'pseudonyms');

const dirOf = (project) => path.join(project, PSEUDONYM_DIR);
// The file name comes from a hash of the session key, so a key can never name a path.
const fileOf = (project, sessionKey) => path.join(dirOf(project), `${createHash('sha256').update(String(sessionKey)).digest('hex').slice(0, 32)}.json`);
const sleep = (ms) => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);

// Takes the lock for a session's file, waiting up to about 200 ms; past that it carries on without it (masking must not
// hang a tool call). `release()` is safe to call twice.
function acquire(file) {
  const lock = `${file}.lock`;
  let fd = null;
  for (let attempt = 0; attempt < 40 && fd === null; attempt++) {
    try {
      fd = openSync(lock, 'wx', 0o600);
    } catch {
      try {
        // A lock older than a few seconds belongs to a process that died.
        if (Date.now() - statSync(lock).mtimeMs > 5000) rmSync(lock, { force: true });
      } catch {
        // released in the meantime
      }
      sleep(5);
    }
  }
  return {
    release() {
      if (fd === null) return;
      closeSync(fd);
      fd = null;
      rmSync(lock, { force: true });
    },
  };
}

function load(file) {
  try {
    const data = JSON.parse(readFileSync(file, 'utf8'));
    if (typeof data.salt === 'string' && data.maps && typeof data.maps === 'object') return data;
  } catch {
    // missing or unreadable: start a new map
  }
  return { salt: randomBytes(16).toString('hex'), maps: {} };
}

function save(file, data) {
  const tmp = `${file}.${process.pid}.tmp`;
  writeFileSync(tmp, JSON.stringify(data), { mode: 0o600 });
  chmodSync(tmp, 0o600);
  renameSync(tmp, file);
}

// A pseudonymizer for one session: `name(kind, value)` returns the stable name; `close()` writes the map once and
// releases the lock, so call it in a `finally`. The lock is held from here to `close()`, which keeps two parallel hooks
// from handing out the same number.
export function createPseudonymizer(project, sessionKey) {
  mkdirSync(dirOf(project), { recursive: true, mode: 0o700 });
  const file = fileOf(project, sessionKey);
  const lock = acquire(file);
  const data = load(file);
  const hashOf = (kind, value) => createHash('sha256').update(`${data.salt}\0${kind}\0${value}`).digest('hex');
  return {
    name(kind, value) {
      const hash = hashOf(kind, value);
      const map = (data.maps[kind] ??= {});
      if (map[hash] === undefined) map[hash] = Object.keys(map).length + 1;
      return `[${kind}-${map[hash]}]`;
    },
    close() {
      try {
        save(file, data);
        const now = new Date();
        utimesSync(file, now, now);
      } finally {
        lock.release();
      }
    },
  };
}

// Deletes a session's map (its session ended).
export function cleanupSession(project, sessionKey) {
  rmSync(fileOf(project, sessionKey), { force: true });
  rmSync(`${fileOf(project, sessionKey)}.lock`, { force: true });
}

// Deletes every map not touched within `maxAgeMs`; returns how many.
export function sweepPseudonyms(project, { now = Date.now(), maxAgeMs = MAX_AGE_MS } = {}) {
  let removed = 0;
  let names;
  try {
    names = readdirSync(dirOf(project));
  } catch {
    return 0;
  }
  for (const name of names) {
    const file = path.join(dirOf(project), name);
    try {
      if (now - statSync(file).mtimeMs > maxAgeMs) {
        rmSync(file, { force: true });
        removed++;
      }
    } catch {
      // gone already
    }
  }
  return removed;
}
