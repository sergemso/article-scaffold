// Secrets in the lines a change adds (decision 0106): the staged diff, and the commits since the base (the argument, else
// the pull request's base in CI, else origin's default branch). Existing history and untouched lines are not read. A
// line carrying `go-getter:allow-secret`, and a file matching `allow` (comma-separated globs), are skipped. A finding
// names the file, line and kind, never the value.
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { defaultBranch, cleanGitEnv } from '../../git-env.mjs';
import { findings } from '../../secrets/patterns.mjs';
import { matchesAny } from '../../glob.mjs';

export const ALLOW_MARKER = 'go-getter:allow-secret';
const LISTED = 20;
const DIFF = ['diff', '-U0', '--no-color', '--no-ext-diff', '--diff-filter=ACMR'];

const git = (project, args, env) => execFileSync('git', args, { cwd: project, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], env, maxBuffer: 256 * 1024 * 1024 });

// Added lines of a `diff -U0` as [{ file, line, text }]; binary and deleted files add none.
export function addedLines(diff) {
  const out = [];
  let file = null;
  let line = 0;
  for (const l of diff.split('\n')) {
    if (l.startsWith('+++ ')) {
      file = l === '+++ /dev/null' ? null : l.replace(/^\+\+\+ b\//, '');
    } else if (l.startsWith('@@')) {
      const m = /\+(\d+)/.exec(l);
      line = m ? Number(m[1]) : 0;
    } else if (file && l.startsWith('+') && !l.startsWith('+++')) {
      out.push({ file, line, text: l.slice(1) });
      line++;
    }
  }
  return out;
}

// The environment git runs in: the hooked repository's variables are dropped (a surrounding hook must not point this
// project's git at another repository), except the index a `commit -a` hands the pre-commit hook, when it is ours.
function gitEnv(project) {
  const env = cleanGitEnv(process.env);
  const index = process.env.GIT_INDEX_FILE;
  if (index) {
    try {
      const gitDir = git(project, ['rev-parse', '--absolute-git-dir'], env).trim();
      if (path.resolve(project, index).startsWith(`${gitDir}${path.sep}`)) env.GIT_INDEX_FILE = path.resolve(project, index);
    } catch {
      // not a repository: nothing to scan
    }
  }
  return env;
}

function baseRef(project, args) {
  if (args.base) return args.base;
  if (process.env.GITHUB_BASE_REF) return `origin/${process.env.GITHUB_BASE_REF}`;
  const known = defaultBranch(project);
  return known.known ? `origin/${known.name}` : null;
}

export default function secretScan({ project, args }) {
  const env = gitEnv(project);
  const sources = [];
  try {
    sources.push(git(project, [...DIFF, '--cached'], env));
  } catch {
    return { ok: true, message: 'not a git repository' };
  }
  const base = baseRef(project, args);
  if (base) {
    try {
      sources.push(git(project, [...DIFF, `${base}...HEAD`], env));
    } catch {
      // the base does not exist here (a shallow or fresh clone): only the staged diff is read
    }
  }
  const allow = String(args.allow ?? '').split(',').map((s) => s.trim()).filter(Boolean);
  const seen = new Set();
  const found = [];
  for (const { file, line, text } of sources.flatMap(addedLines)) {
    if (text.includes(ALLOW_MARKER) || (allow.length && matchesAny(file, allow))) continue;
    for (const f of findings(text)) {
      const key = `${file}:${line}:${f.kind}`;
      if (!seen.has(key)) {
        seen.add(key);
        found.push({ file, line, kind: f.kind });
      }
    }
  }
  if (!found.length) return { ok: true };
  const listed = found.slice(0, LISTED).map((f) => `${f.file}:${f.line} ${f.kind}`);
  const more = found.length > LISTED ? ` (and ${found.length - LISTED} more)` : '';
  return { ok: false, message: `possible secrets in added lines: ${listed.join(', ')}${more}; remove them, or mark a false positive with ${ALLOW_MARKER}` };
}
