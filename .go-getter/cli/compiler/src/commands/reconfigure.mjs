// go-getter reconfigure <pack-id> --answers <file> [--project <dir>] [--pack-file <file>] [--dry-run] [--current]
// --current prints the answers currently recorded in this project's artifacts (the interview's defaults).
import path from 'node:path';
import { readFileSync, existsSync } from 'node:fs';
import { loadPack, retiredPackNote } from '../packs.mjs';
import { planReconfigure, applyReconfigure, adoptedArtifacts, currentAnswers } from '../reconfigure.mjs';

export default function reconfigureCommand({ root, args }) {
  let id;
  let answersFile;
  let project = process.cwd();
  let packFile;
  let dryRun = false;
  let current = false;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--answers') answersFile = args[++i];
    else if (args[i] === '--project') project = path.resolve(args[++i]);
    else if (args[i] === '--pack-file') packFile = path.resolve(args[++i]);
    else if (args[i] === '--dry-run') dryRun = true;
    else if (args[i] === '--current') current = true;
    else id = args[i];
  }
  packFile ??= path.join(root, 'src/packs', id ?? '', 'pack.json');
  if (!existsSync(packFile)) {
    const note = retiredPackNote(root, id);
    if (note) console.error(`reconfigure: ${note}`);
    console.error('usage: go-getter reconfigure <pack-id> --answers <file> [--dry-run] | --current');
    return 2;
  }
  const pack = loadPack(packFile);
  if (current) {
    console.log(JSON.stringify({ answers: currentAnswers(adoptedArtifacts(project, pack.id)) }, null, 2));
    return 0;
  }
  const input = JSON.parse(readFileSync(path.resolve(answersFile), 'utf8'));
  try {
    const result = planReconfigure({
      project,
      pack,
      answers: input.answers ?? {},
      acceptedBy: input.acceptedBy,
      date: input.date ?? new Date().toISOString().slice(0, 10),
      detect: input.detect ?? {},
    });
    const summary = {
      changed: result.changed,
      write: result.plan.artifacts.map((a) => a.path),
      statusChanges: result.statusChanges.map((s) => `${s.artifact.file}: ${s.status}${s.supersededBy ? ` by ${s.supersededBy}` : ''}`),
    };
    if (!dryRun) applyReconfigure({ project, result });
    console.log(JSON.stringify({ dryRun, ...summary }, null, 2));
    return 0;
  } catch (err) {
    console.error(`reconfigure: ${err.message}`);
    return 1;
  }
}
