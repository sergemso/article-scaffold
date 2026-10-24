// The WorkSource contract (decisions 0117, 0118, 0119): where `plan` gets its steps. A source is `{ id, ops, handle }`;
// the core reaches it only through `callSource`, which holds the rules a helper process would be held to later: a call
// and its answer are plain JSON data (no callbacks, no shared state), an op the source does not list is `unsupported`,
// and nothing a source returns is run as a command.
//
// Ops: list {} -> { steps }; get { id } -> { step }; create { id?, title, class?, needs?, doneWhen? } -> { step } (id is
// required where a source cannot assign one, as the file source cannot; a tracker assigns its own);
// setState { id, state } -> { step }; comment { id, text } -> {}.
// A step is plain data: { id, title, state, parallel, class, needs, fields, check?, doneWhen?, issue?, effort?, tier?, data? }.
export const OPS = ['list', 'get', 'create', 'setState', 'comment'];
export const STATES = ['pending', 'in progress', 'done', 'blocked', 'moved'];
export const ERROR_CODES = ['unknown-op', 'unsupported', 'invalid-args', 'unknown-step', 'invalid-plan', 'unavailable'];

// What an answer must hold for its op; anything else is `unavailable`, since a source's data is untrusted.
export function isStep(s) {
  return Boolean(s) && typeof s === 'object' && typeof s.id === 'string' && s.id !== '' && typeof s.title === 'string' && STATES.includes(s.state) && typeof s.parallel === 'boolean' &&
    typeof s.class === 'string' && Array.isArray(s.needs) && s.needs.every((n) => typeof n === 'string') && Boolean(s.fields) && typeof s.fields === 'object' && !Array.isArray(s.fields);
}
const RESULT_OK = {
  list: (r) => Array.isArray(r.steps) && r.steps.every(isStep),
  get: (r) => isStep(r.step),
  create: (r) => isStep(r.step),
  setState: (r) => isStep(r.step),
  comment: () => true,
};

export const ok = (result = {}) => ({ ok: true, result });
export const fail = (code, message, extra = {}) => ({ ok: false, error: { code, message, ...extra } });

// True when the value is JSON data: null, booleans, finite numbers, strings, arrays and plain objects of those. A Date,
// a function, undefined, a class instance or a cycle is not, since it would not cross a process boundary unchanged.
export function isPlainData(value, seen = new Set()) {
  if (value === null || ['string', 'boolean'].includes(typeof value)) return true;
  if (typeof value === 'number') return Number.isFinite(value);
  if (typeof value !== 'object' || seen.has(value)) return false;
  const proto = Object.getPrototypeOf(value);
  if (!Array.isArray(value) && proto !== Object.prototype && proto !== null) return false;
  seen.add(value);
  const inner = Object.values(value).every((v) => isPlainData(v, seen));
  seen.delete(value);
  return inner;
}

// The one entry the core uses. Never throws: an error a source raises is `unavailable`.
export async function callSource(source, op, args = {}) {
  if (!OPS.includes(op)) return fail('unknown-op', `unknown op "${op}"`);
  if (!source.ops.includes(op)) return fail('unsupported', `source "${source.id}" does not support ${op}`);
  if (!args || typeof args !== 'object' || Array.isArray(args) || !isPlainData(args)) return fail('invalid-args', `${op} takes a plain object`);
  let answer;
  try {
    answer = await source.handle(op, JSON.parse(JSON.stringify(args)));
  } catch (err) {
    return fail('unavailable', String(err?.message ?? err).split('\n')[0]);
  }
  if (!answer || typeof answer.ok !== 'boolean' || !isPlainData(answer)) return fail('unavailable', `source "${source.id}" answered ${op} with data that is not plain JSON`);
  if (answer.ok && !(answer.result && typeof answer.result === 'object' && RESULT_OK[op](answer.result))) return fail('unavailable', `source "${source.id}" answered ${op} with a result of the wrong shape`);
  if (!answer.ok && !ERROR_CODES.includes(answer.error?.code)) return fail('unavailable', `source "${source.id}" answered ${op} with an unknown error code`);
  return answer;
}
