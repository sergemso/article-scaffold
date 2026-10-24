// go-getter packs [--json]: list available practice packs.
import { listPackFiles, loadPack } from '../packs.mjs';

export default function packsCommand({ root, args }) {
  const packs = listPackFiles(root).map((f) => {
    const p = loadPack(f);
    return { id: p.id, version: p.version, family: p.family, components: p.components ?? [], requires: p.requires ?? [], title: p.title, summary: p.summary };
  });
  if (args.includes('--json')) console.log(JSON.stringify(packs, null, 2));
  else if (!packs.length) console.log('no packs available');
  else for (const p of packs) console.log(`${p.id}@${p.version} [${p.family}${p.components.length ? ` ${p.components.join(',')}` : ''}] ${p.title} — ${p.summary}`);
  return 0;
}
