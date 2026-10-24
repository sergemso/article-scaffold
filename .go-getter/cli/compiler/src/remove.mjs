// `go-getter apply --remove` (decision 0090): undo every item the manifest lists. A file, key or block edited since
// go-getter wrote it is `modified`: kept, reported and left in the manifest, unless `force`. `docs/` and
// `.go-getter/state` are never touched.
import { existsSync, readFileSync, writeFileSync, rmSync, readdirSync, rmdirSync } from 'node:fs';
import path from 'node:path';
import { MANIFEST, SCHEMA, readManifest, manifestText } from './manifest.mjs';
import { undoJson, blockOf, hashContent, fileEdited, gitSetting, setGitSetting, isLink, MARK_START, MARK_END } from './reconcile.mjs';

const MARKERS = [MARK_START, MARK_END];
const PROTECTED = [/^docs(\/|$)/, /^\.go-getter\/state(\/|$)/];

const safe = (rel) => {
  const norm = path.posix.normalize(rel);
  if (path.isAbsolute(rel) || norm.startsWith('..') || PROTECTED.some((re) => re.test(norm))) throw new Error(`apply --remove: the manifest lists ${rel}, which go-getter never removes`);
  return rel;
};

// The text with the go-getter block taken out, and the blank line that separated it from the text before it.
function withoutBlock(text) {
  const block = blockOf(text, MARKERS);
  const from = text.indexOf(block);
  const before = text.slice(0, from).replace(/\n*$/, '');
  const after = text.slice(from + block.length).replace(/^\n*/, '');
  return before && after ? `${before}\n\n${after}` : `${before}${after}`.replace(/\n*$/, '') + '\n';
}

// Plans the removal: { steps: [{ text, run }], modified, remaining }, where `remaining` is the manifest that is left
// when modified items were kept (null when the manifest goes too).
export function planRemove(project, { force = false } = {}) {
  const manifest = readManifest(project);
  if (!manifest) throw new Error('apply --remove: no .go-getter/manifest.json here; nothing is recorded as go-getter\'s');
  if (manifest.schema > SCHEMA) throw new Error(`apply --remove: the manifest has schema ${manifest.schema}, newer than this go-getter understands (${SCHEMA})`);
  const steps = [];
  const modified = [];
  const kept = { files: {}, shared: {} };
  const abs = (rel) => path.join(project, safe(rel));
  const keep = (rel, what, reason) => modified.push({ path: rel, what, reason });

  for (const [rel, rec] of Object.entries(manifest.files ?? {})) {
    if (!existsSync(abs(rel)) && !isLink(abs(rel))) continue;
    if (!force && fileEdited(project, rel, rec)) {
      keep(rel, 'file', 'edited since go-getter wrote it');
      kept.files[rel] = rec;
    } else steps.push({ text: `delete ${rel}`, run: () => rmSync(abs(rel), { force: true }), deleted: rel });
  }

  for (const [rel, items] of Object.entries(manifest.shared ?? {})) {
    if (rel === 'git-config') {
      const [rec] = items;
      const now = gitSetting(project, rec.setting);
      if (now === undefined) continue;
      if (rec.unknown) {
        // What the setting was before go-getter is not recorded, so it stays as it is.
        steps.push({ text: `keep ${rec.setting} = ${now} (its previous value was not recorded)`, run: () => {} });
      } else if (!force && now !== rec.value) {
        keep(rec.setting, 'git-config', `changed to ${now} since go-getter set it`);
        kept.shared[rel] = items;
      } else steps.push({ text: rec.replaced === undefined ? `unset ${rec.setting}` : `restore ${rec.setting} = ${rec.replaced}`, run: () => setGitSetting(project, rec.setting, rec.replaced) });
    } else if (items[0]?.kind === 'block') {
      if (!existsSync(abs(rel))) continue;
      const [rec] = items;
      const text = readFileSync(abs(rel), 'utf8');
      const block = blockOf(text, MARKERS);
      if (!block) continue;
      if (!force && hashContent(block) !== rec.hash) {
        keep(rel, 'block', 'the go-getter block was edited since go-getter wrote it');
        kept.shared[rel] = items;
        continue;
      }
      const rest = withoutBlock(text);
      // A file go-getter created holds nothing else once its block is gone.
      if (rec.created && ['', '# AGENTS.md'].includes(rest.trim())) steps.push({ text: `delete ${rel}`, run: () => rmSync(abs(rel), { force: true }), deleted: rel });
      else steps.push({ text: `remove the go-getter block from ${rel}`, run: () => writeFileSync(abs(rel), rest) });
    } else {
      if (!existsSync(abs(rel))) continue;
      const { json, modified: edited } = undoJson(JSON.parse(readFileSync(abs(rel), 'utf8')), items, force);
      for (const item of edited) keep(rel, 'key', `${item.path.join('.')} was edited since go-getter wrote it`);
      if (edited.length) kept.shared[rel] = edited;
      if (!Object.keys(json).length) steps.push({ text: `delete ${rel}`, run: () => rmSync(abs(rel), { force: true }), deleted: rel });
      else steps.push({ text: `restore ${items.filter((i) => !i.unknown).length - edited.length} owned part(s) of ${rel}${items.some((i) => i.unknown) ? ` (${items.filter((i) => i.unknown).length} key(s) whose old value was not recorded stay)` : ''}`, run: () => writeFileSync(abs(rel), `${JSON.stringify(json, null, 2)}\n`) });
    }
  }

  const remaining = modified.length ? { ...manifest, files: kept.files, shared: kept.shared } : null;
  steps.push(remaining
    ? { text: `keep ${MANIFEST} with the ${modified.length} modified item(s)`, run: () => writeFileSync(abs(MANIFEST), manifestText(remaining)) }
    : { text: `delete ${MANIFEST}`, run: () => rmSync(abs(MANIFEST), { force: true }), deleted: MANIFEST });
  return { steps, modified, remaining };
}

// Runs the plan, then removes the directories it emptied (never above the project).
export function applyRemove(project, plan) {
  const dirs = new Set();
  for (const step of plan.steps) {
    step.run();
    if (step.deleted) for (let d = path.dirname(step.deleted); d !== '.'; d = path.dirname(d)) dirs.add(d);
  }
  for (const d of [...dirs].sort((a, b) => b.length - a.length)) {
    const dir = path.join(project, d);
    if (PROTECTED.some((re) => re.test(d))) continue;
    try {
      if (existsSync(dir) && readdirSync(dir).length === 0) rmdirSync(dir);
    } catch {
      // not empty or not removable: leave it
    }
  }
}
