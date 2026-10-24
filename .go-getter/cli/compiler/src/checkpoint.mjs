// Checkpoints (decision 0097): a commit of the working tree (tracked and untracked, not ignored) stored under
// refs/go-getter/checkpoints/, written through a temporary index so the working tree, the index, HEAD and the branches
// are never touched. The 10 newest are kept.
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { cleanGitEnv } from './git-env.mjs';

export const CHECKPOINT_REF = 'refs/go-getter/checkpoints';
export const DEFAULT_KEEP = 10;
const IDENTITY = ['-c', 'user.name=go-getter', '-c', 'user.email=go-getter@localhost', '-c', 'commit.gpgsign=false'];

function git(cwd, args, { env = {}, input } = {}) {
  return execFileSync('git', args, { cwd, encoding: 'utf8', input, stdio: ['pipe', 'pipe', 'ignore'], env: { ...cleanGitEnv(process.env), ...env } }).trim();
}

// The top level of the repository holding `project`, or null when it is not in one (or git is missing).
function toplevel(project) {
  try {
    return git(project, ['rev-parse', '--show-toplevel']);
  } catch {
    return null;
  }
}

export const sanitizeLabel = (label) => (String(label ?? '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40).replace(/-+$/, '') || 'checkpoint');

// The tree of the working tree as it is now, built in a throwaway index; `add -A` honours .gitignore.
function snapshotTree(root) {
  const dir = mkdtempSync(path.join(tmpdir(), 'gg-checkpoint-'));
  try {
    const env = { GIT_INDEX_FILE: path.join(dir, 'index') };
    git(root, ['add', '-A'], { env });
    return git(root, ['write-tree'], { env });
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

const stamp = (d) => d.toISOString().replace(/[-:]/g, '').replace('.', '');

// Checkpoints, newest first: { ref, label, commit, time }.
export function listCheckpoints(project) {
  const root = toplevel(project);
  if (!root) return [];
  const out = git(root, ['for-each-ref', '--sort=-refname', '--format=%(refname)\t%(objectname:short)\t%(creatordate:iso-strict)', CHECKPOINT_REF]);
  return out
    .split('\n')
    .filter(Boolean)
    .map((line) => {
      const [ref, commit, time] = line.split('\t');
      return { ref, label: ref.slice(CHECKPOINT_REF.length + 1).replace(/^\d{8}T\d{9}Z-?/, '') || 'checkpoint', commit, time };
    });
}

// Deletes all but the `keep` newest checkpoints; returns the deleted refs.
export function pruneCheckpoints(project, keep = DEFAULT_KEEP) {
  const root = toplevel(project);
  if (!root) return [];
  const old = listCheckpoints(project).slice(Math.max(0, keep));
  for (const { ref } of old) git(root, ['update-ref', '-d', ref]);
  return old.map((c) => c.ref);
}

// Writes a checkpoint of the working tree and prunes to the `keep` newest. Returns { ref, commit, pruned }, or null
// outside a git repository. Works before the first commit (the checkpoint is then a root commit).
export function createCheckpoint(project, { label, keep = DEFAULT_KEEP, now = new Date() } = {}) {
  const root = toplevel(project);
  if (!root) return null;
  const tree = snapshotTree(root);
  let head = null;
  try {
    head = git(root, ['rev-parse', '--verify', '--quiet', 'HEAD']);
  } catch {
    head = null;
  }
  const name = sanitizeLabel(label);
  const base = `${CHECKPOINT_REF}/${stamp(now)}-${name}`;
  const taken = new Set(listCheckpoints(project).map((c) => c.ref));
  let ref = base;
  for (let n = 2; taken.has(ref); n++) ref = `${base}-${n}`;
  const commit = git(root, [...IDENTITY, 'commit-tree', tree, ...(head ? ['-p', head] : []), '-m', `go-getter checkpoint: ${name}`]);
  git(root, ['update-ref', ref, commit]);
  return { ref, commit, pruned: pruneCheckpoints(project, keep) };
}

// How the working tree now differs from `ref`: M modified since, D deleted since (restore brings it back), A created
// since (restore leaves it in place). Null outside a git repository.
export function restorePlan(project, ref) {
  const root = toplevel(project);
  if (!root) return null;
  const now = snapshotTree(root);
  const out = git(root, ['diff-tree', '-r', '--name-status', '--no-renames', '-z', ref, now]);
  const parts = out.split('\0').filter(Boolean);
  const changes = [];
  for (let i = 0; i + 1 < parts.length; i += 2) changes.push({ status: parts[i], path: parts[i + 1] });
  return { ref, changes, createdSince: changes.filter((c) => c.status === 'A').map((c) => c.path) };
}

// The checkpoint a name refers to: a full ref, `latest`, or the newest whose label or ref contains the name. Null when none.
export function resolveCheckpoint(project, name) {
  const all = listCheckpoints(project);
  if (!name || name === 'latest') return all[0]?.ref ?? null;
  return (all.find((c) => c.ref === name || c.ref === `${CHECKPOINT_REF}/${name}`) ?? all.find((c) => c.label === name) ?? all.find((c) => c.ref.includes(name)))?.ref ?? null;
}

// Puts back the files modified or deleted since `ref`, in the working tree only: the index, HEAD and branches stay as
// they are, and files created since are left in place. Returns { restored, createdSince }, or null outside a git repository.
export function restoreCheckpoint(project, ref) {
  const root = toplevel(project);
  if (!root) return null;
  const plan = restorePlan(project, ref);
  const paths = plan.changes.filter((c) => c.status !== 'A').map((c) => c.path);
  if (paths.length) git(root, ['--literal-pathspecs', 'restore', `--source=${ref}`, '--worktree', '--pathspec-from-file=-', '--pathspec-file-nul'], { input: paths.join('\0') });
  return { restored: paths, createdSince: plan.createdSince };
}
