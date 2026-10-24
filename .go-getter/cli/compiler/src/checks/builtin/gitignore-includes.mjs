import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

export default function gitignoreIncludes({ project, args }) {
  const file = path.join(project, '.gitignore');
  const lines = existsSync(file) ? readFileSync(file, 'utf8').split('\n').map((l) => l.trim()) : [];
  const missing = String(args.patterns ?? '').split(',').filter(Boolean).filter((p) => !lines.includes(p));
  return missing.length ? { ok: false, message: `.gitignore lacks: ${missing.join(', ')}` } : { ok: true };
}
