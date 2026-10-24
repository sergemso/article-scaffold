// Guardrail guardrails-declare-enforcement: every guardrail carries go-getter.enforcement;
// tier 2/3 entries name a `run`; tier-1-only guardrails say "advisory" in their body.
import { readArtifacts } from '../artifacts.mjs';

export function guardrailProblems(guardrails) {
  const problems = [];
  for (const g of guardrails) {
    const entries = g.data?.['go-getter']?.enforcement;
    if (!Array.isArray(entries) || entries.length === 0) {
      problems.push(`${g.file}: missing go-getter.enforcement`);
      continue;
    }
    entries.forEach((e, i) => {
      if (![1, 2, 3].includes(e?.tier)) problems.push(`${g.file}: enforcement[${i}].tier must be 1, 2 or 3`);
      if (typeof e?.check !== 'string' || !e.check.trim()) problems.push(`${g.file}: enforcement[${i}].check is required`);
      if ([2, 3].includes(e?.tier) && (typeof e.run !== 'string' || !e.run.trim())) problems.push(`${g.file}: enforcement[${i}] tier ${e.tier} needs run`);
      if (e?.stages !== undefined) {
        const ok = Array.isArray(e.stages) && e.stages.length > 0 && e.stages.every((x) => ['pre-commit', 'pre-push'].includes(x));
        if (e.tier !== 3 || !ok) problems.push(`${g.file}: enforcement[${i}].stages is for tier 3 and lists pre-commit and/or pre-push`);
      }
    });
    if (entries.every((e) => e?.tier === 1) && !/advisory/i.test(g.body)) {
      problems.push(`${g.file}: tier-1-only guardrail must say it is advisory`);
    }
  }
  return problems;
}

export default function checkGuardrails({ root }) {
  const problems = guardrailProblems(readArtifacts(root, ['guardrails']));
  if (problems.length) {
    console.error('check guardrails:');
    for (const p of problems) console.error(`  ${p}`);
    return 1;
  }
  console.log('check guardrails: ok');
  return 0;
}
