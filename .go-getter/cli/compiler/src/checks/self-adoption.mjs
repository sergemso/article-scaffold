// Guardrail practice-ships-only-after-self-adoption (decision 0010): every pack in src/packs/ must be adopted
// by this repo, i.e. some active artifact in docs/ carries go-getter.generated-by == <id>@<version>.
import path from 'node:path';
import { listPackFiles, loadPack } from '../packs.mjs';
import { readArtifacts } from '../artifacts.mjs';

export function unadoptedPacks(packs, artifacts) {
  const adopted = new Set(artifacts.filter((a) => a.data.status === 'active').map((a) => a.data['go-getter']?.['generated-by']).filter(Boolean));
  return packs.filter((p) => !adopted.has(`${p.id}@${p.version}`)).map((p) => `${p.id}@${p.version}`);
}

export default function checkSelfAdoption({ root }) {
  const packs = listPackFiles(root).map(loadPack);
  const missing = unadoptedPacks(packs, readArtifacts(root));
  if (missing.length) {
    console.error(`check self-adoption: not adopted by this repo (run go-getter-init / render-pack here first): ${missing.join(', ')}`);
    return 1;
  }
  console.log(`check self-adoption: ok (${packs.length} pack${packs.length === 1 ? '' : 's'} adopted)`);
  return 0;
}
