import { existsSync } from 'node:fs';
import path from 'node:path';

export default function pathExists({ project, args }) {
  const missing = String(args.path ?? '').split(',').filter(Boolean).filter((p) => !existsSync(path.join(project, p)));
  return missing.length ? { ok: false, message: `missing: ${missing.join(', ')}` } : { ok: true };
}
