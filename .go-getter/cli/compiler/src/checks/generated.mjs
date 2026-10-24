// Guardrail generated-host-files-not-hand-edited: rebuild into a temp dir and diff every generated path.
import { mkdtempSync, readFileSync, readlinkSync, lstatSync, readdirSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { compile, writeOutputs, GENERATED_ROOTS } from '../build.mjs';
import { planApply, diffApply, RUNNER } from '../apply.mjs';

function snapshot(root) {
  const entries = {};
  const visit = (rel) => {
    const abs = path.join(root, rel);
    let stat;
    try {
      stat = lstatSync(abs);
    } catch {
      return;
    }
    if (stat.isSymbolicLink()) entries[rel] = `symlink -> ${readlinkSync(abs)}`;
    else if (stat.isDirectory()) for (const n of readdirSync(abs)) visit(`${rel}/${n}`);
    else entries[rel] = readFileSync(abs).toString('base64');
  };
  GENERATED_ROOTS.forEach(visit);
  return entries;
}

export function diffGenerated(root, { copy } = {}) {
  const tmp = mkdtempSync(path.join(tmpdir(), 'go-getter-check-'));
  try {
    writeOutputs(tmp, compile({ root }), copy === undefined ? {} : { copy });
    const expected = snapshot(tmp);
    const actual = snapshot(root);
    const problems = [];
    for (const p of new Set([...Object.keys(expected), ...Object.keys(actual)])) {
      if (!(p in actual)) problems.push(`missing: ${p}`);
      else if (!(p in expected)) problems.push(`not generated (stale or hand-added): ${p}`);
      else if (actual[p] !== expected[p]) problems.push(`differs: ${p}`);
    }
    return problems.sort();
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
}

export default function checkGenerated({ root, args }) {
  const copy = args.includes('--copy') ? true : undefined;
  if (!existsSync(path.join(root, 'src'))) {
    console.error('check generated: no src/ directory');
    return 1;
  }
  const problems = diffGenerated(root, { copy });
  // Self-hosting (decision 0010): this repo's own apply outputs (AGENTS.md section, hooks, CI) must be current.
  if (existsSync(path.join(root, RUNNER))) problems.push(...diffApply(root, planApply(root)).map((p) => `apply ${p}`));
  if (problems.length) {
    console.error(`check generated: ${problems.length} problem(s); run "npm run build" and never hand-edit generated files`);
    for (const p of problems) console.error(`  ${p}`);
    return 1;
  }
  console.log('check generated: ok');
  return 0;
}
