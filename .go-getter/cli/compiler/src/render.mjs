// Deterministic pack renderer (plan 4.3, decision 0022): pack + answers -> knowledge-base artifacts, INDEX rows, files.
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync, appendFileSync } from 'node:fs';
import path from 'node:path';
import { stringifyFrontmatter } from './frontmatter.mjs';
import { readTagVocabulary } from './artifacts.mjs';
import { ANY_ANSWER } from './packs.mjs';

const KIND_DIR = { decisions: 'decisions', facts: 'facts', guardrails: 'guardrails', procedures: 'skills' };
const NUMBERED = new Set(['decisions', 'facts']);
const INDEX_HEADER = { decisions: 'Decisions', facts: 'Facts', guardrails: 'Guardrails', skills: 'Skills' };

// Flattens detection results into {{detect.a.b}} variables; unknown (null) values stay undefined so a template that needs them fails loudly.
function addDetectVars(vars, prefix, value) {
  if (value === null || value === undefined) return;
  if (Array.isArray(value)) vars[prefix] = value.join(', ');
  else if (typeof value === 'object') for (const [k, v] of Object.entries(value)) addDetectVars(vars, `${prefix}.${k}`, v);
  else vars[prefix] = String(value);
}

function checkAnswer(q, a) {
  const type = q.type ?? 'choice';
  if (type === 'choice') {
    for (const opt of [].concat(a)) if (!q.options.some((o) => o.id === opt)) throw new Error(`answer "${opt}" is not an option of "${q.id}"`);
    if (!q.multi && Array.isArray(a)) throw new Error(`question "${q.id}" takes one answer`);
    return;
  }
  if (type === 'text' ? typeof a !== 'string' : !Array.isArray(a) || a.some((x) => typeof x !== 'string')) {
    throw new Error(`question "${q.id}" takes ${type === 'text' ? 'a string' : 'an array of strings'}`);
  }
  if (q.pattern) {
    const re = new RegExp(q.pattern);
    for (const item of [].concat(a)) if (!re.test(item)) throw new Error(`answer "${item}" does not match the pattern of "${q.id}" (${q.pattern})`);
  }
}

// Answers recorded under an option id the pack has since renamed (`renamed` on a question), mapped to the new id.
export function renameAnswers(pack, answers) {
  const out = { ...answers };
  for (const q of pack.questions) {
    if (!q.renamed || out[q.id] === undefined) continue;
    const map = (a) => q.renamed[a] ?? a;
    out[q.id] = Array.isArray(out[q.id]) ? out[q.id].map(map) : map(out[q.id]);
  }
  return out;
}

// A question added in a later pack version (`since`) may be missing from an older answer file: it takes its default
// or recommended option, so the older answers still render.
export function withFallbacks(pack, answers) {
  const filled = renameAnswers(pack, answers);
  for (const q of pack.questions) {
    if (!q.since || filled[q.id] !== undefined) continue;
    filled[q.id] = q.options ? q.options.find((o) => o.recommended).id : q.default;
  }
  return filled;
}

export function activeQuestions(pack, answers) {
  return pack.questions.filter((q) => {
    if (!q.when) return true;
    const prior = [].concat(answers[q.when.question] ?? []);
    return prior.some((a) => q.when.in.includes(a));
  });
}

function substitute(value, vars) {
  if (typeof value === 'string') {
    return value.replace(/\{\{\s*([a-z]+(?:\.[A-Za-z0-9_-]+)*)\s*\}\}/g, (whole, key) => {
      if (!(key in vars)) throw new Error(`placeholder ${whole} has no value`);
      return vars[key];
    });
  }
  if (Array.isArray(value)) return value.map((v) => substitute(v, vars));
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, substitute(v, vars)]));
  return value;
}

export function nextNumber(dir) {
  if (!existsSync(dir)) return 1;
  const nums = readdirSync(dir).map((n) => /^(\d{4})-/.exec(n)?.[1]).filter(Boolean).map(Number);
  return nums.length ? Math.max(...nums) + 1 : 1;
}

const csv = (s) => `"${String(s).replace(/"/g, '""')}"`;

// Replaces the INDEX.md row for `id`, or appends it.
export function setIndexRow(indexFile, id, row) {
  const lines = readFileSync(indexFile, 'utf8').replace(/\n*$/, '').split('\n');
  const at = lines.findIndex((l) => l.startsWith(`${id},`));
  if (at >= 0) lines[at] = row;
  else lines.push(row);
  writeFileSync(indexFile, `${lines.join('\n')}\n`);
}

// Changes the status column of an existing INDEX.md row.
export function setIndexStatus(indexFile, id, status) {
  if (!existsSync(indexFile)) return;
  const lines = readFileSync(indexFile, 'utf8').replace(/\n*$/, '').split('\n');
  const at = lines.findIndex((l) => l.startsWith(`${id},`));
  if (at >= 0) lines[at] = lines[at].replace(/,[a-z]+$/, `,${status}`);
  writeFileSync(indexFile, `${lines.join('\n')}\n`);
}

// Returns { artifacts: [{kind, id, path, content}], files: [{path, content}], newTags: [] } without touching disk.
// `existing` (reconfigure): keepDecisionsFor = questions whose decisions stay (with their ids in decisionIds);
// overwritable = paths of previously generated non-decision artifacts that may be re-rendered in place, artifactIds =
// their ids by `<dir>/<slug>`, so a re-render keeps the number it was adopted with.
// `draft`: decisions are rendered as `draft` without `accepted-by` (decision 0091: update proposes, the owner accepts).
export function planRender({ root, pack, answers: given, acceptedBy, date, detect = {}, existing = {}, draft = false }) {
  const answers = withFallbacks(pack, given);
  const keep = existing.keepDecisionsFor ?? new Set();
  const overwritable = existing.overwritable ?? new Set();
  const questions = activeQuestions(pack, answers);
  for (const q of questions) {
    const a = answers[q.id];
    if (a === undefined) throw new Error(`no answer for question "${q.id}"`);
    checkAnswer(q, a);
  }
  const vars = { 'pack.id': pack.id, 'pack.version': pack.version };
  for (const q of questions) {
    const chosen = [].concat(answers[q.id]);
    vars[`answer.${q.id}`] = chosen.join(', ');
    if (q.options) vars[`label.${q.id}`] = chosen.map((c) => q.options.find((o) => o.id === c).label).join(', ');
  }
  addDetectVars(vars, 'detect', detect);

  const counters = {};
  const artifacts = [];
  const files = [];
  const usedTags = new Set();
  const generatedBy = `${pack.id}@${pack.version}`;

  for (const q of questions) {
    for (const option of q.options ? [].concat(answers[q.id]) : [ANY_ANSWER]) {
      const out = pack.outputs[q.id]?.[option] ?? {};
      // Decisions first so later templates in the same answer can reference {{id.decision.<q>}}.
      for (const kind of ['decisions', 'facts', 'guardrails', 'procedures']) {
        for (const tpl of out[kind] ?? []) {
          const dir = KIND_DIR[kind];
          if (kind === 'decisions' && keep.has(q.id)) {
            vars[`id.decision.${q.id}`] ??= existing.decisionIds[q.id];
            continue;
          }
          let id = tpl.slug;
          if (NUMBERED.has(kind)) {
            const adopted = kind === 'decisions' ? undefined : existing.artifactIds?.[`${dir}/${tpl.slug}`];
            if (adopted) id = adopted;
            else {
              counters[dir] ??= nextNumber(path.join(root, 'docs', dir));
              id = `${String(counters[dir]++).padStart(4, '0')}-${tpl.slug}`;
            }
          }
          if (kind === 'decisions') vars[`id.decision.${q.id}`] ??= id;
          const rendered = substitute(tpl, vars);
          // A template's own `go-getter` data (e.g. roles, access) merges with the keys the renderer owns.
          const { 'go-getter': own = {}, ...extra } = rendered.frontmatter ?? {};
          const status = draft && kind === 'decisions' ? 'draft' : 'active';
          const data = { id, title: rendered.title, status, date, tags: rendered.tags, ...extra };
          if (kind === 'decisions') {
            if (!data.track) throw new Error(`decision template "${tpl.slug}" needs frontmatter.track`);
            if (status === 'active') {
              if (!acceptedBy) throw new Error('acceptedBy is required to render active decisions');
              data['accepted-by'] = acceptedBy;
            }
          }
          if (kind === 'facts' && !data.kind) throw new Error(`fact template "${tpl.slug}" needs frontmatter.kind`);
          if (kind === 'guardrails') {
            for (const f of ['governed-by', 'grounded-in', 'derivation-note']) if (!data[f]) throw new Error(`guardrail template "${tpl.slug}" needs frontmatter.${f}`);
          }
          data['go-getter'] = {
            ...own,
            ...(rendered.enforcement ? { enforcement: rendered.enforcement } : {}),
            'generated-by': generatedBy,
            'pack-answer': q.id,
            'pack-option': q.multi ? [].concat(answers[q.id]) : answers[q.id],
          };
          rendered.tags.forEach((t) => usedTags.add(t));
          const rel = `docs/${dir}/${id}.md`;
          const replaces = existsSync(path.join(root, rel));
          if (replaces && !overwritable.has(rel)) throw new Error(`${rel} already exists (use reconfigure to change an adopted pack)`);
          artifacts.push({ kind: dir, id, status, title: rendered.title, tags: rendered.tags, path: rel, replaces, questionId: q.id, content: stringifyFrontmatter(data, `\n${rendered.body.trimEnd()}\n`) });
        }
      }
      for (const f of out.files ?? []) {
        const rel = path.normalize(substitute(f.path, vars));
        if (path.isAbsolute(rel) || rel.startsWith('..') || rel.startsWith(`docs${path.sep}`)) throw new Error(`file path "${f.path}" must stay inside the project and outside docs/`);
        files.push({ path: rel.split(path.sep).join('/'), content: substitute(f.content, vars) });
      }
    }
  }
  const vocabulary = readTagVocabulary(root);
  const newTags = vocabulary ? [...usedTags].filter((t) => !vocabulary.has(t)).sort() : [];
  return { artifacts, files, newTags, generatedBy };
}

export function applyRender({ root, plan }) {
  for (const a of plan.artifacts) {
    mkdirSync(path.join(root, path.dirname(a.path)), { recursive: true });
    writeFileSync(path.join(root, a.path), a.content);
    const index = path.join(root, 'docs', a.kind, 'INDEX.md');
    if (!existsSync(index)) writeFileSync(index, `# ${INDEX_HEADER[a.kind]} index (CSV)\n\nid,title,tags,status\n`);
    setIndexRow(index, a.id, `${a.id},${csv(a.title)},${csv(a.tags.join(', '))},${a.status}`);
  }
  if (plan.newTags.length) {
    const tagsFile = path.join(root, 'docs/skills/tags.md');
    const body = readFileSync(tagsFile, 'utf8');
    appendFileSync(tagsFile, `${body.endsWith('\n') ? '' : '\n'}${plan.newTags.map((t) => `${t} — introduced by go-getter pack ${plan.generatedBy}`).join('\n')}\n`);
  }
  for (const f of plan.files) {
    mkdirSync(path.dirname(path.join(root, f.path)), { recursive: true });
    writeFileSync(path.join(root, f.path), f.content);
  }
  return [...plan.artifacts.map((a) => a.path), ...plan.files.map((f) => f.path), ...(plan.newTags.length ? ['docs/skills/tags.md'] : [])];
}
