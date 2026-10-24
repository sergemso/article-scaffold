// The code a command runs, as a set of project files and a hash of their contents (decision 0126). An approval to use a secret
// file is bound to this hash: edit the command's script, or a project file it imports, and the approval lapses and asks again; an
// edit to any other file does not. The set is found by reading, never by running: the files the command names (a script, an
// `npm run` script and what it runs, a shell script and what it sources or calls), then the project files they import
// (JavaScript and TypeScript exactly; shell and Python best effort).
//
// Only files inside the project are followed, by real path (a symlink out of it is not), up to a depth, a count and a size
// bound. A package from node_modules or a program outside the project is not part of the set.
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, realpathSync, statSync } from 'node:fs';
import path from 'node:path';
import { commandOf, commandWords } from '../shell.mjs';

const MAX_FILES = 300;
const MAX_DEPTH = 25;
const MAX_BYTES = 1024 * 1024;
const JS_EXT = ['.mjs', '.js', '.cjs', '.ts', '.mts', '.cts', '.jsx', '.tsx', '.json'];
const JS_FILE = /\.(?:mjs|cjs|js|jsx|ts|mts|cts|tsx)$/;
const INTERPRETERS = new Set(['node', 'nodejs', 'deno', 'bun', 'tsx', 'ts-node', 'python', 'python3', 'python2', 'ruby', 'perl', 'php', 'sh', 'bash', 'zsh', 'dash', 'ksh', 'ash', 'source', '.']);
const PACKAGE_RUNNERS = new Set(['npm', 'pnpm', 'yarn', 'bun']);

const sha = (data) => createHash('sha256').update(data).digest('hex');

// The first existing project file `word` names (a path, absolute or relative to `cwd`, which may list several directories to try),
// as a real path inside `root`, else null.
function projectFile(word, cwd, root) {
  if (typeof word !== 'string' || !word || word.startsWith('-')) return null;
  for (const dir of [].concat(cwd)) {
    try {
      const file = path.resolve(dir, word);
      if (!existsSync(file)) continue;
      const real = realpathSync(file);
      if (real !== root && !real.startsWith(`${root}${path.sep}`)) continue;
      if (statSync(real).isFile()) return real;
    } catch {
      // try the next directory
    }
  }
  return null;
}

// A JavaScript specifier as a project file: exact, with an extension, or an index; null for a package or a missing file.
function jsTarget(spec, fromFile, root) {
  if (!spec.startsWith('.') && !spec.startsWith('/')) return null;
  const base = path.resolve(path.dirname(fromFile), spec);
  const tries = [base, ...JS_EXT.map((e) => base + e), ...JS_EXT.map((e) => path.join(base, `index${e}`))];
  for (const candidate of tries) {
    const found = projectFile(candidate, root, root);
    if (found) return found;
  }
  return null;
}

const JS_IMPORTS = [
  /\bimport\s+(?:[^'";]*?\s+from\s+)?['"]([^'"\n]+)['"]/g,
  /\bexport\s+[^'";]*?\s+from\s+['"]([^'"\n]+)['"]/g,
  /\bimport\(\s*['"]([^'"\n]+)['"]\s*\)/g,
  /\brequire\(\s*['"]([^'"\n]+)['"]\s*\)/g,
  /\bnew\s+URL\(\s*['"](\.{1,2}\/[^'"\n]+)['"]\s*,\s*import\.meta\.url/g,
];

function pythonTargets(text, file, root) {
  const found = [];
  const dir = path.dirname(file);
  const tryModule = (base) => [`${base}.py`, path.join(base, '__init__.py')].map((c) => projectFile(c, root, root)).find(Boolean);
  const names = [];
  for (const m of text.matchAll(/^\s*import\s+([\w.]+(?:\s*,\s*[\w.]+)*)/gm)) names.push(...m[1].split(',').map((n) => n.trim()));
  for (const m of text.matchAll(/^[ \t]*from[ \t]+(\.*)([\w.]*)[ \t]+import[ \t]+([\w*, \t()]+)/gm)) {
    const dots = m[1].length;
    const start = dots ? path.resolve(dir, ...Array(Math.max(dots - 1, 0)).fill('..')) : null;
    const mod = m[2].replace(/\./g, '/');
    const bases = start ? [path.join(start, mod)] : [path.join(dir, mod), path.join(root, mod)];
    for (const b of bases) found.push(tryModule(b));
    // `from pkg import name` may name a submodule
    for (const name of m[3].replace(/[()]/g, '').split(',').map((n) => n.trim().split(/\s+/)[0]).filter(Boolean)) for (const b of bases) found.push(tryModule(path.join(b, name)));
  }
  for (const n of names) for (const b of [path.join(dir, n.replace(/\./g, '/')), path.join(root, n.replace(/\./g, '/'))]) found.push(tryModule(b));
  return found.filter(Boolean);
}

// The project files a command's words run or read as code: its program if it is a project file, an interpreter's script, a
// sourced file, and every path-like word that is a project file (a script calling another).
function fileWords(words, cwd, root) {
  const { name, args } = commandOf(words);
  const found = [];
  const program = words.find((w) => !/^[A-Za-z_][A-Za-z0-9_]*=/.test(w));
  if (program?.includes('/')) found.push(projectFile(program, cwd, root));
  if (name && INTERPRETERS.has(name)) {
    for (let k = 0; k < args.length; k++) {
      if (/^(?:-r|--require|--import|--loader|--experimental-loader)$/.test(args[k]) && args[k + 1]) found.push(projectFile(args[++k], cwd, root));
      else if (!args[k].startsWith('-')) {
        found.push(projectFile(args[k], cwd, root));
        break;
      }
    }
  }
  for (const w of args) if (/\.(?:sh|bash|mjs|cjs|js|ts|py|rb|pl|php)$/.test(w)) found.push(projectFile(w, cwd, root)); // a script calling another script
  return found.filter(Boolean);
}

// The npm script a `npm run <x>` / `npm test` / `npm start` style command runs, or null.
function packageScript(words, cwd, root) {
  const { name, args } = commandOf(words);
  if (!name || !PACKAGE_RUNNERS.has(name)) return null;
  const [first, second] = args;
  const script = ['run', 'run-script'].includes(first) ? second : ['test', 'start', 'build', 'stop', 'restart'].includes(first) ? first : name === 'yarn' || name === 'pnpm' || name === 'bun' ? first : null;
  if (!script || script.startsWith('-')) return null;
  const manifest = projectFile('package.json', root, root);
  if (!manifest) return null;
  try {
    const command = JSON.parse(readFileSync(manifest, 'utf8')).scripts?.[script];
    return typeof command === 'string' ? { manifest, command, cwd: root } : null;
  } catch {
    return null;
  }
}

// `{ files, hash, resolved, truncated }` for a command given as its words. `files` are project-relative, sorted; `resolved` is
// false when the command names no project file at all (its hash then covers its words only); `truncated` when a bound was hit.
export function fileSet(words, project) {
  const root = realpathSync(project);
  const seen = new Set();
  const order = [];
  let truncated = false;
  const queue = [];
  const add = (file, depth) => {
    if (!file || seen.has(file)) return;
    if (seen.size >= MAX_FILES || depth > MAX_DEPTH) {
      truncated = true;
      return;
    }
    seen.add(file);
    order.push(file);
    queue.push([file, depth]);
  };
  const analyse = (commandWordsList, cwd, depth) => {
    for (const w of commandWordsList) {
      for (const f of fileWords(w, cwd, root)) add(f, depth);
      const script = packageScript(w, cwd, root);
      if (script) {
        add(script.manifest, depth);
        const inner = commandWords(script.command);
        if (inner) analyse(inner, script.cwd, depth + 1);
      }
    }
  };
  analyse([words], root, 0);
  while (queue.length) {
    const [file, depth] = queue.shift();
    let text;
    try {
      if (statSync(file).size > MAX_BYTES) {
        truncated = true;
        continue;
      }
      text = readFileSync(file, 'utf8');
    } catch {
      continue;
    }
    if (JS_FILE.test(file)) {
      for (const re of JS_IMPORTS) for (const m of text.matchAll(re)) add(jsTarget(m[1], file, root), depth + 1);
    } else if (file.endsWith('.py')) {
      for (const t of pythonTargets(text, file, root)) add(t, depth + 1);
    } else if (/\.(?:sh|bash|zsh)$/.test(file) || text.startsWith('#!')) {
      const inner = commandWords(text.replace(/^#!.*\n/, ''));
      // a shell script's relative paths are the caller's: the project root first, then the script's own directory
      if (inner) analyse(inner, [root, path.dirname(file)], depth + 1);
    } else if (file.endsWith('.rb')) {
      for (const m of text.matchAll(/\brequire_relative\s+['"]([^'"\n]+)['"]/g)) {
        const base = path.resolve(path.dirname(file), m[1]);
        add(projectFile(base, root, root) ?? projectFile(`${base}.rb`, root, root), depth + 1);
      }
    }
  }
  const files = order.map((f) => path.relative(root, f).split(path.sep).join('/')).sort();
  const h = createHash('sha256');
  h.update(`${words.join('\0')}\n`);
  for (const rel of files) h.update(`${rel}\0${sha(readFileSync(path.join(root, rel)))}\n`);
  return { files, hash: h.digest('hex'), resolved: files.length > 0, truncated };
}

export const fileSetHash = (words, project) => fileSet(words, project).hash;
