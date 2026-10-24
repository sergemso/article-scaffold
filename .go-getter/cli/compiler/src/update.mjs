// go-getter update (decision 0090): brings a project's generated output up to the installed package. Adopted packs are
// re-rendered with their recorded answers (new questions take their default, 0085), then the host outputs are applied
// from the manifest. The plan is made by running the update on a scratch copy of the project and diffing the two trees,
// so the printed plan is exactly what a real run writes.
import { cpSync, existsSync, lstatSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, readlinkSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { applyPlan, bootstrap, planApply } from './apply.mjs';
import { readArtifacts } from './artifacts.mjs';
import { parseFrontmatter, stringifyFrontmatter } from './frontmatter.mjs';
import { SCHEMA, adoptedPacks, readManifest } from './manifest.mjs';
import { gitSetting } from './reconcile.mjs';
import { loadPack } from './packs.mjs';
import { adoptedArtifacts, applyReconfigure, planReconfigure, currentAnswers } from './reconfigure.mjs';
import { activeQuestions, renameAnswers, withFallbacks } from './render.mjs';

const skipped = (name) => name === '.git' || name === 'node_modules';

// An artifact re-rendered unchanged keeps its date, so a second update is a no-op.
function keepDate(project, artifact) {
  const file = path.join(project, artifact.path);
  if (!existsSync(file)) return artifact;
  const old = parseFrontmatter(readFileSync(file, 'utf8')).data.date;
  const { data, body } = parseFrontmatter(artifact.content);
  return old === undefined ? artifact : { ...artifact, content: stringifyFrontmatter({ ...data, date: old }, body) };
}

const compareVersions = (a, b) => {
  const [x, y] = [a, b].map((v) => v.split('.').map(Number));
  for (let i = 0; i < 3; i++) if ((x[i] ?? 0) !== (y[i] ?? 0)) return (x[i] ?? 0) - (y[i] ?? 0);
  return 0;
};

// A pack that took over questions of a retired pack (`replaces`, decision 0132) adopts the retired pack's artifacts for
// those questions: only `generated-by` changes, to the new pack at the version the project adopted, so nothing is asked
// again and `since` still tells which questions are new. The ordinary re-render then does the rest.
function relabelTakenOver(project, root, notes) {
  const packsDir = path.join(root, 'src/packs');
  if (!existsSync(packsDir)) return;
  const shipped = new Set(readdirSync(packsDir));
  const takeovers = [];
  for (const id of shipped) {
    const file = path.join(packsDir, id, 'pack.json');
    if (existsSync(file)) {
      const { replaces } = loadPack(file);
      if (replaces && !shipped.has(replaces.pack)) takeovers.push({ id, ...replaces });
    }
  }
  for (const a of readArtifacts(project)) {
    if (!['active', 'draft'].includes(a.data.status)) continue;
    const g = a.data['go-getter'];
    const m = /^([^@]+)@(.+)$/.exec(String(g?.['generated-by'] ?? ''));
    if (!m) continue;
    const to = takeovers.find((t) => t.pack === m[1] && t.questions.includes(g['pack-answer']));
    if (!to) {
      if (takeovers.some((t) => t.pack === m[1])) notes.push(`${a.file.split(path.sep).join('/')}: its question "${g['pack-answer']}" is taken over by no pack; left as it is`);
      continue;
    }
    const file = path.join(project, a.file);
    const { data, body } = parseFrontmatter(readFileSync(file, 'utf8'));
    writeFileSync(file, stringifyFrontmatter({ ...data, 'go-getter': { ...g, 'generated-by': `${to.id}@${m[2]}` } }, body));
  }
}

function reRender(project, root, date, notes) {
  relabelTakenOver(project, root, notes);
  for (const id of Object.keys(adoptedPacks(project))) {
    const packFile = path.join(root, 'src/packs', id, 'pack.json');
    if (!existsSync(packFile)) {
      notes.push(`pack ${id}: not in this go-getter version; left as it is`);
      continue;
    }
    const pack = loadPack(packFile);
    const adopted = adoptedArtifacts(project, id);
    // An answer no adopted artifact records cannot be re-rendered: guessing it could change the project's rules (a
    // question the pack gained after the project adopted it is the one exception: it takes its default, 0085). So the
    // pack is left as it is and the owner is told how to supply the answers.
    const known = renameAnswers(pack, currentAnswers(adopted));
    const adoptedAt = String(adopted[0]?.data['go-getter']?.['generated-by'] ?? '').split('@')[1] ?? '0.0.0';
    const isNew = (q) => q.since && compareVersions(q.since, adoptedAt) > 0;
    const missing = activeQuestions(pack, withFallbacks(pack, known)).filter((q) => known[q.id] === undefined && !isNew(q)).map((q) => q.id);
    if (missing.length) {
      notes.push(`pack ${id}: no recorded answer for ${missing.join(', ')}; left as it is. Run go-getter reconfigure ${id} --current, add those answers to an answers file and run go-getter reconfigure ${id} --answers <file>`);
      continue;
    }
    // Decisions an update adds are proposals (decision 0091): rendered as draft, for the owner to accept.
    const result = planReconfigure({ project, pack, answers: currentAnswers(adopted), date, detect: {}, draft: true });
    const artifacts = result.plan.artifacts.map((a) => keepDate(project, a));
    const differs = (rel, content) => !existsSync(path.join(project, rel)) || readFileSync(path.join(project, rel), 'utf8') !== content;
    result.plan = {
      ...result.plan,
      artifacts: artifacts.filter((a) => differs(a.path, a.content)),
      files: result.plan.files.filter((f) => differs(f.path, f.content)),
    };
    applyReconfigure({ project, result });
  }
}

// Runs the whole update on `project`; returns the files apply left as `modified`.
export function runUpdate(project, { root, date, force = false }) {
  const notes = [];
  const manifest = readManifest(project);
  if (manifest && manifest.schema > SCHEMA) {
    throw new Error(`the manifest has schema ${manifest.schema}, newer than this go-getter (${SCHEMA}); install a newer go-getter`);
  }
  if (!manifest) bootstrap(project);
  reRender(project, root, date, notes);
  const plan = planApply(project, { force });
  notes.push(...(plan.notes ?? []).map((n) => n.replace(/^note: /, '')));
  const { modified } = applyPlan(project, plan);
  return { modified, notes };
}

// Path to content hash (or link target) for each of `files`, or for every file under `dir` when none are given
// (skipping `.git` at the top and `node_modules` anywhere).
function hashOf(dir, r) {
  const stat = lstatSync(path.join(dir, r));
  return stat.isSymbolicLink() ? `-> ${readlinkSync(path.join(dir, r))}` : createHash('sha256').update(readFileSync(path.join(dir, r))).digest('hex');
}

function tree(dir, files, rel = '') {
  const out = new Map();
  if (files) {
    for (const r of files) out.set(r, hashOf(dir, r));
    return out;
  }
  for (const name of readdirSync(path.join(dir, rel)).sort()) {
    if (name === 'node_modules' || (!rel && name === '.git')) continue;
    const r = rel ? `${rel}/${name}` : name;
    if (lstatSync(path.join(dir, r)).isDirectory()) for (const [k, v] of tree(dir, undefined, r)) out.set(k, v);
    else out.set(r, hashOf(dir, r));
  }
  return out;
}

// The files an update works on: what git tracks or would add (so build output such as `target/` is not copied), plus
// the generated files the manifest owns even when git ignores them (`.go-getter/cli`). Undefined outside a git repository.
function projectFiles(project) {
  if (!existsSync(path.join(project, '.git'))) return undefined;
  let listed;
  try {
    listed = execFileSync('git', ['ls-files', '-z', '-c', '-o', '--exclude-standard'], { cwd: project, encoding: 'utf8', maxBuffer: 1 << 28, stdio: ['ignore', 'pipe', 'ignore'] });
  } catch {
    return undefined;
  }
  const files = new Set(listed.split('\0').filter(Boolean));
  for (const rel of Object.keys(readManifest(project)?.files ?? {})) files.add(rel);
  for (const rel of [...files]) if (rel.split('/').includes('node_modules') || (!existsSync(path.join(project, rel)) && !isLink(project, rel))) files.delete(rel);
  return [...files].sort();
}

const isLink = (project, rel) => {
  try {
    return lstatSync(path.join(project, rel)).isSymbolicLink();
  } catch {
    return false;
  }
};

const gitOut = (cwd, ...args) => {
  try {
    return execFileSync('git', args, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
  } catch {
    return '';
  }
};

// The copy has no history: it gets the settings detection and apply read (current branch, origin and its HEAD,
// core.hooksPath), so its plan matches the real one, and its own git directory, so nothing reaches the real repository.
function copyGitState(project, scratch) {
  if (!existsSync(path.join(project, '.git'))) return;
  const branch = gitOut(project, 'branch', '--show-current') || 'main';
  const remote = gitOut(project, 'remote', 'get-url', 'origin');
  const originHead = gitOut(project, 'symbolic-ref', 'refs/remotes/origin/HEAD');
  const hooksPath = gitSetting(project, 'core.hooksPath');
  execFileSync('git', ['init', '-q', '-b', branch], { cwd: scratch });
  if (remote) execFileSync('git', ['remote', 'add', 'origin', remote], { cwd: scratch });
  if (originHead) execFileSync('git', ['symbolic-ref', 'refs/remotes/origin/HEAD', originHead], { cwd: scratch });
  if (hooksPath !== undefined) execFileSync('git', ['config', 'core.hooksPath', hooksPath], { cwd: scratch });
}

// What an update would change, by running it on a scratch copy: { added, changed, removed, modified, notes, docs }.
export function planUpdate(project, opts) {
  const scratch = mkdtempSync(path.join(tmpdir(), 'gg-update-'));
  try {
    const files = projectFiles(project);
    if (files) {
      for (const rel of files) {
        mkdirSync(path.dirname(path.join(scratch, rel)), { recursive: true });
        const from = path.join(project, rel);
        const stat = lstatSync(from);
        if (stat.isSymbolicLink()) symlinkSync(readlinkSync(from), path.join(scratch, rel));
        else if (stat.isDirectory()) mkdirSync(path.join(scratch, rel), { recursive: true });
        else cpSync(from, path.join(scratch, rel));
      }
    } else {
      cpSync(project, scratch, { recursive: true, verbatimSymlinks: true, filter: (src) => src === project || !skipped(path.basename(src)) });
    }
    copyGitState(project, scratch);
    const before = tree(project, files);
    const { modified, notes } = runUpdate(scratch, opts);
    const after = tree(scratch);
    const added = [...after.keys()].filter((k) => !before.has(k));
    const removed = [...before.keys()].filter((k) => !after.has(k));
    const changed = [...after.keys()].filter((k) => before.has(k) && before.get(k) !== after.get(k));
    return { added, changed, removed, modified, notes, git: gitSetting(scratch, 'core.hooksPath') !== gitSetting(project, 'core.hooksPath') };
  } finally {
    rmSync(scratch, { recursive: true, force: true });
  }
}

export const isDocs = (p) => p.startsWith('docs/');

export function writePlanSummary(plan, log = console.log) {
  const groups = [
    ['docs re-rendered', [...plan.added, ...plan.changed].filter(isDocs)],
    ['docs removed', plan.removed.filter(isDocs)],
    ['files added', plan.added.filter((p) => !isDocs(p))],
    ['files changed', plan.changed.filter((p) => !isDocs(p))],
    ['files removed', plan.removed.filter((p) => !isDocs(p))],
  ];
  let any = false;
  for (const [label, list] of groups) {
    if (!list.length) continue;
    any = true;
    log(`  ${label}:`);
    for (const p of list) log(`    ${p}`);
  }
  if (plan.git) {
    any = true;
    log('  git config core.hooksPath changes');
  }
  if (!any) log('  nothing to change');
  for (const n of plan.notes) log(`  note: ${n}`);
  return any;
}
