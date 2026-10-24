// go-getter hook pre-tool --host <id> [--project <dir>]: tier-2 runtime called by host hooks; reads the tool call on stdin.
// go-getter hook session-start --host <id>: prints the vendored capture/lint nudges (never blocks).
// pre-tool also routes delegations to a role (cost-routing pack): it sets the delegated model, or denies when no model is eligible;
// and wraps a host watcher command in `go-getter watch` (context pack, decision 0070).
// go-getter hook stop --host <id>: verification gate; blocks "done" while the adopted checks fail (bounded, then a human).
// go-getter hook post-tool --host <id>: redacts secrets and masks PII in the tool result where the host can replace it.
// go-getter hook session-end --host <id>: deletes the session's pseudonym map (best effort; a 24-hour sweep backs it up).
import path from 'node:path';
import { readFileSync } from 'node:fs';
import { evaluatePreTool, respond, sessionNudges, hookRecord, evaluatePostTool, respondPostTool, evaluateSessionEnd } from '../hook.mjs';
import { recordQuietly } from '../telemetry/record.mjs';
import { evaluateStop, respondStop } from '../verify.mjs';
import { routeDelegation, routeRecord, respondRewrite } from '../routing/delegate.mjs';
import { wrapWatch } from '../watch.mjs';
import { recordHostSpend } from '../spend/index.mjs';

export default async function hookCommand({ root, args }) {
  const [event, ...rest] = args;
  let host;
  let project = process.cwd();
  for (let i = 0; i < rest.length; i++) {
    if (rest[i] === '--host') host = rest[++i];
    else if (rest[i] === '--project') project = path.resolve(rest[++i]);
  }
  if (event === 'session-start') {
    // The payload carries metadata only here (model, effort, resume token and cost estimates); a terminal stdin is skipped.
    let payload = {};
    try {
      if (!process.stdin.isTTY) payload = JSON.parse(readFileSync(0, 'utf8') || '{}');
    } catch {
      // no or malformed payload: record without it
    }
    recordQuietly(project, hookRecord('session-start', host, payload));
    const text = sessionNudges(root, project);
    if (text) process.stdout.write(`${text}\n`);
    return 0;
  }
  if (!['pre-tool', 'post-tool', 'stop', 'session-end'].includes(event) || !host) {
    console.error('usage: go-getter hook <pre-tool|post-tool|stop|session-start|session-end> --host <id>');
    return 0; // never block on a misconfigured hook
  }
  let payload = {};
  try {
    payload = JSON.parse(readFileSync(0, 'utf8') || '{}');
  } catch {
    return 0;
  }
  const dir = payload.cwd ? path.resolve(payload.cwd) : project;
  if (event === 'session-end') {
    recordHostSpend(dir, host, payload);
    try {
      evaluateSessionEnd(dir, payload);
    } catch {
      // cleanup is best effort: the 24-hour sweep catches what this misses
    }
    return 0;
  }
  if (event === 'post-tool') {
    let result;
    try {
      result = evaluatePostTool(dir, payload);
    } catch {
      return 0; // a broken hook fails open (decision 0019)
    }
    recordQuietly(dir, hookRecord('post-tool', host, payload, undefined, result.redactions, result.masked));
    recordHostSpend(dir, host, payload);
    const out = respondPostTool(host, result);
    if (out.stdout) process.stdout.write(out.stdout);
    return out.code;
  }
  if (event === 'stop') {
    recordHostSpend(dir, host, payload);
    let out;
    try {
      out = respondStop(host, await evaluateStop(dir, payload, { host }));
    } catch {
      return 0; // a broken gate must never trap a session
    }
    if (out.stdout) process.stdout.write(out.stdout);
    if (out.stderr) process.stderr.write(`${out.stderr}\n`);
    return out.code;
  }
  const decision = evaluatePreTool(dir, payload, host);
  recordQuietly(dir, hookRecord('pre-tool', host, payload, decision));
  if (!decision.deny) {
    let routed = null;
    try {
      routed = routeDelegation(dir, host, payload);
    } catch {
      // routing is an optimisation: a failure leaves the delegation as it was
    }
    if (routed?.route) recordQuietly(dir, routeRecord(host, routed.route, routed.handoffTokens));
    if (routed?.deny) {
      decision.deny = true;
      decision.reason = routed.reason;
    } else if (routed?.advisory) {
      process.stderr.write(`${routed.advisory}\n`);
    } else if (routed?.rewrite) {
      const rewritten = respondRewrite(host, routed.rewrite);
      process.stdout.write(rewritten.stdout);
      return rewritten.code;
    }
    let watched = null;
    try {
      watched = wrapWatch(project, host, payload);
    } catch {
      // a failed wrap leaves the watch as it was
    }
    if (!decision.deny && watched) {
      const rewritten = respondRewrite(host, watched.rewrite);
      process.stdout.write(rewritten.stdout);
      return rewritten.code;
    }
  }
  const out = respond(host, decision);
  if (out.stdout) process.stdout.write(out.stdout);
  if (out.stderr) process.stderr.write(`${out.stderr}\n`);
  return out.code;
}
