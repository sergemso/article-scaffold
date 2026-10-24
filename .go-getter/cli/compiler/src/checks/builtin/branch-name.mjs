import { execFileSync } from 'node:child_process';

export default function branchName({ project, args }) {
  const branch =
    process.env.GITHUB_HEAD_REF ||
    (() => {
      try {
        return execFileSync('git', ['branch', '--show-current'], { cwd: project, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
      } catch {
        return '';
      }
    })();
  if (!branch) return { ok: true, message: 'no branch (detached HEAD)' };
  const allowed = String(args.allow ?? '').split(',').filter(Boolean);
  if (allowed.includes(branch)) return { ok: true };
  return new RegExp(args.pattern).test(branch) ? { ok: true } : { ok: false, message: `branch "${branch}" does not match ${args.pattern}` };
}
