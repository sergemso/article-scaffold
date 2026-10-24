// go-getter verify --class <explore|plan|implement|review|debug> [--project <dir>] [--host <id>]
// Runs the adopted checks of a task class (pack verification-gate); exit 0 when all pass or none are configured.
import path from 'node:path';
import { CLASSES, verify } from '../verify.mjs';

export default async function verifyCommand({ args }) {
  let taskClass;
  let host;
  let project = process.cwd();
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--class') taskClass = args[++i];
    else if (args[i] === '--host') host = args[++i];
    else if (args[i] === '--project') project = path.resolve(args[++i]);
  }
  if (!CLASSES.includes(taskClass)) {
    console.error(`usage: go-getter verify --class <${CLASSES.join('|')}> [--project <dir>] [--host <id>]`);
    return 2;
  }
  const { ok, results } = await verify(project, taskClass, { host });
  if (!results.length) console.log(`go-getter verify: no checks configured for class "${taskClass}"`);
  for (const r of results) {
    console.log(`${r.ok ? 'pass' : 'FAIL'} ${r.name}`);
    if (!r.ok && r.output) console.error(r.output);
  }
  return ok ? 0 : 1;
}
