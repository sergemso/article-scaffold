// go-getter ci status [--branch <b>] [--wait] [--interval <s>] [--project <dir>]
// Prints the latest CI run of the branch (default: the current one), one line per job. Exit 0 success, 1 failure,
// 2 usage, 3 pending, 4 unknown. `--wait` polls until the run is no longer pending; run it under `go-getter watch`.
import path from 'node:path';
import { setTimeout as sleep } from 'node:timers/promises';
import { ciStatus, formatStatus } from '../ci.mjs';

const USAGE = 'usage: go-getter ci status [--branch <b>] [--wait] [--interval <seconds>] [--project <dir>]';
const CODES = { success: 0, failure: 1, pending: 3, unknown: 4 };
const MAX_WAIT_MS = 2 * 60 * 60 * 1000;

export default async function ciCommand({ args }) {
  const [sub, ...rest] = args;
  let project = process.cwd();
  let branch;
  let wait = false;
  let interval = 30;
  let bad = sub !== 'status';
  for (let i = 0; i < rest.length; i++) {
    if (rest[i] === '--branch' && rest[i + 1]) branch = rest[++i];
    else if (rest[i] === '--project' && rest[i + 1]) project = path.resolve(rest[++i]);
    else if (rest[i] === '--interval' && Number(rest[i + 1]) > 0) interval = Number(rest[++i]);
    else if (rest[i] === '--wait') wait = true;
    else bad = true;
  }
  if (bad) {
    console.error(USAGE);
    return 2;
  }
  const start = Date.now();
  let status = ciStatus(project, branch ? { branch } : {});
  while (wait && status.state === 'pending' && Date.now() - start < MAX_WAIT_MS) {
    await sleep(interval * 1000);
    status = ciStatus(project, branch ? { branch } : {});
  }
  console.log(formatStatus(status));
  return CODES[status.state];
}
