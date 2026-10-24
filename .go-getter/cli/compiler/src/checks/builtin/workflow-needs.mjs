// The named workflow job must depend on the listed jobs. Vacuously true while the workflow does not exist yet.
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

export default function workflowNeeds({ project, args }) {
  const file = path.join(project, args.file ?? '');
  if (!existsSync(file)) return { ok: true, message: `${args.file} not present yet` };
  const text = readFileSync(file, 'utf8');
  const job = new RegExp(`^  ${args.job}:\\s*$([\\s\\S]*?)(?=^  \\S|(?![\\s\\S]))`, 'm').exec(text);
  if (!job) return { ok: false, message: `${args.file} has no job "${args.job}"` };
  const needsLine = /^\s+needs:\s*\[?([^\]\n]*)\]?/m.exec(job[1]);
  const needs = new Set((needsLine?.[1] ?? '').split(',').map((s) => s.trim()).filter(Boolean));
  const missing = String(args.needs ?? '').split(',').filter((n) => n && !needs.has(n));
  return missing.length ? { ok: false, message: `job "${args.job}" does not need: ${missing.join(', ')}` } : { ok: true };
}
