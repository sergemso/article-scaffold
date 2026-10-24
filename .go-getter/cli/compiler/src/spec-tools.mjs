// Spec and change tools go-getter detects and tolerates (decision 0075). One row per tool; detect, refs, attribute and
// conform read this table, so a second tool is a row and a test. go-getter adds no validation, format or pack for them.
import { existsSync, readdirSync } from 'node:fs';
import path from 'node:path';

export const SPEC_TOOLS = [
  {
    id: 'openspec',
    // Present when the tool's directory holds any of these (fact 0029).
    detect: { dir: 'openspec', anyOf: ['config.yaml', 'specs', 'changes'] },
    // A change folder is `<changes>/<id>` or `<changes>/archive/<YYYY-MM-DD>-<id>`; <id> is lowercase kebab-case.
    changes: 'openspec/changes',
    id_pattern: '[a-z0-9]+(?:-[a-z0-9]+)*',
  },
];

export function detectSpecTool(root) {
  for (const tool of SPEC_TOOLS) {
    if (tool.detect.anyOf.some((f) => existsSync(path.join(root, tool.detect.dir, f)))) return tool.id;
  }
  return null;
}

const matcher = (tool) =>
  new RegExp(`^(${tool.changes}/(?:archive/(\\d{4}-\\d{2}-\\d{2})-(${tool.id_pattern})|(?!archive(?:/|$))(${tool.id_pattern})))(?:/|$)`);

// The change a repo-relative path belongs to: { tool, id, folder, archived } or null.
export function changeOfPath(file, tools = SPEC_TOOLS) {
  const p = String(file).split(path.sep).join('/');
  for (const tool of tools) {
    const m = matcher(tool).exec(p);
    if (m) return { tool: tool.id, id: m[3] ?? m[4], folder: m[1], archived: m[2] !== undefined };
  }
  return null;
}

// The distinct changes the paths touch, in first-seen order.
export function changesTouched(files, tools = SPEC_TOOLS) {
  const seen = new Map();
  for (const f of files) {
    const c = changeOfPath(f, tools);
    if (c && !seen.has(c.folder)) seen.set(c.folder, c);
  }
  return [...seen.values()];
}

// The changes that exist on disk, live and archived: [{ tool, id, folder, archived }].
export function listChanges(root, tools = SPEC_TOOLS) {
  const found = [];
  for (const tool of tools) {
    const dir = path.join(root, tool.changes);
    if (!existsSync(dir)) continue;
    const entries = (d) => readdirSync(d, { withFileTypes: true }).filter((e) => e.isDirectory()).map((e) => e.name).sort();
    for (const name of entries(dir)) {
      const live = changeOfPath(`${tool.changes}/${name}/`, tools);
      if (live && name !== 'archive') found.push(live);
    }
    if (existsSync(path.join(dir, 'archive'))) {
      for (const name of entries(path.join(dir, 'archive'))) {
        const archived = changeOfPath(`${tool.changes}/archive/${name}/`, tools);
        if (archived) found.push(archived);
      }
    }
  }
  return found;
}
