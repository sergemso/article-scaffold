import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

export default function fileMaxLines({ project, args }) {
  const file = path.join(project, args.path ?? '');
  const max = Number(args.max);
  if (!Number.isFinite(max)) return { ok: false, message: 'max must be a number' };
  if (!existsSync(file)) return { ok: false, message: `${args.path} does not exist` };
  const lines = readFileSync(file, 'utf8').replace(/\n$/, '').split('\n').length;
  return lines <= max ? { ok: true, message: `${lines}/${max} lines` } : { ok: false, message: `${args.path} has ${lines} lines, cap is ${max}` };
}
