// Reads knowledge-base artifacts (facts, decisions, guardrails, skills) under docs/.
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import path from 'node:path';
import { parseFrontmatter } from './frontmatter.mjs';

export const ARTIFACT_TYPES = ['facts', 'decisions', 'guardrails', 'skills'];

export function readArtifacts(root, types = ARTIFACT_TYPES) {
  const out = [];
  for (const type of types) {
    const dir = path.join(root, 'docs', type);
    if (!existsSync(dir)) continue;
    for (const name of readdirSync(dir).sort()) {
      if (!name.endsWith('.md') || name === 'INDEX.md') continue;
      const file = path.join(dir, name);
      const { data, body } = parseFrontmatter(readFileSync(file, 'utf8'));
      out.push({ type, file: path.relative(root, file), id: name.slice(0, -3), data, body });
    }
  }
  return out;
}

export function readTagVocabulary(root) {
  const file = path.join(root, 'docs/skills/tags.md');
  if (!existsSync(file)) return null;
  const tags = new Set();
  for (const line of readFileSync(file, 'utf8').split('\n')) {
    const m = /^([a-z0-9][a-z0-9-]*) — /.exec(line);
    if (m) tags.add(m[1]);
  }
  return tags;
}
