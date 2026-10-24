// What `go-getter secret run` and the pre-tool hook both need to read about a call (decisions 0107 and 0126): its arguments, the
// project's shared list of approved commands, and whether a command is approved for a secret path by that list. Kept apart from
// run.mjs so the hook can use it without importing the runner.
import { adoptedData } from '../governance.mjs';
import { matchesAny } from '../glob.mjs';

const USAGE = 'usage: go-getter secret run (--from <dotenv-file> | --file <path> [--env <NAME>]) -- <command> [args...]';
export { USAGE };

// "<pattern>|<command>" entries of the `use-commands` answer ("a|b c, d|e"): the commands approved for each pattern.
export function useCommands(project) {
  const out = [];
  for (const entry of String(adoptedData(project, 'use-commands') ?? '').split(/,\s+/)) {
    const at = entry.indexOf('|');
    if (at > 0 && entry.slice(at + 1).trim()) out.push({ pattern: entry.slice(0, at).trim(), command: entry.slice(at + 1).trim() });
  }
  return out;
}

// The arguments after `secret run`: { from | file, env?, command: [words] }, or { error }.
export function parseRunArgs(args) {
  const dash = args.indexOf('--');
  if (dash === -1) return { error: 'the command to run follows "--"' };
  const head = args.slice(0, dash);
  const command = args.slice(dash + 1);
  const opts = {};
  for (let i = 0; i < head.length; i++) {
    if (['--from', '--file', '--env'].includes(head[i]) && head[i + 1] && !head[i + 1].startsWith('--')) opts[head[i].slice(2)] = head[++i];
    else return { error: `unknown or incomplete argument "${head[i]}"` };
  }
  if (Boolean(opts.from) === Boolean(opts.file)) return { error: 'give exactly one of --from and --file' };
  if (opts.env && !opts.file) return { error: '--env goes with --file' };
  if (opts.env && !/^[A-Za-z_][A-Za-z0-9_]*$/.test(opts.env)) return { error: '--env must be a variable name' };
  if (!command.length) return { error: 'the command to run follows "--"' };
  return { ...opts, command };
}

// Whether the project's shared list approves `commandText` (the command's words joined by single spaces) for the project-relative
// secret path `rel`. `modes` maps each restricted pattern to its mode: the shared list applies to `use` paths only.
export function sharedApproved(project, rel, commandText, modes) {
  return useCommands(project).some((u) => modes.get(u.pattern) === 'use' && matchesAny(rel, [u.pattern]) && u.command === commandText);
}
