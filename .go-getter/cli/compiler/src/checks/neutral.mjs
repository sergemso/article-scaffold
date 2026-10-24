// Guardrail neutral-source-has-no-host-specific-language: src/ content must not name a host agent or its files.
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import path from 'node:path';

export const HOST_TERMS = [
  /\bclaude code\b/i,
  /\bcodex\b/i,
  /\bkilo(?: code)?\b/i,
  /\bopencode\b/i,
  /\bcursor\b(?! position)/i,
  /\bgemini\b/i,
  /\bcopilot\b/i,
  /\bCLAUDE\.md\b/,
  /\bGEMINI\.md\b/,
  /(^|[\s`'"(/])\.(claude|codex|cursor|gemini|opencode|kilo)\//,
];

function files(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).flatMap((n) => {
    const p = path.join(dir, n);
    return statSync(p).isDirectory() ? files(p) : /\.(md|json|toml|ya?ml|txt)$/.test(n) ? [p] : [];
  });
}

export function findHostSpecificLanguage(srcDir) {
  const problems = [];
  for (const file of files(srcDir)) {
    readFileSync(file, 'utf8')
      .split('\n')
      .forEach((line, i) => {
        for (const re of HOST_TERMS) {
          const m = re.exec(line);
          if (m) problems.push(`${file}:${i + 1}: "${m[0].trim()}"`);
        }
      });
  }
  return problems;
}

export default function checkNeutral({ root }) {
  const problems = findHostSpecificLanguage(path.join(root, 'src')).map((p) => path.relative(root, p.split(':')[0]) + p.slice(p.indexOf(':')));
  if (problems.length) {
    console.error('check neutral: host-specific language in neutral source (move it to compiler/adapters or capabilities):');
    for (const p of problems) console.error(`  ${p}`);
    return 1;
  }
  console.log('check neutral: ok');
  return 0;
}
