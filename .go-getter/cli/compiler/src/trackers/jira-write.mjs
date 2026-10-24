// The Jira write calls of `go-getter plan issue` (decision 0117): create an issue, comment, close. The verbs, their dry runs,
// the answer that gates them and the text checks are in write.mjs; this module only speaks to Jira's REST API with the
// credentials of `checkConfig` (jira.mjs), and no message here carries a response body or a credential.
//
// Closing takes the transition into the done status category: the one transition, or the one the configuration names
// (`done-transition`, by name or id); with none or several and no name it refuses and lists the names.
import { checkConfig } from './jira.mjs';

const TIMEOUT_MS = 20_000;
const safe = (message) => Object.assign(new Error(message), { safe: true });

export async function jiraRequest({ base, header }, method, apiPath, body, fetchImpl = fetch) {
  const res = await fetchImpl(`${base}/rest/api/2${apiPath}`, {
    method,
    headers: { Accept: 'application/json', Authorization: header, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    redirect: 'error',
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (res.status === 401 || res.status === 403) throw safe(`Jira refused the credentials (HTTP ${res.status})`);
  if (res.status === 404) throw safe('Jira has no such issue or project, or the account cannot see it (HTTP 404)');
  if (!res.ok) throw safe(`Jira rejected the request (HTTP ${res.status})`);
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

// The Jira project key and issue type that `create` uses, from the configuration.
export function createSettings(config) {
  const project = String(config?.project ?? '');
  if (!/^[A-Z][A-Z0-9_]+$/.test(project)) throw safe('the tracker answers name no Jira project key (project) to create issues in');
  return { project, issueType: String(config['issue-type'] ?? 'Task') };
}

export async function createIssue(config, env, { summary, description }, fetchImpl) {
  const settings = checkConfig(config, env);
  const { project, issueType } = createSettings(config);
  const made = await jiraRequest(settings, 'POST', '/issue', { fields: { project: { key: project }, summary, description, issuetype: { name: issueType } } }, fetchImpl);
  if (typeof made?.['key'] !== 'string' || !new RegExp(`^${project}-[1-9][0-9]*$`).test(made['key'])) throw safe('Jira created an issue but answered with no usable issue key, so the step was not updated');
  return made['key'];
}

export async function commentIssue(config, env, issueKey, text, fetchImpl) {
  await jiraRequest(checkConfig(config, env), 'POST', `/issue/${encodeURIComponent(issueKey)}/comment`, { body: text }, fetchImpl);
}

// The transition that closes the issue, or a safe problem naming why none was chosen.
export function chooseTransition(transitions, named) {
  const done = (transitions ?? []).filter((t) => t?.to?.statusCategory?.['key'] === 'done');
  if (named) {
    const hit = done.filter((t) => t.id === String(named) || String(t.name).toLowerCase() === String(named).toLowerCase());
    if (hit.length === 1) return hit[0];
    throw safe(`the configured done transition "${String(named).slice(0, 60)}" is not one of the transitions into done (${done.map((t) => `${t.name} (${t.id})`).join(', ') || 'none'})`);
  }
  if (done.length === 1) return done[0];
  if (!done.length) throw safe('the issue has no transition into the done category from its current status');
  throw safe(`several transitions lead to done (${done.map((t) => `${t.name} (${t.id})`).join(', ')}); name one as done-transition in the tracker answers`);
}

export async function closeIssue(config, env, issueKey, fetchImpl) {
  const settings = checkConfig(config, env);
  const listed = await jiraRequest(settings, 'GET', `/issue/${encodeURIComponent(issueKey)}/transitions`, undefined, fetchImpl);
  const chosen = chooseTransition(listed?.transitions, config['done-transition']);
  await jiraRequest(settings, 'POST', `/issue/${encodeURIComponent(issueKey)}/transitions`, { transition: { id: chosen.id } }, fetchImpl);
  return chosen.name;
}
