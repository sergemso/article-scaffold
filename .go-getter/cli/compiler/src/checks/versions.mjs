// Release check: every generated manifest carries the version in package.json (decision 0021: one source of truth),
// and, with --tag <vX.Y.Z>, the release tag names that same version.
import { readFileSync, existsSync } from 'node:fs';
import path from 'node:path';

// Generated manifests that carry a version (the paths the build writes; see build.mjs and the adapters).
export const MANIFESTS = [
  'gemini-extension.json',
  'plugins/go-getter/plugin.json',
  'plugins/go-getter/.claude-plugin/plugin.json',
  'plugins/go-getter/.codex-plugin/plugin.json',
  'skills/index.json',
];

// Every "version" a manifest declares, as [location, value]; skills/index.json lists one per skill.
export function versionsIn(file, json) {
  const found = [];
  if (typeof json.version === 'string') found.push([file, json.version]);
  for (const s of json.skills ?? []) if (typeof s?.version === 'string') found.push([`${file}#${s.name}`, s.version]);
  return found;
}

export function versionProblems({ root, tag }) {
  const expected = JSON.parse(readFileSync(path.join(root, 'package.json'), 'utf8')).version;
  const problems = [];
  if (tag !== undefined && tag !== `v${expected}`) problems.push(`tag ${tag} does not match package.json version ${expected} (expected v${expected})`);
  for (const file of MANIFESTS) {
    const abs = path.join(root, file);
    if (!existsSync(abs)) {
      problems.push(`${file}: missing`);
      continue;
    }
    const found = versionsIn(file, JSON.parse(readFileSync(abs, 'utf8')));
    if (!found.length) problems.push(`${file}: declares no version`);
    for (const [where, v] of found) if (v !== expected) problems.push(`${where}: version ${v}, package.json has ${expected}`);
  }
  return problems;
}

export default function checkVersions({ root, args }) {
  const i = args.indexOf('--tag');
  const tag = i >= 0 ? args[i + 1] : undefined;
  const problems = versionProblems({ root, tag });
  if (problems.length) {
    console.error('check versions: generated manifests disagree with package.json (run "npm run build" after bumping it):');
    for (const p of problems) console.error(`  ${p}`);
    return 1;
  }
  console.log('check versions: ok');
  return 0;
}
