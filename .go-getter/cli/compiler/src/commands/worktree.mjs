// go-getter worktree new <slug> [--branch <name>] [--from <ref>] | list [--json] | clean [--dry-run]
import { newWorktree, listWorktrees, cleanWorktrees } from '../worktree.mjs';

const USAGE = 'usage: go-getter worktree new <slug> [--branch <name>] [--from <ref>] | list [--json] | clean [--dry-run]';

export default function worktreeCommand({ args }) {
  const [sub, ...rest] = args;
  const flag = (name) => (rest.includes(name) ? rest[rest.indexOf(name) + 1] : undefined);
  try {
    if (sub === 'new') {
      const made = newWorktree(process.cwd(), rest[0], { branch: flag('--branch'), from: flag('--from') });
      console.log(`${made.path} (${made.branch})`);
      return 0;
    }
    if (sub === 'list') {
      const trees = listWorktrees(process.cwd());
      if (rest.includes('--json')) console.log(JSON.stringify(trees, null, 2));
      else for (const t of trees) console.log(`${t.path}\t${t.branch ?? '(detached)'}${t.main ? '\t(main)' : ''}`);
      return 0;
    }
    if (sub === 'clean') {
      const dryRun = rest.includes('--dry-run');
      const plan = cleanWorktrees(process.cwd(), { dryRun });
      for (const t of plan) console.log(`${t.action === 'remove' ? (dryRun ? 'would remove' : 'removed') : 'kept'}\t${t.path}\t${t.reason}${t.action === 'remove' && !dryRun && !t.branchDeleted ? `; branch ${t.branch} kept` : ''}`);
      if (!plan.length) console.log('no managed worktrees');
      return 0;
    }
  } catch (err) {
    console.error(`worktree: ${(err.stderr?.toString().trim() || err.message).split('\n')[0]}`);
    return 1;
  }
  console.error(USAGE);
  return 2;
}
