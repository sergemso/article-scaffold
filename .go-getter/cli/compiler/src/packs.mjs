// Practice packs (decisions 0008, 0022): loading, schema + semantic validation, enforcement `run` grammar.
import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs';
import path from 'node:path';
import { validate } from './schema.mjs';

// Outputs of a text/list question sit under this key and apply whatever the answer is.
export const ANY_ANSWER = '*';

const compareVersions = (a, b) => {
  const [x, y] = [a, b].map((v) => v.split('.').map(Number));
  return x[0] - y[0] || x[1] - y[1] || x[2] - y[2];
};
const PLACEHOLDER = /\{\{\s*([a-z]+)((?:\.[A-Za-z0-9_-]+)*)\s*\}\}/g;

export function loadPackSchema(root) {
  return JSON.parse(readFileSync(path.join(root, 'compiler/schemas/pack.schema.json'), 'utf8'));
}

export function loadPack(file) {
  return JSON.parse(readFileSync(file, 'utf8'));
}

export function listPackFiles(root) {
  const dir = path.join(root, 'src/packs');
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((n) => statSync(path.join(dir, n)).isDirectory())
    .sort()
    .map((n) => path.join(dir, n, 'pack.json'));
}

// "builtin:<id> key=value key=\"quoted value\"" or a shell command.
export function parseRun(run) {
  if (!run.startsWith('builtin:')) return { kind: 'command', command: run };
  const [head, ...rest] = run.slice('builtin:'.length).match(/(?:[^\s"]+|"[^"]*")+/g) ?? [];
  if (!head || !/^[a-z0-9]+(-[a-z0-9]+)*$/.test(head)) throw new Error(`invalid builtin check id in "${run}"`);
  const args = {};
  for (const token of rest) {
    const m = /^([a-zA-Z0-9_-]+)=(.*)$/.exec(token);
    if (!m) throw new Error(`invalid argument "${token}" in "${run}" (expected key=value)`);
    args[m[1]] = m[2].replace(/^"(.*)"$/, '$1');
  }
  return { kind: 'builtin', id: head, args };
}

function placeholdersIn(value, found = []) {
  if (typeof value === 'string') for (const m of value.matchAll(PLACEHOLDER)) found.push({ ns: m[1], parts: m[2].split('.').filter(Boolean) });
  else if (Array.isArray(value)) value.forEach((v) => placeholdersIn(v, found));
  else if (value && typeof value === 'object') Object.values(value).forEach((v) => placeholdersIn(v, found));
  return found;
}

export function validatePack(schema, pack, { dirName, knownPacks } = {}) {
  const errors = validate(schema, pack);
  if (errors.length) return errors;
  if (dirName && pack.id !== dirName) errors.push(`$.id: "${pack.id}" must equal its directory "${dirName}"`);
  if (pack.family === 'harness' && !pack.components?.length) errors.push('$.components: harness packs must list the components they cover');
  if (pack.replaces) {
    const own = new Set(pack.questions.map((q) => q.id));
    if (pack.replaces.pack === pack.id) errors.push('$.replaces.pack: a pack cannot replace itself');
    for (const q of pack.replaces.questions) if (!own.has(q)) errors.push(`$.replaces.questions: "${q}" is not a question of this pack`);
  }
  for (const r of pack.requires ?? []) if (knownPacks && !knownPacks.has(r)) errors.push(`$.requires: unknown pack "${r}"`);

  const questions = new Map();
  pack.questions.forEach((q, i) => {
    const at = `$.questions[${i}]`;
    if (questions.has(q.id)) errors.push(`${at}.id: duplicate question "${q.id}"`);
    const type = q.type ?? 'choice';
    if (type === 'choice') {
      if (!q.options) errors.push(`${at}.options: choice questions need options`);
      else {
        const optionIds = q.options.map((o) => o.id);
        if (new Set(optionIds).size !== optionIds.length) errors.push(`${at}.options: duplicate option ids`);
        if (q.options.filter((o) => o.recommended).length !== 1) errors.push(`${at}.options: exactly one option must be recommended`);
      }
      const current = (q.options ?? []).map((o) => o.id);
      for (const [oldId, newId] of Object.entries(q.renamed ?? {})) {
        if (current.includes(oldId)) errors.push(`${at}.renamed.${oldId}: "${oldId}" is still an option of "${q.id}"`);
        if (!current.includes(newId)) errors.push(`${at}.renamed.${oldId}: "${newId}" is not an option of "${q.id}"`);
      }
      for (const k of ['pattern', 'default']) if (q[k] !== undefined) errors.push(`${at}.${k}: only text and list questions take "${k}"`);
    } else {
      if (q.renamed) errors.push(`${at}.renamed: only choice questions rename options`);
      if (q.options) errors.push(`${at}.options: ${type} questions take no options`);
      if (q.default === undefined && !q.detect) errors.push(`${at}: ${type} questions need a default or a detect key`);
      if (type === 'text' && Array.isArray(q.default)) errors.push(`${at}.default: text questions take a string default`);
      if (type === 'list' && q.default !== undefined && !Array.isArray(q.default)) errors.push(`${at}.default: list questions take an array default`);
      if (q.pattern) {
        try {
          const re = new RegExp(q.pattern);
          for (const d of [].concat(q.default ?? [])) if (!re.test(d)) errors.push(`${at}.default: "${d}" does not match pattern`);
        } catch {
          errors.push(`${at}.pattern: not a valid regular expression`);
        }
      }
    }
    if (q.since) {
      if (compareVersions(q.since, pack.version) > 0) errors.push(`${at}.since: "${q.since}" is later than the pack version ${pack.version}`);
      if (type !== 'choice' && q.default === undefined) errors.push(`${at}: a question with "since" needs a default for older answer files`);
    }
    if (q.when) {
      const prior = questions.get(q.when.question);
      if (!prior) errors.push(`${at}.when.question: "${q.when.question}" must be an earlier question`);
      else if (prior.options) {
        for (const o of q.when.in) if (!prior.options.some((p) => p.id === o)) errors.push(`${at}.when.in: "${o}" is not an option of "${q.when.question}"`);
      }
    }
    questions.set(q.id, q);
  });

  for (const [qid, byOption] of Object.entries(pack.outputs)) {
    const q = questions.get(qid);
    if (!q) {
      errors.push(`$.outputs.${qid}: no such question`);
      continue;
    }
    for (const [oid, out] of Object.entries(byOption)) {
      const at = `$.outputs.${qid}.${oid}`;
      if (q.options ? !q.options.some((o) => o.id === oid) : oid !== ANY_ANSWER) {
        errors.push(q.options ? `${at}: "${oid}" is not an option of "${qid}"` : `${at}: ${q.type} questions use the key "${ANY_ANSWER}"`);
      }
      (out.guardrails ?? []).forEach((g, i) => {
        if (!g.enforcement?.length) errors.push(`${at}.guardrails[${i}]: guardrails need enforcement entries`);
        (g.enforcement ?? []).forEach((e, j) => {
          if (e.tier >= 2 && !e.run) errors.push(`${at}.guardrails[${i}].enforcement[${j}]: tier ${e.tier} needs run`);
          if (e.run) {
            try {
              parseRun(e.run);
            } catch (err) {
              errors.push(`${at}.guardrails[${i}].enforcement[${j}].run: ${err.message}`);
            }
          }
        });
      });
    }
  }

  for (const { ns, parts } of placeholdersIn(pack.outputs)) {
    const label = `{{${[ns, ...parts].join('.')}}}`;
    if ((ns === 'answer' || ns === 'label') && !questions.has(parts[0])) errors.push(`placeholder ${label}: unknown question`);
    else if (ns === 'label' && !questions.get(parts[0]).options) errors.push(`placeholder ${label}: only choice questions have labels`);
    else if (ns === 'id' && (parts[0] !== 'decision' || !questions.has(parts[1]))) errors.push(`placeholder ${label}: expected {{id.decision.<question>}}`);
    else if (ns === 'pack' && !['id', 'version'].includes(parts[0])) errors.push(`placeholder ${label}: expected pack.id or pack.version`);
    else if (!['answer', 'label', 'id', 'pack', 'detect'].includes(ns)) errors.push(`placeholder ${label}: unknown namespace`);
  }
  return errors;
}

export function validateAllPacks(root, files = listPackFiles(root)) {
  const schema = loadPackSchema(root);
  const packs = files.map((f) => ({ file: f, pack: loadPack(f) }));
  const knownPacks = new Set(packs.map((p) => p.pack.id));
  return packs.flatMap(({ file, pack }) =>
    validatePack(schema, pack, { dirName: path.basename(path.dirname(file)), knownPacks }).map((e) => `${path.relative(root, file)}: ${e}`),
  );
}

// The packs that took over a retired pack (`replaces`, decision 0132): ids, for a message that says where it went.
export function successorsOf(root, retiredId) {
  return listPackFiles(root).map((file) => loadPack(file)).filter((p) => p.replaces?.pack === retiredId).map((p) => p.id);
}

// "<id> was split into a, b and c; ..." when `id` is a retired pack, else null.
export function retiredPackNote(root, id) {
  const now = id ? successorsOf(root, id) : [];
  return now.length ? `pack "${id}" was split into ${now.join(', ')}; run this command for each with the same answers file (answers a pack does not ask are ignored)` : null;
}
