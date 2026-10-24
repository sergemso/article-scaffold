// Every non-merge commit not yet on the base branch must carry a `<trailer>: <value>` line in its message (git trailers
// sit in the last paragraph). Base: args.base, else origin's default branch.
import { execFileSync } from 'node:child_process';
import { defaultBranch, cleanGitEnv } from '../../git-env.mjs';

const git = (project, a) => execFileSync('git', a, { cwd: project, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], env: cleanGitEnv(process.env) });

export default function commitTrailer({ project, args }) {
  const trailer = args.trailer;
  if (!trailer || !/^[A-Za-z][A-Za-z0-9-]*$/.test(trailer)) return { ok: false, message: 'commit-trailer needs trailer=<Name>' };
  let commits;
  try {
    const known = defaultBranch(project);
    const base = args.base ?? (known.known ? `origin/${known.name}` : null);
    if (!base) throw new Error('no base');
    commits = git(project, ['log', '--no-merges', '--format=%H', `${base}..HEAD`]).split('\n').filter(Boolean);
  } catch {
    return { ok: true, message: 'no base branch to compare against' };
  }
  const re = new RegExp(`^${trailer}: \\S`, 'm');
  const missing = commits.filter((sha) => {
    const paragraphs = git(project, ['log', '-1', '--format=%B', sha]).trim().split(/\n\s*\n/);
    return !re.test(paragraphs.at(-1));
  });
  return missing.length ? { ok: false, message: `commits without a "${trailer}:" trailer: ${missing.map((s) => s.slice(0, 7)).join(', ')}` } : { ok: true };
}
