import { execFileSync } from 'node:child_process';
// Git hooks export variables that pin every git command to the hooked repository; a child process that runs git
// elsewhere (a temporary repository in a check's tests, say) must not inherit them.
const REPO_ENV = ['GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_PREFIX', 'GIT_COMMON_DIR', 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES'];

export const cleanGitEnv = (env) => Object.fromEntries(Object.entries(env).filter(([k]) => !REPO_ENV.includes(k)));

// The project's default branch: { name, known }. `known` when the remote says so (origin/HEAD, or the only one of
// origin/main and origin/master that exists). Otherwise `name` is only the checked-out branch (null when detached),
// which is a guess: a CI checkout of a pull request is detached and has no origin/HEAD.
export function defaultBranch(root) {
  const run = (...args) => {
    try {
      return execFileSync('git', args, { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], env: cleanGitEnv(process.env) }).trim() || null;
    } catch {
      return null;
    }
  };
  const head = run('symbolic-ref', '--short', 'refs/remotes/origin/HEAD')?.replace(/^origin\//, '');
  if (head) return { name: head, known: true };
  const remote = ['main', 'master'].filter((b) => run('rev-parse', '--verify', '--quiet', `refs/remotes/origin/${b}`));
  if (remote.length === 1) return { name: remote[0], known: true };
  return { name: run('branch', '--show-current'), known: false };
}
