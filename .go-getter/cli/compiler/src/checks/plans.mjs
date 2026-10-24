// Decision 0069: every plan in docs/plans and docs/plans/archive parses, with known field values, known Needs ids and no cycles.
import path from 'node:path';
import { readFileSync } from 'node:fs';
import { parsePlan, planFiles } from '../plan.mjs';

export default function checkPlans({ args }) {
  const project = args.includes('--project') ? path.resolve(args[args.indexOf('--project') + 1]) : process.cwd();
  const files = planFiles(project);
  const problems = files.flatMap((f) => parsePlan(readFileSync(path.join(project, f), 'utf8'), f).problems);
  if (problems.length) {
    console.error('check plans:');
    for (const p of problems) console.error(`  ${p}`);
    return 1;
  }
  console.log(`check plans: ok (${files.length} plans)`);
  return 0;
}
