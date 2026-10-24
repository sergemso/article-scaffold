// go-getter sandbox [--host <h>]: prints the hosts' secret-lever snippets for the adopted restricted paths. Writes no file.
import { loadCapabilities } from '../capabilities.mjs';
import { sandboxReport } from '../sandbox.mjs';

export default function sandboxCommand({ root, args }) {
  const caps = loadCapabilities(root);
  let hosts = Object.keys(caps);
  for (let i = 0; i < args.length; i++) {
    if (args[i] !== '--host') {
      console.error(`go-getter sandbox: unknown argument "${args[i]}"\nusage: go-getter sandbox [--host <h>]`);
      return 2;
    }
    const host = args[++i];
    if (!caps[host]) {
      console.error(`go-getter sandbox: unknown host "${host}" (${Object.keys(caps).join(', ')})`);
      return 2;
    }
    hosts = [host];
  }
  console.log(sandboxReport(process.cwd(), caps, hosts));
  return 0;
}
