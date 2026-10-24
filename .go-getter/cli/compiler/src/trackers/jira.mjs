// The Jira tracker (decision 0117): reads an issue's state over the REST API with Node's own fetch (no dependency) for the
// overlay in overlay.mjs. Credentials come from environment variables the project names in its tracker answers; their values
// are never written, printed or recorded, and no message here contains one. Everything an issue returns is untrusted (0119).
//
// A Jira status is read by its status category, not its name: `new` is open, `indeterminate` is in progress, `done` is done.
// Configuration, from the adopted tracker pack's decisions (see `jiraConfig`):
//   { site, 'email-env', 'token-env', auth?: 'basic' | 'bearer', 'done-transition'? }
// `site` is the Jira base URL (https; http only to a loopback address, for tests); `email-env` and `token-env` name the
// variables holding the account email and API token (`bearer` sends a personal access token and needs no email).
import { adoptedData } from '../governance.mjs';
import { parseRef } from './refs.mjs';
import { fileSource } from './file-source.mjs';
import { overlay } from './overlay.mjs';
import { ok } from './worksource.mjs';

const TIMEOUT_MS = 20_000;
const CONCURRENCY = 4;
const ENV_NAME = /^[A-Za-z_][A-Za-z0-9_]{0,63}$/;
const LOOPBACK = new Set(['127.0.0.1', 'localhost', '[::1]']);
export const DEFAULT_EMAIL_ENV = 'JIRA_EMAIL';
export const DEFAULT_TOKEN_ENV = 'JIRA_API_TOKEN';

// A problem whose message is safe to show (it names a variable or a setting, never a value).
const problem = (message) => Object.assign(new Error(message), { safe: true });

// The tracker pack records each Jira setting as its own decision (`go-getter.tracker-jira-<setting>`); null when the project
// has no Jira site answer at all. An empty answer means not set.
export function jiraConfig(project) {
  const site = adoptedData(project, 'tracker-jira-site');
  if (site === undefined) return null;
  const get = (setting) => {
    const v = adoptedData(project, `tracker-jira-${setting}`);
    return v === undefined || v === '' ? undefined : v;
  };
  return { site, auth: get('auth'), 'email-env': get('email-env'), 'token-env': get('token-env'), project: get('project'), 'issue-type': get('issue-type'), 'done-transition': get('done-transition') };
}

// The validated site, headers builder inputs and names; throws a safe problem when the configuration cannot be used.
export function checkConfig(config, env = process.env) {
  if (!config) throw problem('Jira is not configured: answer the tracker pack with jira');
  if (!config.site) throw problem('the Jira site is not set: answer jira-site in the tracker pack');
  let site;
  try {
    site = new URL(String(config.site));
  } catch {
    throw problem('the Jira site is not a URL');
  }
  if (site.username || site.password || site.search || site.hash) throw problem('the Jira site must be a plain URL');
  if (site.protocol !== 'https:' && !(site.protocol === 'http:' && LOOPBACK.has(site.hostname))) throw problem('the Jira site must be an https URL');
  const auth = config.auth === 'bearer' ? 'bearer' : 'basic';
  const tokenEnv = String(config['token-env'] ?? DEFAULT_TOKEN_ENV);
  const emailEnv = String(config['email-env'] ?? DEFAULT_EMAIL_ENV);
  for (const name of auth === 'bearer' ? [tokenEnv] : [emailEnv, tokenEnv]) {
    if (!ENV_NAME.test(name)) throw problem(`"${name.slice(0, 40)}" is not an environment variable name`);
    if (!env[name]) throw problem(`the environment variable ${name} is not set`);
  }
  const header = auth === 'bearer' ? `Bearer ${env[tokenEnv]}` : `Basic ${Buffer.from(`${env[emailEnv]}:${env[tokenEnv]}`).toString('base64')}`;
  return { base: `${site.origin}${site.pathname.replace(/\/+$/, '')}`, header };
}

const STATE_OF = { new: 'open', indeterminate: 'in progress', done: 'done' };

// One issue: { state, title }, or null when it does not exist. Throws a safe problem for refused credentials, otherwise the
// network or HTTP error (not safe: its text is not shown).
export async function fetchIssue({ base, header }, issueKey, fetchImpl = fetch) {
  const res = await fetchImpl(`${base}/rest/api/2/issue/${encodeURIComponent(issueKey)}?fields=summary,status`, {
    headers: { Accept: 'application/json', Authorization: header },
    redirect: 'error',
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (res.status === 404) return null;
  if (res.status === 401 || res.status === 403) throw problem(`Jira refused the credentials (HTTP ${res.status})`);
  if (!res.ok) throw new Error(`Jira answered HTTP ${res.status}`);
  const body = await res.json();
  const category = body?.fields?.status?.statusCategory?.['key'];
  if (!(category in STATE_OF) || typeof body.fields.summary !== 'string') throw new Error('Jira answered with an unexpected shape');
  return { state: STATE_OF[category], title: body.fields.summary };
}

// The adapter the overlay reads Jira through. `fetchImpl` is for tests that do not use a server.
export function jiraAdapter(project, { config = jiraConfig(project), env = process.env, fetchImpl } = {}) {
  return {
    id: 'jira',
    refOf(step) {
      const ref = step.issue === undefined ? null : parseRef(step.issue);
      return ref?.tracker === 'jira' ? { ref, cacheKey: `jira:${ref.key}`, label: ref.text } : null;
    },
    async fetch(items) {
      const settings = checkConfig(config, env);
      const out = new Map();
      const queue = [...items];
      let last;
      const worker = async () => {
        for (let item = queue.shift(); item; item = queue.shift()) {
          try {
            out.set(item.cacheKey, await fetchIssue(settings, item.ref.key, fetchImpl));
          } catch (err) {
            if (err.safe) throw err; // refused credentials fail every issue alike
            last = err; // one issue that cannot be read leaves only that step stale
          }
        }
      };
      await Promise.all(Array.from({ length: Math.min(CONCURRENCY, queue.length) }, worker));
      if (!out.size && last) throw last;
      return out;
    },
  };
}

// The file WorkSource with each Jira-issue step's state read from its issue; the rules are those of the GitHub source
// (a step with no issue stays file-driven, a mismatch is reported, a failure falls back to the cache, marked stale).
export function jiraSource(file, { project, name = file, now = () => new Date(), config, env, fetchImpl } = {}) {
  const base = fileSource(file, { name });
  const adapter = jiraAdapter(project, { config, env, fetchImpl });
  return {
    id: 'jira',
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
