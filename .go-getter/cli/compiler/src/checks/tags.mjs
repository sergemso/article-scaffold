// Guardrail tags-from-canonical-list: every artifact tag must be on docs/skills/tags.md.
import { readArtifacts, readTagVocabulary } from '../artifacts.mjs';

export function tagProblems(artifacts, vocabulary) {
  const problems = [];
  for (const a of artifacts) {
    const tags = a.data?.tags;
    if (!Array.isArray(tags)) {
      problems.push(`${a.file}: tags must be a list`);
      continue;
    }
    for (const t of tags) if (!vocabulary.has(t)) problems.push(`${a.file}: tag "${t}" is not in docs/skills/tags.md`);
  }
  return problems;
}

export default function checkTags({ root }) {
  const vocabulary = readTagVocabulary(root);
  if (!vocabulary) {
    console.log('check tags: no docs/skills/tags.md; skipped');
    return 0;
  }
  const problems = tagProblems(readArtifacts(root), vocabulary);
  if (problems.length) {
    console.error('check tags:');
    for (const p of problems) console.error(`  ${p}`);
    return 1;
  }
  console.log('check tags: ok');
  return 0;
}
