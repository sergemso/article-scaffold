// The GitHub tracker (decision 0117): reads an issue's state through `gh` for the overlay in overlay.mjs. Reading only; the
// write verbs are in write.mjs. Everything an issue returns is untrusted text (0119).
import { execFile, execFileSync } from 'node:child_process';
import { cleanGitEnv } from '../git-env.mjs';
import { parseRef } from './refs.mjs';
import { fileSource } from './file-source.mjs';
import { overlay, cleanTitle } from './overlay.mjs';
import { ok } from './worksource.mjs';

export { cleanTitle };

const GH_TIMEOUT_MS = 20_000;
const LIST_AT = 4; // from this many issues in one repository a single list call replaces one view each
const LIST_LIMIT = 1000;
const FIELDS = 'number,title,state,stateReason';

// `owner/repo` of the project's origin when it is on GitHub, else null.
export function originRepo(project) {
  try {
    const url = execFileSync('git', ['remote', 'get-url', 'origin'], { cwd: project, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], env: cleanGitEnv(process.env) }).trim();
    const m = /github\.com[:/]([A-Za-z0-9-]+)\/([A-Za-z0-9._-]+?)(?:\.git)?\/?$/.exec(url);
    return m ? `${m[1]}/${m[2]}` : null;
  } catch {
    return null;
  }
}

// GitHub says open or closed with a reason; a plan step is done when the issue closed as completed, moved out of the plan
// when it closed as not planned, and otherwise still open (an open issue cannot say pending from in progress).
export function issueStateOf({ state, stateReason }) {
  if (String(state).toUpperCase() !== 'CLOSED') return 'open';
  return String(stateReason ?? '').toUpperCase() === 'NOT_PLANNED' ? 'moved' : 'done';
}

// Runs gh without a shell; `input` (when given) is written to its standard input. Rejects with the process error.
export function gh(args, project, input) {
  return new Promise((resolve, reject) => {
    const child = execFile('gh', args, { cwd: project, timeout: GH_TIMEOUT_MS, maxBuffer: 16 * 1024 * 1024, env: cleanGitEnv(process.env) }, (err, stdout, stderr) =>
      err ? reject(Object.assign(err, { stderr: String(stderr ?? '') })) : resolve(stdout));
    if (input !== undefined) child.stdin.end(input);
  });
}

// Map of `owner/repo#number` to the issue gh returned, or null for one that does not exist; throws when gh cannot be reached.
// `refs` are parsed GitHub references; the repository of one written without it is origin's.
export async function fetchIssues(project, refs, origin = originRepo(project)) {
  const wanted = new Map();
  for (const ref of refs) {
    const repo = ref.repo ?? origin;
    if (!repo) continue;
    if (!wanted.has(repo)) wanted.set(repo, new Set());
    wanted.get(repo).add(ref.key);
  }
  const found = new Map();
  for (const [repo, numbers] of wanted) {
    if (numbers.size >= LIST_AT) {
      for (const issue of JSON.parse(await gh(['issue', 'list', '--repo', repo, '--state', 'all', '--limit', String(LIST_LIMIT), '--json', FIELDS], project))) {
        if (numbers.has(String(issue.number))) found.set(`${repo}#${issue.number}`, issue);
      }
    }
    await Promise.all([...numbers].filter((n) => !found.has(`${repo}#${n}`)).map(async (n) => {
      try {
        found.set(`${repo}#${n}`, JSON.parse(await gh(['issue', 'view', n, '--repo', repo, '--json', FIELDS], project)));
      } catch (err) {
        if (/could not resolve|not found/i.test(String(err.stderr ?? err.message))) found.set(`${repo}#${n}`, null);
        else throw err;
      }
    }));
  }
  return found;
}

// The adapter the overlay reads GitHub through.
export function githubAdapter(project) {
  const origin = originRepo(project);
  return {
    id: 'github',
    refOf(step) {
      const ref = step.issue === undefined ? null : parseRef(step.issue);
      if (ref?.tracker !== 'github') return null;
      const repo = ref.repo ?? origin;
      return { ref, cacheKey: repo ? `${repo}#${ref.key}` : null, label: ref.text };
    },
    async fetch(items) {
      const issues = await fetchIssues(project, items.map((i) => i.ref), origin);
      return new Map([...issues].map(([key, issue]) => [key, issue ? { state: issueStateOf(issue), title: issue.title } : null]));
    },
  };
}

// The file WorkSource with each GitHub-issue step's state read from its issue (decision 0117): the issue decides, a step with
// no issue stays file-driven, and a disagreement is reported on the step (`mismatch`), never changed. When `gh` fails the last
// state read is used and marked stale; with none, the step keeps its file state and is marked stale and unknown.
export function githubSource(file, { project, name = file, now = () => new Date() } = {}) {
  const base = fileSource(file, { name });
  const adapter = githubAdapter(project);
  return {
    id: 'github',
    ops: base.ops,
    async handle(op, args) {
      const answer = await base.handle(op, args);
      if (!answer.ok) return answer;
      if (op === 'list') return ok({ steps: await overlay({ project, steps: answer.result.steps, adapter, now }) });
      if (answer.result.step) return ok({ step: (await overlay({ project, steps: [answer.result.step], adapter, now }))[0] });
      return answer;
    },
  };
}
