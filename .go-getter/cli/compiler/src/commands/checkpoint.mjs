// go-getter checkpoint create [--label <l>] | list | restore <ref-or-label> [--yes] | prune [--keep <n>] (decision 0097)
import { createCheckpoint, listCheckpoints, pruneCheckpoints, resolveCheckpoint, restorePlan, restoreCheckpoint, DEFAULT_KEEP } from '../checkpoint.mjs';

const USAGE = 'usage: go-getter checkpoint create [--label <l>] | list | restore <ref-or-label> [--yes] | prune [--keep <n>]';

export default function checkpointCommand({ args }) {
  const [sub, ...rest] = args;
  const flag = (name) => (rest.includes(name) ? rest[rest.indexOf(name) + 1] : undefined);
  const project = process.cwd();
  const keep = flag('--keep') === undefined ? DEFAULT_KEEP : Number(flag('--keep'));
  if (!Number.isInteger(keep) || keep < 0) {
    console.error('checkpoint: --keep takes a whole number');
    return 2;
  }
  try {
    if (sub === 'create') {
      const made = createCheckpoint(project, { label: flag('--label'), keep });
      if (!made) {
        console.error('checkpoint: not inside a git repository');
        return 1;
      }
      console.log(made.ref);
      return 0;
    }
    if (sub === 'list') {
      const all = listCheckpoints(project);
      for (const c of all) console.log(`${c.commit}\t${c.time}\t${c.label}\t${c.ref}`);
      if (!all.length) console.log('no checkpoints');
      return 0;
    }
    if (sub === 'prune') {
      const gone = pruneCheckpoints(project, keep);
      console.log(`pruned ${gone.length}; kept ${listCheckpoints(project).length}`);
      return 0;
    }
    if (sub === 'restore') {
      const name = rest.find((a) => !a.startsWith('--') && a !== flag('--keep'));
      const ref = resolveCheckpoint(project, name);
      if (!ref) {
        console.error(`checkpoint: no checkpoint${name ? ` matching "${name}"` : ''}`);
        return 1;
      }
      const plan = restorePlan(project, ref);
      for (const c of plan.changes) console.log(`${c.status}\t${c.path}`);
      const back = plan.changes.filter((c) => c.status !== 'A').length;
      if (!rest.includes('--yes')) {
        console.log(`${ref}: would put back ${back} file(s) (M modified, D deleted since); ${plan.createdSince.length} created since stay (A). Nothing changed; run again with --yes to restore.`);
        return 0;
      }
      const done = restoreCheckpoint(project, ref);
      console.log(`${ref}: restored ${done.restored.length} file(s); left in place, created since: ${done.createdSince.length ? done.createdSince.join(', ') : 'none'}`);
      return 0;
    }
  } catch (err) {
    console.error(`checkpoint: ${(err.stderr?.toString().trim() || err.message).split('\n')[0]}`);
    return 1;
  }
  console.error(USAGE);
  return 2;
}
