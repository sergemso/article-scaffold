// go-getter watch [--noise quiet|normal|verbose] [--until done] -- <command>: a quiet wrapper for watch commands (decision 0070).
import { resolveLevel, runWatch } from '../watch.mjs';

const USAGE = 'usage: go-getter watch [--noise quiet|normal|verbose] [--until done] -- <command>';

export default async function watchCommand({ args }) {
  const sep = args.indexOf('--');
  const opts = sep === -1 ? args : args.slice(0, sep);
  const argv = sep === -1 ? [] : args.slice(sep + 1);
  const value = (name) => (opts.includes(name) ? opts[opts.indexOf(name) + 1] : undefined);
  const unknown = opts.filter((a, i) => !['--noise', '--until'].includes(a) && !['--noise', '--until'].includes(opts[i - 1]));
  if (!argv.length || unknown.length || (opts.includes('--until') && value('--until') !== 'done') || (opts.includes('--noise') && !value('--noise'))) {
    console.error(USAGE);
    return 2;
  }
  let level;
  try {
    level = resolveLevel(process.cwd(), value('--noise'));
  } catch (err) {
    console.error(`watch: ${err.message}`);
    return 2;
  }
  return runWatch(argv, { level, until: opts.includes('--until') });
}
