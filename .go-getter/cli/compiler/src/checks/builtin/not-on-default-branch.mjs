// Fails when the work is on the project's default branch, so a commit or push goes through a branch and a pull request.
// Before a push the refs being pushed decide, not the checked-out branch (a tag push from the default branch passes).
// In CI only a pull request's head branch counts (GITHUB_HEAD_REF): a push to the default branch is the merge itself.
// Passes when the default branch is not known (no origin/HEAD), since the checked-out branch would then be a guess.
import { execFileSync } from 'node:child_process';
import { defaultBranch, cleanGitEnv } from '../../git-env.mjs';

export default function notOnDefaultBranch({ project, args, pushRefs }) {
  if (pushRefs && !process.env.GITHUB_ACTIONS) {
    // Before a push only the refs being pushed matter: a tag, or a branch other than the default, may go from any checkout.
    const known = defaultBranch(project);
    if (!known.known) return { ok: true, message: 'default branch not known' };
    return pushRefs.includes(`refs/heads/${known.name}`)
      ? { ok: false, message: `"${known.name}" is the default branch; push a branch and open a pull request` }
      : { ok: true };
  }
  const inCi = Boolean(process.env.GITHUB_ACTIONS);
  let branch = process.env.GITHUB_HEAD_REF || '';
  if (!branch && !inCi) {
    try {
      branch = execFileSync('git', ['branch', '--show-current'], { cwd: project, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], env: cleanGitEnv(process.env) }).trim();
    } catch {
      branch = '';
    }
  }
  if (!branch) return { ok: true, message: 'no branch to check (detached HEAD or a push in CI)' };
  const known = defaultBranch(project);
  if (!known.known) return { ok: true, message: 'default branch not known' };
  if (String(args.allow ?? '').split(',').filter(Boolean).includes(branch)) return { ok: true };
  return branch === known.name ? { ok: false, message: `"${branch}" is the default branch; work on a branch and open a pull request` } : { ok: true };
}
