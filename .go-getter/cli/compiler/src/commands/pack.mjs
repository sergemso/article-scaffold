// go-getter pack <id>: print a pack's JSON (questions, options, outputs) for the init skill to read.
import path from 'node:path';
import { existsSync } from 'node:fs';
import { loadPack } from '../packs.mjs';

export default function packCommand({ root, args }) {
  const file = path.join(root, 'src/packs', args[0] ?? '', 'pack.json');
  if (!args[0] || !existsSync(file)) {
    console.error(`pack: unknown pack "${args[0] ?? ''}" (see "go-getter packs")`);
    return 1;
  }
  console.log(JSON.stringify(loadPack(file), null, 2));
  return 0;
}
