// `go-getter worktree new|list|clean` (plan 5.2): parallel-task isolation as chosen in the orchestration pack's
// isolation, location and concurrency decisions (decision 0028). Defaults to the recommended answers when the pack is not adopted.
import { defaultBranch as remoteDefaultBranch } from './git-env.mjs';
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { readArtifacts } from './artifacts.mjs';

const git = (cwd, ...args) => execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
const tryGit = (cwd, ...args) => {
  try {
    return git(cwd, ...args);
  } catch {
    return null;
  }
};

export function worktreeConfig(project) {
  const data = Object.assign(
    {},
    ...readArtifacts(project, ['decisions'])
      .filter((d) => d.data.status === 'active' && String(d.data['go-getter']?.['generated-by'] ?? '').startsWith('orchestration@'))
      .map((d) => d.data['go-getter']),
  );
  return { isolation: data.isolation ?? 'worktree', location: data['worktree-location'] ?? 'sibling', max: Number(data['max-concurrent'] ?? 3) };
}

// [{path, branch|null, head, main}] from `git worktree list --porcelain`; the first entry is the main working tree.
export function listWorktrees(cwd) {
  return git(cwd, 'worktree', 'list', '--porcelain')
    .split('\n\n')
    .filter(Boolean)
    .map((block, i) => {
      const field = (name) => new RegExp(`^${name} (.*)$`, 'm').exec(block)?.[1] ?? null;
      return { path: field('worktree'), branch: field('branch')?.replace(/^refs\/heads\//, '') ?? null, head: field('HEAD'), main: i === 0 };
    });
}

function defaultBranch(main) {
  const remote = remoteDefaultBranch(main);
  if (remote.known) return `origin/${remote.name}`;
  return ['main', 'master'].find((b) => tryGit(main, 'rev-parse', '--verify', '--quiet', `refs/heads/${b}`)) ?? 'HEAD';
}

// Where a task's worktree goes under the chosen location, or null when the host agent decides.
export function worktreeDir(main, location, slug) {
  if (location === 'sibling') return path.join(path.dirname(main), `${path.basename(main)}-wt`, slug);
  if (location === 'in-repo') return path.join(main, '.worktrees', slug);
  return null;
}

export function newWorktree(cwd, slug, { branch, from } = {}) {
  if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(slug ?? '')) throw new Error('slug must be lowercase words joined by hyphens');
  const trees = listWorktrees(cwd);
  const main = trees[0].path;
  const config = worktreeConfig(main);
  if (config.isolation !== 'worktree') throw new Error(`isolation is "${config.isolation}"; this project does not use worktrees`);
  if (config.location === 'host-default') throw new Error('worktree location is the host default; let the host agent create the worktree');
  if (trees.length - 1 >= config.max) throw new Error(`${trees.length - 1} worktrees already exist; the limit is ${config.max} concurrent agents (run "go-getter worktree clean" or finish a task)`);
  const dir = worktreeDir(main, config.location, slug);
  if (existsSync(dir)) throw new Error(`${dir} already exists`);
  const name = branch ?? `feat/${slug}`;
  git(main, 'worktree', 'add', '-b', name, dir, from ?? defaultBranch(main));
  return { path: dir, branch: name };
}

// Linked worktrees in the managed location, with what `clean` would do about each.
export function planClean(cwd) {
  const trees = listWorktrees(cwd);
  const main = trees[0].path;
  const config = worktreeConfig(main);
  const base = config.location === 'in-repo' ? path.join(main, '.worktrees') : path.join(path.dirname(main), `${path.basename(main)}-wt`);
  const target = defaultBranch(main);
  const here = tryGit(cwd, 'rev-parse', '--show-toplevel');
  return trees
    .filter((t) => !t.main && t.path.startsWith(`${base}${path.sep}`))
    .map((t) => {
      if (!t.branch) return { ...t, action: 'keep', reason: 'detached HEAD' };
      if (t.path === here) return { ...t, action: 'keep', reason: 'current worktree' };
      if (git(t.path, 'status', '--porcelain')) return { ...t, action: 'keep', reason: 'uncommitted changes' };
      const gone = tryGit(main, 'for-each-ref', '--format=%(upstream:track)', `refs/heads/${t.branch}`) === '[gone]';
      // `worktree add -b` leaves one reflog entry; any commit adds another. A branch with no commits of its own is a task just started, not a merged one.
      const hasWork = (tryGit(main, 'reflog', 'show', '--format=%H', `refs/heads/${t.branch}`) ?? '').split('\n').filter(Boolean).length > 1;
      const behind = hasWork && tryGit(main, 'merge-base', '--is-ancestor', t.branch, target) !== null;
      if (gone || behind) return { ...t, action: 'remove', reason: gone ? 'remote branch deleted' : `merged into ${target}` };
      return { ...t, action: 'keep', reason: `not merged into ${target}` };
    });
}

export function cleanWorktrees(cwd, { dryRun = false } = {}) {
  const plan = planClean(cwd);
  const main = listWorktrees(cwd)[0].path;
  for (const t of plan) {
    if (t.action !== 'remove' || dryRun) continue;
    git(main, 'worktree', 'remove', t.path);
    // Squash-merged branches are not ancestors of the target, so -d refuses; keep such a branch rather than force-delete it.
    t.branchDeleted = tryGit(main, 'branch', '-d', t.branch) !== null;
  }
  if (!dryRun) git(main, 'worktree', 'prune');
  return plan;
}
