// Repository detection probes (plan 4.2): facts the init interview prefills instead of asking.
// Output is deterministic: sorted arrays, null when unknown.
import { defaultBranch } from './git-env.mjs';
import { detectSpecTool } from './spec-tools.mjs';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import path from 'node:path';

const SKIP_DIRS = new Set(['.git', 'node_modules', 'vendor', 'dist', 'build', '.venv', 'venv', 'target', '__pycache__']);

const has = (root, rel) => existsSync(path.join(root, rel));
const readJson = (root, rel) => {
  try {
    return JSON.parse(readFileSync(path.join(root, rel), 'utf8'));
  } catch {
    return null;
  }
};
const readText = (root, rel) => (has(root, rel) ? readFileSync(path.join(root, rel), 'utf8') : '');
const sorted = (set) => [...set].sort();

function walk(root, maxDepth, visit, rel = '', depth = 0) {
  let names;
  try {
    names = readdirSync(path.join(root, rel));
  } catch {
    return;
  }
  for (const name of names.sort()) {
    const r = rel ? `${rel}/${name}` : name;
    let isDir;
    try {
      isDir = statSync(path.join(root, r)).isDirectory();
    } catch {
      continue;
    }
    visit(r, name, isDir);
    if (isDir && depth < maxDepth && !SKIP_DIRS.has(name)) walk(root, maxDepth, visit, r, depth + 1);
  }
}

function git(root, args) {
  try {
    return execFileSync('git', args, { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim() || null;
  } catch {
    return null;
  }
}

// Check catalog of decision 0071: the commands each check runs, inferred from conventions; null when unknown.
export const CHECKS = ['format', 'lint', 'typecheck', 'static-analysis', 'build', 'test', 'unit', 'integration', 'e2e', 'coverage'];
// Package scripts and Makefile targets per check, first match wins; non-mutating variants come first.
const SCRIPTS = {
  format: ['format:check', 'check:format', 'fmt:check', 'format', 'fmt'],
  lint: ['lint'],
  typecheck: ['typecheck', 'type-check', 'tsc'],
  'static-analysis': ['static-analysis', 'analyze', 'sast'],
  build: ['build'],
  unit: ['test:unit', 'unit'],
  integration: ['test:integration', 'integration', 'test:int'],
  e2e: ['test:e2e', 'e2e'],
  coverage: ['test:coverage', 'coverage', 'test:cov'],
};
const TARGETS = {
  format: ['format', 'fmt'],
  'static-analysis': ['static-analysis', 'analyze'],
  build: ['build'],
  test: ['test'],
  lint: ['lint'],
  typecheck: ['typecheck'],
  unit: ['unit', 'test-unit'],
  integration: ['integration', 'test-integration'],
  e2e: ['e2e', 'test-e2e'],
  coverage: ['coverage', 'test-coverage'],
};

function detectCommands(root, { pkg, deps, pyproject, packageManagers, languages }) {
  const commands = Object.fromEntries(CHECKS.map((c) => [c, null]));
  const set = (check, command) => {
    commands[check] ??= command;
  };
  if (pkg) {
    const manager = ['pnpm', 'yarn', 'bun'].find((m) => packageManagers.has(m)) ?? 'npm';
    const run = (name) => (name === 'test' ? `${manager} test` : manager === 'npm' ? `npm run ${name}` : `${manager} run ${name}`);
    const exec = { npm: 'npx', pnpm: 'pnpm exec', yarn: 'yarn', bun: 'bunx' }[manager];
    const scripts = pkg.scripts ?? {};
    // A stock `npm init` placeholder is not a test command.
    if (scripts.test && !/no test specified/.test(scripts.test)) set('test', run('test'));
    for (const [check, names] of Object.entries(SCRIPTS)) for (const name of names) if (scripts[name]) set(check, run(name));
    if (deps.prettier) set('format', `${exec} prettier --check .`);
    if (deps['@playwright/test'] || deps.playwright) set('e2e', `${exec} playwright test`);
    if (deps.cypress) set('e2e', `${exec} cypress run`);
  }
  const make = readText(root, 'Makefile');
  for (const [check, names] of Object.entries(TARGETS)) for (const name of names) if (new RegExp(`^${name}:`, 'm').test(make)) set(check, `make ${name}`);
  if (languages.has('python')) {
    const pytest = /pytest/.test(pyproject) || has(root, 'pytest.ini');
    if (pytest) set('test', 'pytest');
    if (/\[tool\.ruff/.test(pyproject) || has(root, 'ruff.toml')) {
      set('lint', 'ruff check .');
      set('format', 'ruff format --check .');
    }
    if (/\[tool\.black/.test(pyproject)) set('format', 'black --check .');
    if (/\[tool\.mypy/.test(pyproject) || has(root, 'mypy.ini')) set('typecheck', 'mypy .');
    if (/\[tool\.bandit/.test(pyproject) || has(root, '.bandit')) set('static-analysis', 'bandit -r .');
    if (/\[build-system\]/.test(pyproject)) set('build', 'python -m build');
    for (const kind of ['unit', 'integration', 'e2e']) if (pytest && has(root, `tests/${kind}`)) set(kind, `pytest tests/${kind}`);
  }
  if (languages.has('go')) {
    set('format', 'test -z "$(gofmt -l .)"');
    set('test', 'go test ./...');
    set('lint', has(root, '.golangci.yml') || has(root, '.golangci.yaml') ? 'golangci-lint run' : 'go vet ./...');
    set('typecheck', 'go build ./...');
    set('build', 'go build ./...');
  }
  if (languages.has('rust')) {
    set('format', 'cargo fmt --check');
    set('test', 'cargo test');
    set('lint', 'cargo clippy');
    set('typecheck', 'cargo check');
    set('build', 'cargo build');
  }
  return commands;
}

// The project's Node version, for CI jobs: a version file first, then the lowest major of `engines.node`.
function detectNodeVersion(root, pkg) {
  for (const file of ['.nvmrc', '.node-version']) {
    const v = readText(root, file).trim().split('\n')[0].trim().replace(/^v(?=\d)/, '');
    if (v) return v;
  }
  const tool = /^nodejs\s+(\S+)/m.exec(readText(root, '.tool-versions'));
  if (tool) return tool[1];
  const engines = /^\s*(?:>=|\^|~|=)?\s*v?(\d+)(?![\d-])/.exec(pkg?.engines?.node ?? '');
  return engines ? engines[1] : null;
}

export function detect(root) {
  const pkg = readJson(root, 'package.json');
  const deps = { ...(pkg?.dependencies ?? {}), ...(pkg?.devDependencies ?? {}) };
  const pyproject = readText(root, 'pyproject.toml');

  const languages = new Set();
  if (pkg) languages.add(has(root, 'tsconfig.json') || deps.typescript ? 'typescript' : 'javascript');
  if (pyproject || has(root, 'requirements.txt') || has(root, 'setup.py')) languages.add('python');
  if (has(root, 'go.mod')) languages.add('go');
  if (has(root, 'Cargo.toml')) languages.add('rust');
  if (has(root, 'pom.xml') || has(root, 'build.gradle') || has(root, 'build.gradle.kts')) languages.add('java');
  if (has(root, 'Gemfile')) languages.add('ruby');
  if (has(root, 'composer.json')) languages.add('php');

  const lockfiles = [
    ['package-lock.json', 'npm'], ['pnpm-lock.yaml', 'pnpm'], ['yarn.lock', 'yarn'], ['bun.lockb', 'bun'], ['bun.lock', 'bun'],
    ['poetry.lock', 'poetry'], ['uv.lock', 'uv'], ['Pipfile.lock', 'pipenv'], ['go.sum', 'go'], ['Cargo.lock', 'cargo'],
  ];
  const packageManagers = new Set(lockfiles.filter(([f]) => has(root, f)).map(([, m]) => m));

  const testFrameworks = new Set();
  for (const t of ['vitest', 'jest', 'mocha', 'ava', 'playwright', '@playwright/test', 'cypress']) if (deps[t]) testFrameworks.add(t.replace('@playwright/test', 'playwright'));
  if (/node --test/.test(pkg?.scripts?.test ?? '')) testFrameworks.add('node:test');
  if (/pytest/.test(pyproject) || has(root, 'pytest.ini')) testFrameworks.add('pytest');
  if (has(root, 'go.mod')) testFrameworks.add('go test');
  if (has(root, 'Cargo.toml')) testFrameworks.add('cargo test');

  const linters = new Set();
  const typecheckers = new Set();
  walk(root, 0, (rel) => {
    if (/^(\.eslintrc(\..+)?|eslint\.config\.[cm]?js)$/.test(rel)) linters.add('eslint');
    if (/^biome\.jsonc?$/.test(rel)) linters.add('biome');
    if (/^\.golangci\.ya?ml$/.test(rel)) linters.add('golangci-lint');
    if (rel === '.flake8') linters.add('flake8');
  });
  if (/\[tool\.ruff/.test(pyproject) || has(root, 'ruff.toml')) linters.add('ruff');
  if (has(root, 'tsconfig.json')) typecheckers.add('tsc');
  if (/\[tool\.mypy/.test(pyproject) || has(root, 'mypy.ini')) typecheckers.add('mypy');

  const commands = detectCommands(root, { pkg, deps, pyproject, packageManagers, languages });

  const ci = new Set();
  if (has(root, '.github/workflows')) ci.add('github-actions');
  if (has(root, '.gitlab-ci.yml')) ci.add('gitlab-ci');
  if (has(root, '.circleci')) ci.add('circleci');
  if (has(root, 'azure-pipelines.yml')) ci.add('azure-pipelines');
  if (has(root, 'Jenkinsfile')) ci.add('jenkins');

  const monorepo = new Set();
  if (pkg?.workspaces) monorepo.add('npm-workspaces');
  for (const [f, k] of [['pnpm-workspace.yaml', 'pnpm'], ['lerna.json', 'lerna'], ['nx.json', 'nx'], ['turbo.json', 'turbo'], ['go.work', 'go-work']]) if (has(root, f)) monorepo.add(k);

  const hostSignals = {
    'claude-code': ['CLAUDE.md', '.claude'],
    codex: ['.codex'],
    kilo: ['.kilo', 'kilo.json', 'kilo.jsonc'],
    opencode: ['.opencode', 'opencode.json', 'opencode.jsonc'],
    cursor: ['.cursor', '.cursorrules', '.cursorignore'],
    'gemini-cli': ['GEMINI.md', '.gemini'],
    copilot: ['.github/copilot-instructions.md', '.github/agents', '.github/instructions'],
  };
  const hostAgents = Object.keys(hostSignals).filter((h) => hostSignals[h].some((f) => has(root, f)));
  const agentFiles = ['AGENTS.md', 'CLAUDE.md', 'GEMINI.md', '.cursorrules', '.github/copilot-instructions.md'].filter((f) => has(root, f));

  const sensitivePaths = new Set();
  walk(root, 3, (rel, name, isDir) => {
    if (isDir ? /^(secrets?|credentials|\.ssh)$/i.test(name) : /^(\.env(\..+)?|.*\.(pem|key|p12|pfx)|id_(rsa|ed25519|ecdsa)|credentials.*\.json|.*secret.*\.(json|ya?ml))$/i.test(name)) {
      if (!/\.env\.(example|sample|template)$/i.test(name)) sensitivePaths.add(isDir ? `${rel}/` : rel);
    }
  });

  const remote = git(root, ['remote', 'get-url', 'origin']);
  const remoteHost = remote ? (/^(?:https?:\/\/|ssh:\/\/)?(?:[^@/]+@)?([^/:]+)/.exec(remote)?.[1] ?? null) : null;
  const branch = defaultBranch(root);
  const defaultBranchName = branch.name;

  return {
    languages: sorted(languages),
    packageManagers: sorted(packageManagers),
    testFrameworks: sorted(testFrameworks),
    linters: sorted(linters),
    typecheckers: sorted(typecheckers),
    commands,
    nodeVersion: detectNodeVersion(root, pkg),
    ci: sorted(ci),
    monorepo: sorted(monorepo),
    hostAgents,
    agentFiles,
    knowledgeBase: has(root, 'docs/decisions') || has(root, 'docs/facts'),
    specTool: detectSpecTool(root),
    sensitivePaths: sorted(sensitivePaths),
    git: { defaultBranch: defaultBranchName, defaultBranchKnown: branch.known, remoteHost },
  };
}
