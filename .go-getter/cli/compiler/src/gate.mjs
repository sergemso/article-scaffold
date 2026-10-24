// Gate catalog and matcher for decision 0094: shell commands of two classes need a human.
// `irreversible` commands destroy history or data; `outward` commands publish work to other people.
//
// `matchGated` splits a command into segments (on `&&`, `||`, `;`, `|`, `&`, newlines, parentheses and backticks outside
// quotes), strips leading `VAR=value` words, `sudo` and `env`, and matches each segment's command word and arguments.
// Limits, by design:
// - Text inside quotes is masked, so `echo "git push"` does not match. SQL entries read the quoted text of psql, mysql
//   and sqlite3 commands, since that is where the statement is.
// - A wrapped command (`sh -c "git push"`, `eval`, a script that pushes) is matched on its literal text only: the verb must
//   be the segment's command word. Heredoc body lines count as segments, so a gated verb in one prompts: the safe failure.
import { existsSync } from 'node:fs';
import path from 'node:path';
import { tmpdir } from 'node:os';

const GIT = String.raw`git(?:\s+(?:-[Cc]\s+\S+|--[\w-]+(?:=\S+)?|-[pP]))*\s+`;
const ARGS = String.raw`(?:\s+\S+)*`;
const END = String.raw`(?=\s|$)`;
const flag = (letters) => String.raw`-[a-zA-Z]*[${letters}][a-zA-Z]*`;
const hasFlag = (alts) => String.raw`(?=${ARGS}\s+(?:${alts})(?=\s|=|$))`;
const LIST_FLAGS = '-d|--delete|-l|--list|-v|--verify|-n|--contains|--no-contains|--merged|--no-merged|--points-at|--sort';

// Whether every target of an `rm` command is inside /tmp or the OS temporary directory.
const inTemp = (text) => {
  const roots = ['/tmp', tmpdir().replace(/\/+$/, '')];
  const targets = text.split(/\s+/).slice(1).filter((w) => !w.startsWith('-')).map((w) => w.replace(/^["']|["']$/g, ''));
  return targets.length > 0 && targets.every((t) => !t.split('/').includes('..') && roots.some((r) => t.startsWith(`${r}/`)));
};

const ENTRIES = [
  { id: 'git-push-force', class: 'irreversible', description: 'force-push rewrites remote history',
    pattern: new RegExp(`^${GIT}push${END}(?:${hasFlag(`${flag('f')}|--force(?:-with-lease|-if-includes)?(?:=\\S+)?`)}|${hasFlag('\\+\\S+')})`),
    examples: { match: ['git push --force', 'git push -f origin main', 'git push --force-with-lease=main', 'git push origin +main', 'git -C app push -uf'], noMatch: ['git push origin main', 'git push --follow-tags'] } },
  { id: 'git-push-delete', class: 'irreversible', description: 'deletes a remote branch or tag',
    pattern: new RegExp(`^${GIT}push${END}(?:${hasFlag(`${flag('d')}|--delete`)}|${hasFlag(':\\S+')})`),
    examples: { match: ['git push --delete origin old', 'git push origin :old', 'git push -d origin old'], noMatch: ['git push origin main'] } },
  { id: 'git-reset-hard', class: 'irreversible', description: 'discards uncommitted work',
    pattern: new RegExp(`^${GIT}reset${ARGS}\\s+--hard${END}`),
    examples: { match: ['git reset --hard', 'git reset --hard origin/main'], noMatch: ['git reset HEAD file', 'git reset --soft HEAD~1'] } },
  { id: 'git-rebase', class: 'irreversible', description: 'rewrites commit history',
    pattern: new RegExp(`^${GIT}rebase${END}`),
    examples: { match: ['git rebase main', 'git rebase -i HEAD~3', 'git rebase --abort'], noMatch: ['git status', 'git pull --rebase'] } },
  { id: 'git-filter-branch', class: 'irreversible', description: 'rewrites the whole history',
    pattern: new RegExp(`^${GIT}filter-(?:branch|repo)${END}`),
    examples: { match: ['git filter-branch --tree-filter x', 'git filter-repo --path a'], noMatch: ['git log --follow x'] } },
  { id: 'git-branch-delete', class: 'irreversible', description: 'force-deletes a branch',
    pattern: new RegExp(`^${GIT}branch${ARGS}\\s+(?:${flag('D')}|-df|-fd|--delete\\s+--force)${END}`),
    examples: { match: ['git branch -D old', 'git branch -df old'], noMatch: ['git branch', 'git branch -d merged', 'git branch new'] } },
  { id: 'git-tag-delete', class: 'irreversible', description: 'deletes a tag',
    pattern: new RegExp(`^${GIT}tag${ARGS}\\s+(?:${flag('d')}|--delete)${END}`),
    examples: { match: ['git tag -d v1', 'git tag --delete v1'], noMatch: ['git tag -l', 'git tag v1'] } },
  { id: 'rm-rf', class: 'irreversible', description: 'recursive forced delete outside a temporary directory',
    pattern: new RegExp(`^rm${END}(?=${ARGS}\\s+(?:${flag('rR')}|--recursive)${END})(?=${ARGS}\\s+(?:${flag('f')}|--force)${END})`),
    exempt: inTemp,
    examples: { match: ['rm -rf build', 'rm -fr /', 'rm -r -f dist', 'rm --recursive --force x', 'rm -rf /tmp/../etc'], noMatch: ['rm -rf /tmp/build', 'rm -r dir', 'rm file', 'ls -rf'] } },
  { id: 'sql-destructive', class: 'irreversible', description: 'drops, truncates or deletes database rows', raw: true,
    pattern: /^(?:psql|mysql|sqlite3)(?=\s|$)[\s\S]*?\b(?:DROP\s+\w+|TRUNCATE|DELETE\s+FROM)\b/i,
    examples: { match: ['psql -c "DROP TABLE users"', 'mysql -e "truncate orders"', 'sqlite3 app.db "delete from t where 1"'], noMatch: ['psql -c "select 1"', 'echo "DROP TABLE x"'] } },
  { id: 'repo-settings', class: 'irreversible', description: 'changes repository settings, branch protection, secrets or access', provided: true },
  { id: 'git-push', class: 'outward', description: 'publishes commits to a remote',
    pattern: new RegExp(`^${GIT}push${END}`),
    examples: { match: ['git push', 'git push origin main', 'git -C app push'], noMatch: ['git status', 'git pull', 'git stash push', 'echo "git push"'] } },
  { id: 'pr-create', class: 'outward', description: 'opens a pull request', provided: true },
  { id: 'pr-merge', class: 'outward', description: 'merges a pull request', provided: true },
  { id: 'pr-close', class: 'outward', description: 'closes a pull request', provided: true },
  { id: 'release-create', class: 'outward', description: 'publishes a release', provided: true },
  { id: 'git-tag-create', class: 'outward', description: 'creates a tag',
    pattern: new RegExp(`^${GIT}tag(?!${ARGS}\\s+(?:${LIST_FLAGS})(?=\\s|=|$))(?=(?:\\s+-\\S+)*\\s+[^\\s-])`),
    examples: { match: ['git tag v1', 'git tag -a v1 -m "release"', 'git tag -s v1'], noMatch: ['git tag', 'git tag -l', 'git tag --list "v*"', 'git tag -d v1'] } },
  { id: 'package-publish', class: 'outward', description: 'publishes a package',
    pattern: /^(?:npm|pnpm|yarn)(?:\s+-\S+)*(?:\s+npm)?\s+publish(?=\s|$)/,
    examples: { match: ['npm publish', 'pnpm publish --no-git-checks', 'yarn npm publish'], noMatch: ['npm install', 'npm run publish-docs', 'npm pack'] } },
  { id: 'comment-post', class: 'outward', description: 'posts a comment on an issue or pull request', provided: true },
];

// What each hosting provider supplies for the entries marked `provided`: the command pattern, examples and native ask globs
// (decision 0129). The entries name the action; a project picks the provider with `provider=` on `gate-command` (default
// github). A provider that does not offer an action is a gap to fill here, not a silent miss.
const PROVIDERS = {
  github: {
    'repo-settings': {
      // `gh repo edit|delete|...`, `gh secret|variable set|delete`, and `gh api` writes to settings-like endpoints.
      pattern: new RegExp(`^gh\\s+(?:repo\\s+(?:edit|delete|archive|unarchive|rename|transfer)|(?:secret|variable)\\s+(?:set|delete|remove)|ruleset\\s+(?:create|edit|delete)|api(?=${ARGS}\\s+(?:-X|--method)(?:\\s+|=)(?:POST|PUT|PATCH|DELETE)${END})(?=${ARGS}\\s+\\S*(?:/protection|/rulesets|/collaborators|/hooks|/keys|/actions|/environments|/pages|/autolinks|/transfer|orgs/)\\S*)${END})`),
        native: ['gh repo edit *', 'gh repo delete *', 'gh repo archive *', 'gh repo unarchive *', 'gh repo rename *', 'gh repo transfer *', 'gh secret set *', 'gh secret delete *', 'gh secret remove *', 'gh variable set *', 'gh variable delete *', 'gh ruleset create *', 'gh ruleset edit *', 'gh ruleset delete *', 'gh api -X *', 'gh api --method *', 'gh api * -X *', 'gh api * --method *'],
      examples: { match: ['gh repo edit --default-branch dev', 'gh repo delete x --yes', 'gh secret set TOKEN', 'gh api -X PUT repos/o/r/branches/main/protection', 'gh api repos/o/r/rulesets -X POST', 'gh api --method DELETE repos/o/r/hooks/1'], noMatch: ['gh repo view', 'gh repo clone o/r', 'gh secret list', 'gh api repos/o/r/pulls', 'gh api -X GET repos/o/r/branches/main/protection', 'gh api -X POST repos/o/r/issues/1/comments'] } },
    'pr-create': { pattern: /^gh\s+pr\s+create(?=\s|$)/, native: ['gh pr create *'],
      examples: { match: ['gh pr create --fill', 'gh pr create'], noMatch: ['gh pr view 5', 'gh pr list', 'gh pr merge 5'] } },
    'pr-merge': { pattern: /^gh\s+pr\s+merge(?=\s|$)/, native: ['gh pr merge *'],
      examples: { match: ['gh pr merge 5', 'gh pr merge --squash --delete-branch 5'], noMatch: ['gh pr checks 5', 'gh pr create --fill'] } },
    'pr-close': { pattern: /^gh\s+pr\s+close(?=\s|$)/, native: ['gh pr close *'],
      examples: { match: ['gh pr close 5'], noMatch: ['gh pr view 5', 'gh pr merge 5'] } },
    'release-create': { pattern: /^gh\s+release\s+create(?=\s|$)/, native: ['gh release create *'],
      examples: { match: ['gh release create v1'], noMatch: ['gh release list', 'gh release view v1'] } },
    'comment-post': { pattern: /^gh\s+(?:issue|pr)\s+comment(?=\s|$)/, native: ['gh issue comment *', 'gh pr comment *'],
      examples: { match: ['gh issue comment 3 -b hi', 'gh pr comment 5 -b hi'], noMatch: ['gh issue view 3', 'gh pr checks'] } },
  },
};
export const PROVIDER_IDS = Object.keys(PROVIDERS);
export const DEFAULT_PROVIDER = 'github';

// Command globs of each entry for the hosts' native ask rules (`*` matches any text; a trailing ` *` also matches the bare
// command). Native rules see one command at a time, after the host splits compound commands. They cannot tell `rm -rf /tmp/x`
// from `rm -rf x`, nor a list `git tag -l` from a create, and do not strip `sudo` or see `git -C dir push`: they prompt more
// than `matchGated` in the first two cases and less in the last two, so the hook is not a substitute (decision 0094).
const around = (base, ...flags) => flags.flatMap((f) => [`${base} ${f}`, `${base} * ${f}`]);
const sql = (tool) => ['DROP *', 'drop *', 'TRUNCATE*', 'truncate*', 'DELETE FROM*', 'delete from*'].map((w) => `${tool} *${w}`);
const NATIVE = {
  'git-push-force': [...around('git push', '-f*', '--force*', '+*')],
  'git-push-delete': [...around('git push', '-d*', '--delete*', ':*')],
  'git-reset-hard': around('git reset', '--hard*'),
  'git-rebase': ['git rebase *'],
  'git-filter-branch': ['git filter-branch *', 'git filter-repo *'],
  'git-branch-delete': [...around('git branch', '-D*', '-df*', '-fd*', '--delete --force*', '--force --delete*')],
  'git-tag-delete': around('git tag', '-d*', '--delete*'),
  'rm-rf': [...around('rm', '-rf*', '-fr*', '-Rf*', '-fR*', '-r -f*', '-f -r*', '--recursive --force*', '--force --recursive*')],
  'sql-destructive': ['psql', 'mysql', 'sqlite3'].flatMap(sql),
  'git-push': ['git push *'],
  'git-tag-create': ['git tag *'],
  'package-publish': ['npm publish *', 'pnpm publish *', 'yarn publish *', 'yarn npm publish *'],
};
// The catalog with the provider's commands filled in.
export function catalogFor(provider = DEFAULT_PROVIDER) {
  const table = PROVIDERS[provider];
  if (!table) throw new Error(`unknown gate provider "${provider}"; known: ${PROVIDER_IDS.join(', ')}`);
  return ENTRIES.map(({ provided, ...e }) => {
    if (!provided) return { ...e, native: NATIVE[e.id] };
    const p = table[e.id];
    if (!p) throw new Error(`gate provider "${provider}" has no command for ${e.id}`);
    return { ...e, ...p };
  });
}
export const CATALOG = catalogFor();

// The outward shapes a remembered approval or a run may allow (decision 0130). Tags, releases and publishing are never on it.
export const APPROVABLE = ['git-push', 'pr-create', 'pr-merge', 'pr-close', 'comment-post'];
// The shape of an MCP write tool a person approved or a run granted (decision 0138 item 2): `mcp:<server>:<tool>`, the server as `normaliseServer` spells it.
export const MCP_SHAPE = /^mcp:[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+$/;
export const isApprovable = (id) => APPROVABLE.includes(id) || MCP_SHAPE.test(String(id));

// Splits into command segments, each as `{ raw, masked }` of equal length; masked has quoted text (quotes included) as 'X'.
function segments(command) {
  const out = [];
  let raw = '';
  let masked = '';
  let quote = null;
  const flush = () => {
    if (raw.trim()) out.push({ raw, masked });
    raw = '';
    masked = '';
  };
  const add = (ch, mask = ch) => {
    raw += ch;
    masked += mask;
  };
  for (let i = 0; i < command.length; i++) {
    const ch = command[i];
    if (quote === "'") {
      add(ch, 'X');
      if (ch === "'") quote = null;
    } else if (quote === '"') {
      add(ch, 'X');
      if (ch === '\\' && i + 1 < command.length) add(command[++i], 'X');
      else if (ch === '"') quote = null;
    } else if (ch === '\\' && command[i + 1] === '\n') {
      add(' ');
      i++;
    } else if (ch === '\\' && i + 1 < command.length) {
      add(ch, 'X');
      add(command[++i], 'X');
    } else if (ch === "'" || ch === '"') {
      quote = ch;
      add(ch, 'X');
    } else if ('\n;|()`'.includes(ch)) flush();
    else if (ch === '&' && !'<>'.includes(command[i - 1] ?? '') && command[i + 1] !== '>') flush();
    else add(ch);
  }
  flush();
  return out;
}

const PREFIX = /^\s*(?:(?:[A-Za-z_]\w*=\S*|sudo(?:\s+(?:-[ugCphrtUT]\s+\S+|-\S+))*|env(?:\s+(?:-[uCS]\s+\S+|-\S+))*)(?:\s+|$))*/;

// A project pattern written /like this/ is a regex; any other is a command prefix. `extra` lists are comma-separated, so a
// regex with a comma (a `{1,3}` quantifier) cannot be written there.
export const isRegexExtra = (spec) => /^\/.+\/[a-z]*$/s.test(spec);
const parseExtra = (spec) => {
  const m = /^\/(.+)\/([a-z]*)$/s.exec(spec);
  return m ? { id: `extra:${spec}`, test: (text) => new RegExp(m[1], m[2]).test(text) } : { id: `extra:${spec}`, test: (text) => text === spec.trim() || text.startsWith(`${spec.trim()} `) };
};

// The catalog entries (and project `extra` patterns, which are outward commands and ignore `classes`) that `command` matches.
// The GitHub-named ids from before the ids were neutral stay accepted: `gh-pr-*`, `gh-release-create`, `gh-comment`, and
// `gh-pr` (the id before it was split into create, merge and close), which means all three.
const ALIASES = {
  'gh-pr': ['pr-create', 'pr-merge', 'pr-close'],
  'gh-pr-create': ['pr-create'],
  'gh-pr-merge': ['pr-merge'],
  'gh-pr-close': ['pr-close'],
  'gh-release-create': ['release-create'],
  'gh-comment': ['comment-post'],
};
export const normaliseFree = (ids = []) => ids.flatMap((id) => ALIASES[id] ?? [id]);

// `free` lists catalog ids the project lets run without a human (outward entries only, `gateEntries` rejects others).
export function matchGated(command, { classes = ['irreversible', 'outward'], extra = [], free = [], provider = DEFAULT_PROVIDER } = {}) {
  if (typeof command !== 'string' || !command.trim()) return [];
  const freed = normaliseFree(free);
  const wanted = catalogFor(provider).filter((e) => classes.includes(e.class) && !freed.includes(e.id));
  const extras = extra.map(String).filter((s) => s.trim()).map(parseExtra);
  const hits = new Set();
  const found = [];
  for (const seg of segments(command)) {
    const cut = PREFIX.exec(seg.masked)[0].length;
    const masked = seg.masked.slice(cut).trim();
    const raw = seg.raw.slice(cut).trim();
    for (const e of wanted) {
      if (!hits.has(e.id) && e.pattern.test(e.raw ? raw : masked) && !e.exempt?.(raw)) {
        hits.add(e.id);
        found.push(e);
      }
    }
    for (const x of extras) {
      if (!hits.has(x.id) && x.test(raw.replace(/\s+/g, ' '))) {
        hits.add(x.id);
        found.push({ id: x.id, class: 'outward', description: 'a command this project gates', pattern: null });
      }
    }
  }
  return found;
}

// The `extra` patterns as catalog-shaped entries for `nativeRules`: a command prefix becomes a glob; a /regex/ has no native
// form, so it carries no globs and `nativeRules` leaves it to the hook.
export const extraEntries = (extra = []) =>
  extra.map(String).map((s) => s.trim()).filter(Boolean).map((s) => ({ id: `extra:${s}`, class: 'outward', native: isRegexExtra(s) ? [] : [`${s} *`] }));

// The host's native ask rules for `entries` (catalog entries from `CATALOG`, `extraEntries`), in the format its capabilities
// name under `permissions.ask`; null for a host without one.
//   claude-permissions: a list of `Bash(<glob>)` rules for `permissions.ask`
//   opencode-permission: a map of glob to "ask" for `permission.bash`
export function nativeRules(host, entries, caps) {
  const format = caps[host]?.permissions?.ask?.format;
  if (!format) return null;
  // A host whose pre-tool hook can ask prompts for an identity-gated call itself, for every spelling, so it needs no glob; the same
  // for a shape a run or a remembered approval may allow (`hookDecides`): a static ask rule would prompt even when it is allowed.
  const hookAsks = caps[host]?.hooks?.askPreTool === true;
  const globs = [...new Set(entries.filter((e) => !((e.identity || e.hookDecides) && hookAsks)).flatMap((e) => e.native ?? []))];
  if (format === 'claude-permissions') return globs.map((g) => `Bash(${g})`);
  if (format === 'opencode-permission') return Object.fromEntries(globs.map((g) => [g, 'ask']));
  throw new Error(`unknown ask rule format "${format}" for ${host}`);
}

const list = (s) => String(s ?? '').split(',').map((x) => x.trim()).filter(Boolean);

// The `classes` and `extra` of a `builtin:gate-command` entry's arguments (comma-separated lists), for apply and the hook.
export const GATE_CLASSES = ['irreversible', 'outward'];
// `go-getter` lists go-getter subcommands (`plan issue create`) that are gated whichever way go-getter is run (decision 0126).
export const gateArgs = (args = {}) => ({ classes: list(args.classes ?? 'irreversible,outward'), extra: list(args.extra), free: normaliseFree(list(args.free)), goGetter: list(args['go-getter']), grantable: normaliseFree(list(args.grantable)), provider: String(args.provider ?? DEFAULT_PROVIDER).trim() });

// The ways go-getter is typed that a host's glob rules can name: the project runner, a go-getter on PATH, npx, and the entry script
// of a checkout. A call spelled any other way is still recognised by the hook, which reads what it runs (invocation.mjs).
export function goGetterSpellings(project) {
  const spellings = ['go-getter', '.go-getter/bin/go-getter', './.go-getter/bin/go-getter', 'npx go-getter', 'npx -y go-getter'];
  if (project && existsSync(path.join(project, 'compiler/bin/go-getter.mjs'))) spellings.push('node compiler/bin/go-getter.mjs');
  return spellings;
}

// The entries the tier-2 `builtin:gate-command` enforcement entries gate (from `collectEnforcement`): catalog entries of
// their classes, then their `extra` patterns.
export function gateEntries(enforcement, { project } = {}) {
  const gates = enforcement.filter((e) => e.tier === 2 && e.parsed?.kind === 'builtin' && e.parsed.id === 'gate-command').map((e) => {
    const args = gateArgs(e.parsed.args);
    const bad = args.classes.filter((c) => !GATE_CLASSES.includes(c));
    // A gate may list only project commands (`extra`) and no class, as the tracker pack's does for the write verbs.
    if ((!args.classes.length && !args.extra.length && !args.goGetter.length) || bad.length) throw new Error(`guardrail ${e.guardrail}: gate-command classes must be ${GATE_CLASSES.join(' and/or ')}${bad.length ? `, not ${bad.join(', ')}` : ''}`);
    const badSub = args.goGetter.filter((sub) => !/^[a-z][a-z-]*(?: [a-z][a-z-]*)*$/.test(sub));
    if (badSub.length) throw new Error(`guardrail ${e.guardrail}: gate-command go-getter must be subcommand words, not ${badSub.join(', ')}`);
    const ungrantable = args.grantable.filter((id) => !isApprovable(id));
    if (ungrantable.length) throw new Error(`guardrail ${e.guardrail}: gate-command grantable must name approvable commands (${APPROVABLE.join(', ')}), not ${ungrantable.join(', ')}`);
    if (!PROVIDER_IDS.includes(args.provider)) throw new Error(`guardrail ${e.guardrail}: gate-command provider must be one of ${PROVIDER_IDS.join(', ')}, not ${args.provider}`);
    const unfree = args.free.filter((id) => CATALOG.find((c) => c.id === id)?.class !== 'outward');
    if (unfree.length) throw new Error(`guardrail ${e.guardrail}: gate-command free must name outward catalog commands, not ${unfree.join(', ')}`);
    for (const x of args.extra.filter(isRegexExtra)) {
      try {
        new RegExp(x.slice(1, x.lastIndexOf('/')), x.slice(x.lastIndexOf('/') + 1));
      } catch (err) {
        throw new Error(`guardrail ${e.guardrail}: gate-command extra ${x} is not a valid regular expression (${err.message})`);
      }
    }
    return args;
  });
  // An entry is gated when some gate covers its class and does not free it.
  const gated = gates.flatMap((g) => catalogFor(g.provider).filter((e) => g.classes.includes(e.class) && !g.free.includes(e.id)));
  const grantable = new Set(gates.flatMap((g) => g.grantable));
  const gatedOnce = [...new Map(gated.map((e) => [e.id, grantable.has(e.id) ? { ...e, hookDecides: true } : e])).values()];
  // Subcommands gated by what the call runs: native globs for the usual spellings, for hosts whose hook cannot ask.
  const identity = [...new Set(gates.flatMap((g) => g.goGetter))].map((sub) => ({ id: `go-getter:${sub}`, class: 'outward', identity: sub.split(' '), native: goGetterSpellings(project).map((sp) => `${sp} ${sub} *`) }));
  return [...gatedOnce, ...extraEntries([...new Set(gates.flatMap((g) => g.extra))]), ...identity];
}

// OpenCode globs as automata, to reason about every command a glob matches rather than a sample of them. A glob is a token
// list (`*` any text, `?` one character, else a literal character); a trailing ` *` also accepts the bare command.
const STAR = Symbol('*');
const ANY = Symbol('?');
const automaton = (glob) => {
  const tokens = [...glob].map((ch) => (ch === '*' ? STAR : ch === '?' ? ANY : ch));
  return { tokens, accept: new Set(glob.endsWith(' *') ? [tokens.length, tokens.length - 2] : [tokens.length]) };
};
// The positions reachable from `positions` without reading a character (a star may match nothing), sorted.
const closure = (tokens, positions) => {
  const out = [...new Set(positions)];
  for (let k = 0; k < out.length; k++) if (tokens[out[k]] === STAR && !out.includes(out[k] + 1)) out.push(out[k] + 1);
  return out.sort((a, b) => a - b);
};
// The positions after reading `ch` (null stands for any character no glob names).
const step = (tokens, positions, ch) =>
  closure(tokens, positions.flatMap((i) => (tokens[i] === STAR ? [i] : tokens[i] === ANY || (ch !== null && tokens[i] === ch) ? [i + 1] : [])));

const LIMIT = 20000;
// Whether some command matched by `globs[0]` makes `test` true; `test` gets, per glob, whether that glob matches the
// command. Walks the product of the automata: from each state only the literals the current positions expect, plus
// one character none of them expects, lead anywhere distinct. null past LIMIT states.
function someCommand(globs, test) {
  const machines = globs.map(automaton);
  const keyOf = (state) => state.map((s) => s.join(',')).join('|');
  const start = machines.map((m) => closure(m.tokens, [0]));
  const seen = new Set([keyOf(start)]);
  const queue = [start];
  while (queue.length) {
    const state = queue.pop();
    if (test(state.map((s, i) => s.some((p) => machines[i].accept.has(p))))) return true;
    const expected = new Set(state.flatMap((s, i) => s.map((p) => machines[i].tokens[p]).filter((t) => typeof t === 'string')));
    for (const ch of [...expected, null]) {
      const next = state.map((s, i) => step(machines[i].tokens, s, ch));
      if (!next[0].length) continue;
      const key = keyOf(next);
      if (seen.has(key)) continue;
      if (seen.add(key).size > LIMIT) return null;
      queue.push(next);
    }
  }
  return false;
}

// The OpenCode rules that apply to bash, in evaluation order: `permission` keys `*` and `bash`, a string value being a
// rule for every command. Each carries `pos`, the index of its `permission` key, and `at`, its index inside that key's map.
const bashRules = (permission) =>
  Object.entries(permission).flatMap(([key, value], pos) => {
    if (key !== 'bash' && key !== '*') return [];
    if (typeof value === 'string') return [{ glob: '*', action: value, pos, at: 0 }];
    return Object.entries(value ?? {}).map(([glob, action], at) => ({ glob, action, pos, at }));
  });
// The action of the last of `rules` whose glob matches, given the match vector (index 0 is the glob being placed).
const lastAction = (rules, matched) => rules.findLast((_, i) => matched[i + 1])?.action;
const prompts = (action) => action === 'ask' || action === 'deny';
// The rules that match some command `glob` matches (the others never decide one of its commands), in order; a rule
// whose overlap is unknown is kept.
const overlapping = (glob, rules) => rules.filter((r) => someCommand([glob, r.glob], (m) => m[0] && m[1]) !== false);
// Whether some command of `glob` makes `test` true, given the rules that overlap it and the match vector.
const anyCommand = (glob, rules, test) => someCommand([glob, ...rules.map((r) => r.glob)], (m) => m[0] && test(m));

// `config` (a host's settings object) with the ask `rules` from `nativeRules` added, never weakening the user's own rules.
// Returns { config, unprompted, reason }: `unprompted` lists the rule globs some of whose commands still run without a
// prompt, because covering them would have overridden one of the user's rules.
//   claude-permissions: the rules the user's `permissions.ask` lacks are appended (deny rules win over ask on that host).
//   opencode-permission: OpenCode takes the last matching rule in config order (`evaluate`, findLast). A glob whose
//   commands the user already asks for or denies is skipped. Otherwise it goes into `permission.bash` at the latest place
//   where it overrides no command the user denies (a user key with the same glob that allows is set to ask in place);
//   user keys never move, so removing the added keys restores the map as it was. A string `permission` or
//   `permission.bash` is left as it is: replacing it with a map would make go-getter own the whole value.
export function withAskRules(format, config, rules) {
  if (format === 'claude-permissions') {
    const ask = [].concat(config.permissions?.ask ?? []);
    const added = rules.filter((r) => !ask.includes(r));
    if (!added.length) return { config, unprompted: [] };
    return { config: { ...config, permissions: { ...config.permissions, ask: [...ask, ...added] } }, unprompted: [] };
  }
  if (format !== 'opencode-permission') throw new Error(`unknown ask rule format "${format}"`);
  const permission = config.permission ?? {};
  if (typeof permission === 'string' || typeof permission.bash === 'string') {
    const unprompted = prompts(typeof permission === 'string' ? permission : permission.bash) ? [] : Object.keys(rules);
    return { config, unprompted, reason: unprompted.length ? `its ${typeof permission === 'string' ? 'permission' : 'permission.bash'} is a string; write it as a map to get ask rules` : undefined };
  }
  const user = bashRules(permission);
  const own = Object.keys(permission.bash ?? {});
  // Without a bash key, one is appended to `permission`, after every rule.
  const bashPos = 'bash' in permission ? Object.keys(permission).indexOf('bash') : Object.keys(permission).length;
  // Whether a rule is evaluated after a glob placed before the user's bash key `p` (own.length: after them all).
  const isLater = (r, p) => r.pos > bashPos || (r.pos === bashPos && r.at >= p);
  const bash = { ...permission.bash };
  const before = own.map(() => []); // before[p]: globs to insert before the user's bash key p
  const last = [];
  const unprompted = [];
  for (const [glob, action] of Object.entries(rules)) {
    const near = overlapping(glob, user);
    // Nothing to do where the user already prompts for every command of the glob (unknown counts as needing a rule).
    if (anyCommand(glob, near, (m) => !prompts(lastAction(near, m))) === false) continue;
    // Where the glob goes: before the user's bash key p (own.length: after them all), or onto the user's own key p - 1.
    let p = null;
    if (glob in bash) {
      if (bash[glob] === 'allow') {
        bash[glob] = action;
        p = own.indexOf(glob) + 1;
      }
    } else {
      // The latest place where the glob, winning a command, does not turn the user's deny into ask.
      for (let q = own.length; q >= 0 && p === null; q--) {
        if (anyCommand(glob, near, (m) => !near.some((r, i) => m[i + 1] && isLater(r, q)) && lastAction(near, m) === 'deny') === false) p = q;
      }
      if (p !== null) (p === own.length ? last : before[p]).push([glob, action]);
    }
    // Some of its commands still run unprompted when it is not written, or when a later user rule lets them through. The
    // other added rules only ask, so they cannot make a command unprompted.
    const later = p === null ? null : near.filter((r) => isLater(r, p));
    const open = later === null || anyCommand(glob, later, (m) => later.some((_, i) => m[i + 1]) && !prompts(lastAction(later, m))) !== false;
    if (open) unprompted.push(glob);
  }
  const merged = Object.fromEntries([...own.flatMap((g, p) => [...before[p], [g, bash[g]]]), ...last]);
  const next = { ...config, permission: { ...permission, bash: merged } };
  const changed = JSON.stringify(merged) !== JSON.stringify(permission.bash ?? {});
  return { config: changed ? next : config, unprompted, reason: unprompted.length ? 'covering them would override your own rules' : undefined };
}
