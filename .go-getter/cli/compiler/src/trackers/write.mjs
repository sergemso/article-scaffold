// The write verbs of `go-getter plan issue` (decision 0117): create an issue from a plan step, comment on a step's issue, close
// it, on GitHub (through `gh`) or Jira (over REST). Writing is outward-facing, so each verb has a dry run that sends nothing,
// refuses when the project's answer is `off` (or no tracker pack is adopted), and checks what it would send for secrets and
// personal data. Only the verb and its outcome reach telemetry, never issue text. These are go-getter's own verbs; a raw
// `gh issue` command stays gated by the human-approval guardrail whatever the answer is.
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { adoptedData } from '../governance.mjs';
import { recordQuietly } from '../telemetry/record.mjs';
import { findings } from '../secrets/patterns.mjs';
import { piiFindings } from '../secrets/pii.mjs';
import { parsePlan, setIssueField, stepBody } from '../plan.mjs';
import { parseRef } from './refs.mjs';
import { gh, originRepo, cleanTitle } from './github.mjs';
import { jiraConfig } from './jira.mjs';
import { createIssue, commentIssue, closeIssue, createSettings } from './jira-write.mjs';

export const VERBS = ['create', 'comment', 'close'];
export const WRITE_MODES = ['off', 'ask', 'allow'];
const REASONS = { completed: 'completed', 'not-planned': 'not planned' };
const COMMENT_MAX = 20_000;
const TITLE_MAX = 200;

// The project's answer to "may plan write to the tracker": `off` unless an adopted decision says ask or allow.
export function writeMode(project) {
  const mode = adoptedData(project, 'tracker-writes');
  return WRITE_MODES.includes(mode) ? mode : 'off';
}

// The kinds found in text that must not leave the project (secrets, emails, cards, IBANs), never the matches.
function sensitiveKinds(text) {
  return [...new Set([...findings(text).map((f) => f.kind), ...piiFindings(text).map((f) => f.kind)])];
}

const fail = (error, extra = {}) => ({ ok: false, error, ...extra });

// The request a verb would send, as plain data, or { error }. GitHub: { tracker, verb, repo, number?, title?, body?, reason? };
// Jira: { tracker, verb, project?, issueKey?, title?, body? }.
function buildRequest(verb, { project, step, planText, rel, opts }) {
  if (verb === 'create') {
    if (step.fields.Issue !== undefined) return { error: `step ${step.id} already has an issue (${step.fields.Issue})` };
    if (step.title.length > TITLE_MAX) return { error: `the step title is longer than ${TITLE_MAX} characters` };
    const body = [stepBody(planText, step), `Plan step: ${rel} step ${step.id}`].filter(Boolean).join('\n\n');
    if (adoptedData(project, 'tracker') === 'jira') {
      let settings;
      try {
        settings = createSettings(jiraConfig(project));
      } catch (err) {
        return { error: err.message };
      }
      return { tracker: 'jira', verb, project: settings.project, title: step.title, body };
    }
    const origin = originRepo(project);
    if (!origin) return { error: 'the project has no GitHub origin to create an issue in' };
    return { tracker: 'github', verb, repo: origin, title: step.title, body };
  }
  const ref = step.fields.Issue === undefined ? null : parseRef(step.fields.Issue);
  if (!ref) return { error: `step ${step.id} has no issue; run plan issue create first` };
  if (verb === 'comment') {
    const body = String(opts.text ?? '').trim();
    if (!body) return { error: 'a comment needs text (--text or --stdin)' };
    if (body.length > COMMENT_MAX) return { error: `a comment is at most ${COMMENT_MAX} characters` };
    return ref.tracker === 'jira' ? { tracker: 'jira', verb, issueKey: ref.text, body } : githubTarget(project, ref, { verb, body });
  }
  if (ref.tracker === 'jira') return { tracker: 'jira', verb, issueKey: ref.text };
  const reason = opts.reason ?? 'completed';
  if (!(reason in REASONS)) return { error: `--reason is ${Object.keys(REASONS).join(' or ')}` };
  return githubTarget(project, ref, { verb, reason: REASONS[reason] });
}

function githubTarget(project, ref, rest) {
  const repo = ref.repo ?? originRepo(project);
  if (!repo) return { error: 'the project has no GitHub origin and the issue names no repository' };
  return { tracker: 'github', repo, number: ref.key, ...rest };
}

function ghArgs(r) {
  if (r.verb === 'create') return { args: ['issue', 'create', '--repo', r.repo, '--title', r.title, '--body-file', '-'], input: r.body };
  if (r.verb === 'comment') return { args: ['issue', 'comment', r.number, '--repo', r.repo, '--body-file', '-'], input: r.body };
  return { args: ['issue', 'close', r.number, '--repo', r.repo, '--reason', r.reason] };
}

export function describeRequest(r, mode) {
  const where = r.tracker === 'jira' ? (r.issueKey ?? `the Jira project ${r.project}`) : r.number ? `${r.repo}#${r.number}` : r.repo;
  const head =
    r.verb === 'create' ? `would create an issue in ${where} (writes: ${mode})`
    : r.verb === 'comment' ? `would comment on ${where} (writes: ${mode})`
    : r.tracker === 'jira' ? `would close ${where} by its transition into done (writes: ${mode})`
    : `would close ${where} as ${r.reason} (writes: ${mode})`;
  return [head, ...(r.title ? [`title: ${r.title}`] : []), ...(r.body ? ['body:', r.body] : [])].join('\n');
}

// Sends a request; returns { reference?, message } or throws (an error with `safe` carries a message that names no secret).
async function send(project, r, jiraFetch) {
  if (r.tracker === 'jira') {
    const config = jiraConfig(project);
    if (r.verb === 'create') {
      const issueKey = await createIssue(config, process.env, { summary: r.title, description: r.body }, jiraFetch);
      return { reference: issueKey, message: `created ${issueKey} in Jira` };
    }
    if (r.verb === 'comment') {
      await commentIssue(config, process.env, r.issueKey, r.body, jiraFetch);
      return { message: `commented on ${r.issueKey}` };
    }
    const name = await closeIssue(config, process.env, r.issueKey, jiraFetch);
    return { message: `closed ${r.issueKey} by the "${name}" transition` };
  }
  const { args, input } = ghArgs(r);
  const stdout = await gh(args, project, input);
  if (r.verb === 'create') {
    const m = /\/issues\/([1-9][0-9]*)\s*$/.exec(String(stdout).trim());
    if (!m) throw Object.assign(new Error('gh created an issue but printed no issue URL, so the step was not updated'), { safe: true });
    const reference = r.repo === originRepo(project) ? `#${m[1]}` : `${r.repo}#${m[1]}`;
    return { reference, message: `created ${r.repo}#${m[1]}` };
  }
  return { message: r.verb === 'comment' ? `commented on ${r.repo}#${r.number}` : `closed ${r.repo}#${r.number} as ${r.reason}` };
}

// Runs one verb on a plan step. Returns { ok, message, request?, blocked?, dryRun? }; never throws for an expected refusal.
//   opts: { dryRun, text, reason, jiraFetch }
export async function planIssue(project, planFile, rel, verb, id, opts = {}) {
  if (!VERBS.includes(verb)) return fail(`unknown verb "${verb}" (${VERBS.join(', ')})`);
  const planText = readFileSync(planFile, 'utf8');
  const plan = parsePlan(planText, rel);
  if (plan.problems.length) return fail(`the plan does not parse: ${plan.problems[0]}`);
  const step = plan.steps.find((s) => s.id === id);
  if (!step) return fail(`no step ${id} in ${rel}`);
  const request = buildRequest(verb, { project, step, planText, rel, opts });
  if (request.error) return fail(request.error);
  const mode = writeMode(project);
  const record = (outcome) => recordQuietly(project, { event: `plan-issue:${verb}`, outcome });
  const found = sensitiveKinds([request.title, request.body].filter(Boolean).join('\n'));
  if (found.length) {
    if (!opts.dryRun) record('blocked');
    return fail(`refused: the text to send contains ${found.join(', ')}; remove it from the ${verb === 'comment' ? 'comment' : 'plan step'} first`, { blocked: true });
  }
  if (opts.dryRun) return { ok: true, dryRun: true, request, message: describeRequest(request, mode) };
  if (mode === 'off') {
    record('blocked');
    return fail('plan issue writes are off: the project has no tracker pack with writes ask or allow', { blocked: true });
  }
  let sent;
  try {
    sent = await send(project, request, opts.jiraFetch);
  } catch (err) {
    record('fail');
    const label = request.tracker === 'jira' ? 'Jira' : 'gh';
    return fail(err.safe ? String(err.message) : `${label} failed: ${cleanTitle(String(err.stderr ?? err.message).split('\n')[0])}`);
  }
  if (verb === 'create') writeFileSync(planFile, setIssueField(readFileSync(planFile, 'utf8'), step, sent.reference));
  record('pass');
  return { ok: true, request, message: verb === 'create' ? `${sent.message}; Issue: ${sent.reference} written to step ${id} in ${rel}` : sent.message };
}

export const relPlan = (project, planFile) => path.relative(project, planFile);
