// Reconciling the project with the manifest (decision 0089): undo what go-getter owns in shared files, detect what
// was modified since go-getter wrote it, so apply never clobbers an edit without --force.
import { lstatSync, readFileSync, readlinkSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import path from 'node:path';

export const MARK_START = '<!-- go-getter:start -->';
export const MARK_END = '<!-- go-getter:end -->';
export const isLink = (file) => {
  try {
    return lstatSync(file).isSymbolicLink();
  } catch {
    return false;
  }
};

export const hashContent = (content) => `sha256:${createHash('sha256').update(content).digest('hex')}`;

const isObject = (v) => typeof v === 'object' && v !== null && !Array.isArray(v);
export const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
export const at = (obj, keys) => keys.reduce((n, k) => (isObject(n) ? n[k] : undefined), obj);

// Set the value at a path (cloning), or delete the key when value is undefined, pruning objects that become empty.
export function setAt(obj, keys, value) {
  const out = structuredClone(obj);
  const trail = [out];
  for (const k of keys.slice(0, -1)) {
    const node = trail.at(-1);
    if (!isObject(node[k])) {
      if (value === undefined) return out;
      node[k] = {};
    }
    trail.push(node[k]);
  }
  const last = keys.at(-1);
  if (value === undefined) delete trail.at(-1)[last];
  else trail.at(-1)[last] = value;
  for (let i = keys.length - 1; i > 0 && value === undefined && Object.keys(trail[i]).length === 0; i--) delete trail[i - 1][keys[i - 1]];
  return out;
}

// Undo the owned parts of a shared JSON file: restore the value a key replaced (delete it when it was new) and remove
// the array items go-getter added. A key whose current value is no longer the recorded one is `modified` and left alone,
// unless `force`.
export function undoJson(current, items, force = false) {
  let out = structuredClone(current);
  const modified = [];
  for (const item of items) {
    const now = at(out, item.path);
    if (item.unknown) continue; // the value it replaced was never recorded: left in place
    if (item.kind === 'items') {
      if (!Array.isArray(now)) continue;
      const rest = now.filter((x) => !item.items.some((y) => same(x, y)));
      out = setAt(out, item.path, rest.length ? rest : undefined);
    } else if (now === undefined) continue;
    else if (force || same(now, item.value)) out = setAt(out, item.path, item.replaced);
    else modified.push(item);
  }
  return { json: out, modified };
}

// The marked block (markers included) in a text, or null.
export function blockOf(text, [start, end]) {
  const from = text.indexOf(start);
  const to = text.indexOf(end);
  return from === -1 || to === -1 ? null : text.slice(from, to + end.length);
}

// Whether a file go-getter owns was edited since it wrote it (`rec` is its manifest entry; without one, any file is
// not go-getter's). A missing file is not edited.
export function fileEdited(project, rel, rec) {
  const file = path.join(project, rel);
  let stat;
  try {
    stat = lstatSync(file);
  } catch {
    return false;
  }
  if (rec && 'symlink' in rec) return !stat.isSymbolicLink() || readlinkSync(file) !== rec.symlink;
  return stat.isSymbolicLink() || (rec ? hashContent(readFileSync(file, 'utf8')) !== rec.hash : true);
}

// The project's local value of a git setting, undefined when unset or outside a repository.
export function gitSetting(project, name) {
  try {
    return execFileSync('git', ['config', '--local', '--get', name], { cwd: project, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
  } catch {
    return undefined;
  }
}

// Set a local git setting, or unset it when value is undefined. Outside a repository this does nothing.
export function setGitSetting(project, name, value) {
  try {
    execFileSync('git', value === undefined ? ['config', '--local', '--unset', name] : ['config', '--local', name, value], { cwd: project, stdio: 'ignore' });
  } catch {
    // not a git repository, or already unset
  }
}
