// Guardrail no-runtime-dependencies: package.json must not declare runtime dependencies.
import { readFileSync } from 'node:fs';
import path from 'node:path';

export function findRuntimeDependencies(pkg) {
  return Object.keys(pkg.dependencies ?? {});
}

export default function checkDeps({ root }) {
  const pkg = JSON.parse(readFileSync(path.join(root, 'package.json'), 'utf8'));
  const deps = findRuntimeDependencies(pkg);
  if (deps.length > 0) {
    console.error(`check deps: runtime dependencies are not allowed: ${deps.join(', ')}`);
    return 1;
  }
  console.log('check deps: ok (no runtime dependencies)');
  return 0;
}
