// go-getter refs [--staged | --base <ref>] [--json]: candidate Refs: artifacts for a diff (plan A.1).
import { suggestRefs, formatRefs } from '../refs.mjs';

const USAGE = 'usage: go-getter refs [--staged | --base <ref>] [--json]';

export default function refsCommand({ args }) {
  const staged = args.includes('--staged');
  const base = args.includes('--base') ? args[args.indexOf('--base') + 1] : undefined;
  const unknown = args.filter((a, i) => !['--staged', '--base', '--json'].includes(a) && args[i - 1] !== '--base');
  if (unknown.length || (args.includes('--base') && (!base || base.startsWith('--'))) || (staged && base)) {
    console.error(USAGE);
    return 2;
  }
  try {
    const refs = suggestRefs(process.cwd(), { staged, base });
    console.log(args.includes('--json') ? JSON.stringify(refs, null, 2) : formatRefs(refs));
    return 0;
  } catch (err) {
    console.error(`refs: ${(err.stderr?.toString().trim() || err.message).split('\n')[0]}`);
    return 1;
  }
}
