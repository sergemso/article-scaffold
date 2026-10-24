// go-getter coverage [--project <dir>] [--pack-dir <dir>] [--json]
import path from 'node:path';
import { existsSync, readdirSync } from 'node:fs';
import { loadPack } from '../packs.mjs';
import { loadCapabilities } from '../capabilities.mjs';
import { coverage, formatCoverage } from '../coverage.mjs';
import { ciChecksNote } from '../apply.mjs';
import { adoptedData } from '../governance.mjs';

export default function coverageCommand({ root, args }) {
  let project = process.cwd();
  let packDir = path.join(root, 'src/packs');
  let asJson = false;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--project') project = path.resolve(args[++i]);
    else if (args[i] === '--pack-dir') packDir = path.resolve(args[++i]);
    else if (args[i] === '--json') asJson = true;
  }
  const packs = {};
  for (const name of existsSync(packDir) ? readdirSync(packDir) : []) {
    const file = path.join(packDir, name, 'pack.json');
    if (existsSync(file)) packs[name] = loadPack(file);
  }
  const rows = coverage(project, packs, loadCapabilities(root));
  console.log(asJson ? JSON.stringify(rows, null, 2) : formatCoverage(rows));
  // Plan steps in a tracker (the tracker pack, an SDLC pack with no component of its own): where, and who approves writes.
  const tracker = asJson ? null : adoptedData(project, 'tracker');
  if (tracker && tracker !== 'files') console.log(`\nPlan tracker: ${tracker}; writes ${adoptedData(project, 'tracker-writes') ?? 'off'}.`);
  const note = asJson ? null : ciChecksNote(project);
  if (note) console.log(`\n${note}`);
  return 0;
}
