// go-getter build [--host <id>]... [--copy]: regenerate distributable packaging from src/.
import { compile, writeOutputs } from '../build.mjs';

export function parseBuildArgs(args) {
  const hosts = [];
  let copy;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--host') hosts.push(args[++i]);
    else if (args[i] === '--copy') copy = true;
    else throw new Error(`build: unknown argument ${args[i]}`);
  }
  return { hosts: hosts.length ? hosts : undefined, copy };
}

export default function build({ root, args }) {
  const { hosts, copy } = parseBuildArgs(args);
  const outputs = compile({ root, hosts });
  writeOutputs(root, outputs, copy === undefined ? {} : { copy });
  console.log(`build: wrote ${Object.keys(outputs).length} generated paths`);
  return 0;
}
