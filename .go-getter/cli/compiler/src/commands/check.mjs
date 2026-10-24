// go-getter check [--project <dir>] [--guardrail <id>] [--stage pre-commit|pre-push|ci]: run the tier-3 guardrail checks of
// a stage (an entry without `stages` runs before a push; no stage, or ci, runs every entry).
import path from 'node:path';
import { readFileSync } from 'node:fs';
import { runTier3, STAGES } from '../enforce.mjs';

// Under a pre-push hook git writes one `<local ref> <local sha> <remote ref> <remote sha>` line per ref to stdin. Returns the
// remote refs, or undefined when there are none to read (a terminal, a closed stdin or no refs): checks then fall back to
// the checked-out branch.
function readPushRefs() {
  if (process.stdin.isTTY) return undefined;
  let text = '';
  try {
    text = readFileSync(0, 'utf8');
  } catch {
    return undefined;
  }
  const refs = text.split('\n').map((l) => l.trim().split(/\s+/)[2]).filter(Boolean);
  return refs.length ? refs : undefined;
}

export default async function checkAll({ args }) {
  let project = process.cwd();
  let onlyGuardrail;
  let stage;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--project') project = path.resolve(args[++i]);
    else if (args[i] === '--guardrail') onlyGuardrail = args[++i];
    else if (args[i] === '--stage') stage = args[++i];
  }
  if (stage !== undefined && !STAGES.includes(stage)) {
    console.error(`usage: go-getter check [--project <dir>] [--guardrail <id>] [--stage ${STAGES.join('|')}]`);
    return 2;
  }
  const results = await runTier3(project, { onlyGuardrail, stage, pushRefs: stage === 'pre-push' ? readPushRefs() : undefined });
  const failed = results.filter((r) => !r.ok);
  for (const r of results) console.log(`${r.ok ? 'ok  ' : 'FAIL'} ${r.guardrail}${r.message ? ` — ${r.message}` : ''}`);
  console.log(`go-getter check: ${results.length - failed.length}/${results.length} passed`);
  return failed.length ? 1 : 0;
}
