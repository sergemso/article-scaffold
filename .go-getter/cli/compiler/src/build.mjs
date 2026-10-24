// Compiles neutral source (src/) into each host's distributable packaging (decision 0021, output kind A).
// An output is a map of repo-relative path -> { content } | { symlink: relativeTarget }.
import { readFileSync, readdirSync, statSync, existsSync, mkdirSync, writeFileSync, rmSync, symlinkSync, lstatSync, cpSync } from 'node:fs';
import path from 'node:path';
import { parseFrontmatter } from './frontmatter.mjs';
import { HOSTS, loadCapabilities } from './capabilities.mjs';
import { PLUGIN_DIR } from './emit.mjs';
import claudeCode from '../adapters/claude-code.mjs';
import codex from '../adapters/codex.mjs';
import kilo from '../adapters/kilo.mjs';
import opencode from '../adapters/opencode.mjs';
import cursor from '../adapters/cursor.mjs';
import copilot from '../adapters/copilot.mjs';
import geminiCli from '../adapters/gemini-cli.mjs';

export { PLUGIN_DIR };

// One emitter per host in compiler/adapters/<host>.mjs; identical shared entries are merged.
export const ADAPTERS = { 'claude-code': claudeCode, codex, kilo, opencode, cursor, copilot, 'gemini-cli': geminiCli };

// Plugin-root directories that skills reference relatively (knowledge-base skills use ../../shared and ../../templates).
export const SUPPORT_DIRS = ['shared', 'templates'];
// Paths the build owns completely; anything else in the repo is left alone.
export const GENERATED_ROOTS = [
  PLUGIN_DIR,
  '.claude-plugin/marketplace.json',
  '.agents/plugins/marketplace.json',
  'gemini-extension.json',
  'skills',
  ...SUPPORT_DIRS,
];

const SKILL_NAME = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const SPEC_FIELDS = new Set(['name', 'description', 'license', 'compatibility', 'metadata', 'allowed-tools']);

function listFiles(dir, base = dir) {
  return readdirSync(dir)
    .sort()
    .flatMap((name) => {
      const p = path.join(dir, name);
      return statSync(p).isDirectory() ? listFiles(p, base) : [path.relative(base, p).split(path.sep).join('/')];
    });
}

// Reads skills from <baseDir>/skills/<name>/ (src/).
export function readSkills(baseDir, { exclude = [] } = {}) {
  const skillsDir = path.join(baseDir, 'skills');
  if (!existsSync(skillsDir)) return [];
  return readdirSync(skillsDir)
    .filter((n) => statSync(path.join(skillsDir, n)).isDirectory() && !exclude.includes(n))
    .sort()
    .map((dirName) => {
      const dir = path.join(skillsDir, dirName);
      const skillFile = path.join(dir, 'SKILL.md');
      if (!existsSync(skillFile)) throw new Error(`skill ${dirName}: missing SKILL.md`);
      const { data } = parseFrontmatter(readFileSync(skillFile, 'utf8'));
      if (data.name !== dirName) throw new Error(`skill ${dirName}: frontmatter name "${data.name}" must equal the directory name`);
      if (!SKILL_NAME.test(dirName)) throw new Error(`skill ${dirName}: name must match ${SKILL_NAME}`);
      if (typeof data.description !== 'string' || !data.description.trim()) throw new Error(`skill ${dirName}: description is required`);
      const extra = Object.keys(data).filter((k) => !SPEC_FIELDS.has(k));
      if (extra.length) throw new Error(`skill ${dirName}: non-standard frontmatter ${extra.join(', ')} (Agent Skills fields only)`);
      const files = listFiles(dir);
      return { name: dirName, files, read: (f) => readFileSync(path.join(dir, f)) };
    });
}

// The plugin-root support directories the skills reference relatively (src/shared, src/templates).
export function readSupportDirs(root) {
  const base = path.join(root, 'src');
  return SUPPORT_DIRS.filter((d) => existsSync(path.join(base, d))).map((dir) => ({
    dir,
    files: listFiles(path.join(base, dir)),
    read: (f) => readFileSync(path.join(base, dir, f)),
  }));
}

// Skills that run the CLI carry a copy of it in <skill>/cli (decision 0093), so they work with no network, no npx and
// no environment variable, and travel with the skill on every install route. The copy is the CLI's package root:
// compiler/bin finds the packs and hooks it reads (src/) relative to itself.
export const CLI_SKILLS = ['go-getter-init'];
export const CLI_DIR = 'cli';
const CLI_SOURCES = ['compiler/bin', 'compiler/src', 'compiler/schemas', 'compiler/capabilities', 'compiler/adapters', 'src/packs', 'src/hooks'];

// The files of the CLI copy as a map of path inside <skill>/cli -> content.
export function cliBundle(root, pkg) {
  const files = {};
  for (const dir of CLI_SOURCES) {
    const abs = path.join(root, dir);
    if (!existsSync(abs)) continue;
    for (const f of listFiles(abs)) files[`${dir}/${f}`] = readFileSync(path.join(abs, f));
  }
  if (!Object.keys(files).length) return files;
  const { name, version, description, license, type, engines } = pkg;
  files['package.json'] = Buffer.from(`${JSON.stringify({ name, version, description, license, type, engines }, null, 2)}\n`);
  return files;
}

function withCli(skill, bundle) {
  const names = Object.keys(bundle);
  if (!CLI_SKILLS.includes(skill.name) || !names.length) return skill;
  const prefix = `${CLI_DIR}/`;
  return {
    ...skill,
    files: [...skill.files, ...names.map((n) => prefix + n)].sort(),
    read: (f) => (f.startsWith(prefix) ? bundle[f.slice(prefix.length)] : skill.read(f)),
  };
}

export function packageMeta(pkg) {
  return {
    name: 'go-getter',
    version: pkg.version,
    description: pkg.description,
    author: { name: 'vivantel' },
    homepage: 'https://github.com/vivantel/go-getter',
    repository: 'https://github.com/vivantel/go-getter',
    license: pkg.license,
    keywords: ['agent-harness', 'sdlc', 'model-routing', 'guardrails'],
  };
}


function sameEntry(a, b) {
  if ('symlink' in a || 'symlink' in b) return a.symlink === b.symlink;
  return Buffer.from(a.content).equals(Buffer.from(b.content));
}

export function compile({ root, hosts = HOSTS }) {
  const pkg = JSON.parse(readFileSync(path.join(root, 'package.json'), 'utf8'));
  const caps = loadCapabilities(root);
  const bundle = cliBundle(root, pkg);
  const own = readSkills(path.join(root, 'src')).map((skill) => withCli(skill, bundle));
  const skills = [...own].sort((a, b) => a.name.localeCompare(b.name));
  const ctx = { pkg, meta: packageMeta(pkg), skills, supportDirs: readSupportDirs(root), caps };
  const outputs = {};
  for (const host of hosts) {
    const adapter = ADAPTERS[host];
    if (!adapter) throw new Error(`no adapter for host "${host}"`);
    for (const [p, entry] of Object.entries(adapter(ctx))) {
      if (outputs[p] && !sameEntry(outputs[p], entry)) throw new Error(`hosts disagree on generated file ${p}`);
      outputs[p] = entry;
    }
  }
  // Keep the skills directory present even with no skills, so the gemini symlink never dangles.
  if (!Object.keys(outputs).some((p) => p.startsWith(`${PLUGIN_DIR}/skills/`))) {
    outputs[`${PLUGIN_DIR}/skills/.gitkeep`] = { content: '' };
  }
  return outputs;
}

function removePath(p) {
  try {
    lstatSync(p);
  } catch {
    return;
  }
  rmSync(p, { recursive: true, force: true });
}

export function writeOutputs(targetRoot, outputs, { copy = process.platform === 'win32' } = {}) {
  for (const r of GENERATED_ROOTS) removePath(path.join(targetRoot, r));
  const symlinks = [];
  for (const [rel, entry] of Object.entries(outputs)) {
    const dest = path.join(targetRoot, rel);
    mkdirSync(path.dirname(dest), { recursive: true });
    if ('symlink' in entry) symlinks.push([dest, entry.symlink]);
    else writeFileSync(dest, entry.content);
  }
  // Symlinks last, so copy mode can copy their already-written targets.
  for (const [dest, target] of symlinks) {
    const absTarget = path.join(targetRoot, target);
    if (copy) cpSync(absTarget, dest, { recursive: true });
    else symlinkSync(path.relative(path.dirname(dest), absTarget), dest);
  }
}
