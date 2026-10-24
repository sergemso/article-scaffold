// go-getter detect [dir]: print repository facts as JSON.
import path from 'node:path';
import { detect } from '../detect.mjs';

export default function detectCommand({ args }) {
  const dir = path.resolve(args[0] ?? process.cwd());
  console.log(JSON.stringify(detect(dir), null, 2));
  return 0;
}
