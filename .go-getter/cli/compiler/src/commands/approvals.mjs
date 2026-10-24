// go-getter approvals list [--json] | add <secret-path> -- <command> [args...] | allow <shape> | revoke (<id> | <shape> | --all)
// Personal approvals: to use a secret file (decision 0126) and to run an outward command shape without asking (decision 0130).
// `add`, `allow` and `revoke` change what an agent may do, so a person runs them; the pre-tool hook refuses an agent's call.
import { realpathSync } from 'node:fs';
import { add, list, revoke, storeFile, addShape, listShapes, revokeShape } from '../secrets/approvals.mjs';
import { APPROVABLE, isApprovable } from '../gate.mjs';
import { restrictedPatterns } from '../hook.mjs';
import { matchesAny } from '../glob.mjs';
import { repoRoot } from '../plan.mjs';

const USAGE = 'usage: go-getter approvals list [--json] | add <secret-path> -- <command> [args...] | allow <shape> | revoke (<id> | <shape> | --all)';

const describe = (e) => `${e.id}  ${e.path}  ${e.command.join(' ')}  ${e.current ? 'current' : 'STALE: the code changed since it was approved'}  (${e.files} file${e.files === 1 ? '' : 's'}, approved ${e.approvedAt.slice(0, 10)})`;

export default function approvalsCommand({ args }) {
  const [sub, ...rest] = args;
  const project = repoRoot(process.cwd());
  try {
    if (sub === 'list' && rest.every((a) => a === '--json')) {
      const entries = list(project);
      const shapes = listShapes(project);
      if (rest.includes('--json')) console.log(JSON.stringify(entries, null, 2)); // secret approvals only: the format other tools read
      else {
        const lines = [...entries.map(describe), ...shapes.map((e) => `${e.id}  ${e.id.startsWith('mcp:') ? 'MCP write tool' : 'outward command shape'}, may run without asking while its preconditions hold  (approved ${e.approvedAt.slice(0, 10)})`)];
        console.log(lines.length ? lines.join('\n') : `no approvals for ${realpathSync(project)} (store: ${storeFile()})`);
      }
      return 0;
    }
    if (sub === 'add') {
      const dash = rest.indexOf('--');
      if (dash !== 1 || rest.length < 3) {
        console.error(USAGE);
        return 2;
      }
      const [secretPath] = rest;
      if (!matchesAny(secretPath.replace(/^\.\//, ''), restrictedPatterns(project))) {
        console.error(`approvals: ${secretPath} is not a restricted path of this project, so there is nothing to approve`);
        return 1;
      }
      const entry = add(project, rest.slice(dash + 1), secretPath, { host: process.env.GO_GETTER_HOST });
      console.log(`approved ${entry.id}: ${entry.command.join(' ')} may use ${entry.path} while its code is unchanged`);
      return 0;
    }
    if (sub === 'allow' && rest.length === 1) {
      if (!isApprovable(rest[0])) {
        console.error(`approvals: ${rest[0]} cannot be approved once; the shapes that can are ${APPROVABLE.join(', ')} and mcp:<server>:<tool> (tags, releases, publishing and history rewrites always ask)`);
        return 1;
      }
      const entry = addShape(project, rest[0], { host: process.env.GO_GETTER_HOST });
      console.log(`approved ${entry.id}: it may run without asking in this project while its preconditions hold`);
      return 0;
    }
    if (sub === 'revoke' && rest.length === 1) {
      const all = rest[0] === '--all';
      const removed = revoke(project, all ? { all: true } : { id: rest[0] }) + revokeShape(project, all ? { all: true } : { id: rest[0] });
      console.log(removed ? `revoked ${removed} approval${removed === 1 ? '' : 's'}` : `no approval ${rest[0]} for this project`);
      return removed ? 0 : 1;
    }
  } catch (err) {
    console.error(`approvals: ${err.message.split('\n')[0]}`);
    return 1;
  }
  console.error(USAGE);
  return 2;
}
