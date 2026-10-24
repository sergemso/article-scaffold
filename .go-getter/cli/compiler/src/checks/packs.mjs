// Validates every src/packs/<id>/pack.json (decision 0022). `--file <path>` validates specific pack files.
import path from 'node:path';
import { validateAllPacks, listPackFiles } from '../packs.mjs';

export default function checkPacks({ root, args }) {
  const files = [];
  for (let i = 0; i < args.length; i++) if (args[i] === '--file') files.push(path.resolve(args[++i]));
  const targets = files.length ? files : listPackFiles(root);
  let problems;
  try {
    problems = validateAllPacks(root, targets);
  } catch (err) {
    console.error(`check packs: ${err.message}`);
    return 1;
  }
  if (problems.length) {
    console.error('check packs:');
    for (const p of problems) console.error(`  ${p}`);
    return 1;
  }
  console.log(`check packs: ok (${targets.length} pack${targets.length === 1 ? '' : 's'})`);
  return 0;
}
