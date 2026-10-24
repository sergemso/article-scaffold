// Reconfigure an adopted pack (plan 4.5): changed answers supersede their decisions (decisions are immutable),
// non-decision artifacts are re-rendered in place, and artifacts no longer produced are deprecated.
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { readArtifacts } from './artifacts.mjs';
import { parseFrontmatter, stringifyFrontmatter } from './frontmatter.mjs';
import { planRender, applyRender, activeQuestions, setIndexStatus, withFallbacks, renameAnswers } from './render.mjs';

const same = (a, b) => JSON.stringify([].concat(a ?? []).sort()) === JSON.stringify([].concat(b ?? []).sort());

// Pack-rendered artifacts count as adopted while still draft (decision 0091: a draft stays draft until accepted).
export function adoptedArtifacts(project, packId) {
  return readArtifacts(project).filter((a) => ['active', 'draft'].includes(a.data.status) && String(a.data['go-getter']?.['generated-by'] ?? '').startsWith(`${packId}@`));
}

export function currentAnswers(artifacts) {
  const answers = {};
  for (const a of artifacts) {
    const g = a.data['go-getter'];
    if (g['pack-answer'] && g['pack-option'] !== undefined) answers[g['pack-answer']] ??= g['pack-option'];
    // `provider` (asked only for internal-data: single-provider) has no decision of its own: the internal-data decision
    // holds it as the registry's one provider.
    if (g['pack-answer'] === 'internal-data' && g['pack-option'] === 'single-provider') {
      const id = g['model-registry']?.providers?.[0]?.id;
      if (typeof id === 'string' && id) answers.provider ??= id;
    }
  }
  return answers;
}

export function planReconfigure({ project, pack, answers: given, acceptedBy, date, detect, draft = false }) {
  const answers = withFallbacks(pack, given);
  const adopted = adoptedArtifacts(project, pack.id);
  if (!adopted.length) throw new Error(`pack "${pack.id}" has not been adopted here; run render-pack first`);
  const before = renameAnswers(pack, currentAnswers(adopted));
  const active = new Set(activeQuestions(pack, answers).map((q) => q.id));
  const changed = new Set(pack.questions.map((q) => q.id).filter((q) => !same(before[q], active.has(q) ? answers[q] : undefined)));
  const oldDecisions = adopted.filter((a) => a.type === 'decisions');
  const keepDecisionsFor = new Set();
  const decisionIds = {};
  for (const d of oldDecisions) {
    const q = d.data['go-getter']['pack-answer'];
    if (!changed.has(q)) {
      keepDecisionsFor.add(q);
      decisionIds[q] ??= d.id;
    }
  }
  const overwritable = new Set(adopted.filter((a) => a.type !== 'decisions').map((a) => a.file.split(path.sep).join('/')));
  const artifactIds = {};
  for (const a of adopted) if (a.type !== 'decisions') artifactIds[`${a.type}/${a.id.replace(/^\d+-/, '')}`] = a.id;
  const plan = planRender({ root: project, pack, answers, acceptedBy, date, detect, draft, existing: { keepDecisionsFor, decisionIds, overwritable, artifactIds } });

  const emitted = new Set(plan.artifacts.map((a) => a.path));
  const statusChanges = [];
  for (const d of oldDecisions) {
    const q = d.data['go-getter']['pack-answer'];
    if (!changed.has(q)) continue;
    const successor = plan.artifacts.find((a) => a.kind === 'decisions' && a.questionId === q);
    statusChanges.push(successor ? { artifact: d, status: 'superseded', supersededBy: successor.id } : { artifact: d, status: 'deprecated' });
  }
  for (const a of adopted) {
    if (a.type !== 'decisions' && !emitted.has(a.file.split(path.sep).join('/'))) statusChanges.push({ artifact: a, status: 'deprecated' });
  }
  return { plan, changed: [...changed], statusChanges };
}

export function applyReconfigure({ project, result }) {
  for (const { artifact, status, supersededBy } of result.statusChanges) {
    const file = path.join(project, artifact.file);
    const { data, body } = parseFrontmatter(readFileSync(file, 'utf8'));
    const next = {};
    for (const [k, v] of Object.entries(data)) {
      next[k] = k === 'status' ? status : v;
      if (k === 'status' && supersededBy) next['superseded-by'] = supersededBy;
    }
    writeFileSync(file, stringifyFrontmatter(next, body));
    setIndexStatus(path.join(project, 'docs', artifact.type, 'INDEX.md'), artifact.id, status);
  }
  return [...applyRender({ root: project, plan: result.plan }), ...result.statusChanges.map((s) => s.artifact.file)];
}
