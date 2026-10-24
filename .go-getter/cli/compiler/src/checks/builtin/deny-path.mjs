// Tier 3: no git-tracked file matches the denied paths. Tier 2 (host hooks) is evaluated by the hook runtime.
import { execFileSync } from 'node:child_process';
import { matchesAny } from '../../glob.mjs';

export const patternsOf = (args) => String(args.paths ?? '').split(',').map((s) => s.trim()).filter(Boolean);

export default function denyPath({ project, args }) {
  let tracked;
  try {
    tracked = execFileSync('git', ['ls-files'], { cwd: project, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).split('\n').filter(Boolean);
  } catch {
    return { ok: true, message: 'not a git repository' };
  }
  const hits = tracked.filter((f) => matchesAny(f, patternsOf(args)));
  return hits.length ? { ok: false, message: `tracked files match denied paths: ${hits.join(', ')}` } : { ok: true };
}
