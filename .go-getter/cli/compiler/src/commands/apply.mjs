// go-getter apply [--project <dir>] [--hosts <h1,h2>|all] [--skills|--no-skills] [--check] [--force]
//   go-getter apply --remove [--dry-run] [--force] [--project <dir>]
import path from 'node:path';
import { planApply, applyPlan, diffApply } from '../apply.mjs';
import { planRemove, applyRemove } from '../remove.mjs';
import { readManifest, drift, installedPackage } from '../manifest.mjs';
import { HOSTS } from '../capabilities.mjs';

export default function applyCommand({ root, args }) {
  let project = process.cwd();
  let hosts;
  let check = false;
  let skills;
  let force = false;
  let remove = false;
  let dryRun = false;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--project') project = path.resolve(args[++i]);
    else if (args[i] === '--hosts') hosts = args[++i] === 'all' ? HOSTS : args[i].split(',');
    else if (args[i] === '--check') check = true;
    else if (args[i] === '--force') force = true;
    else if (args[i] === '--remove') remove = true;
    else if (args[i] === '--dry-run') dryRun = true;
    else if (args[i] === '--skills') skills = true;
    else if (args[i] === '--no-skills') skills = false;
    else throw new Error(`apply: unknown argument ${args[i]}`);
  }
  if (dryRun && !remove) throw new Error('apply: --dry-run needs --remove (use --check to see what apply would change)');
  if (remove) {
    if (check || hosts || skills !== undefined) throw new Error('apply: --remove takes only --dry-run, --force and --project');
    const plan = planRemove(project, { force });
    console.log(`apply --remove${dryRun ? ' --dry-run' : ''}:`);
    for (const step of plan.steps) console.log(`  ${step.text}`);
    if (!dryRun) applyRemove(project, plan);
    for (const m of plan.modified) console.error(`  modified: ${m.path} (${m.reason}); ${dryRun ? 'would be kept' : 'kept'}, use --force to remove it`);
    return plan.modified.length ? 1 : 0;
  }
  const plan = planApply(project, { hosts, skills, force });
  if (check) {
    const problems = diffApply(project, plan);
    const manifest = readManifest(project);
    const installed = installedPackage(root);
    const d = drift(manifest, installed);
    if (d) problems.push(`version: manifest at ${manifest.version}${d.packs.length ? `, packs ${d.packs.join(', ')} older` : ''}, installed ${installed.version}; run "go-getter update"`);
    if (problems.length) {
      console.error(`apply --check: ${problems.length} file(s) out of date; run "go-getter apply"`);
      for (const p of problems) console.error(`  ${p}`);
      return 1;
    }
    console.log('apply --check: ok');
    return 0;
  }
  const { written, modified } = applyPlan(project, plan);
  console.log(`apply: hosts ${plan.hosts.join(', ') || '(none detected)'}; tier 2 ${plan.tier2 ? 'on' : 'off'}; tier 3 ${plan.tier3 ? 'on' : 'off'}; project-local skills ${plan.skills ? 'on' : 'off'}`);
  for (const w of written) console.log(`  ${w}`);
  for (const [host, r] of Object.entries(plan.otel ?? {})) {
    console.log(`  otel ${host}: ${r.status === 'emitted' ? `emitted in ${r.file}` : `unavailable (${r.reason})`}`);
  }
  for (const n of plan.notes ?? []) console.log(`  ${n}`);
  for (const m of modified) console.error(`  modified: ${m.path} (${m.reason}); skipped, use --force to overwrite or remove it`);
  return modified.length ? 1 : 0;
}
