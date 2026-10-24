// Loads and validates compiler/capabilities/<host>.json (decision 0021, fact 0009).
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { validate } from './schema.mjs';

export const HOSTS = ['claude-code', 'codex', 'kilo', 'opencode', 'cursor', 'gemini-cli', 'copilot'];

export function loadSchema(root) {
  return JSON.parse(readFileSync(path.join(root, 'compiler/schemas/capabilities.schema.json'), 'utf8'));
}

export function validateCapabilities(schema, manifest) {
  return validate(schema, manifest);
}

export function loadCapabilities(root) {
  const schema = loadSchema(root);
  const dir = path.join(root, 'compiler/capabilities');
  const result = {};
  for (const file of readdirSync(dir).filter((f) => f.endsWith('.json'))) {
    const manifest = JSON.parse(readFileSync(path.join(dir, file), 'utf8'));
    const errors = validateCapabilities(schema, manifest);
    if (errors.length) throw new Error(`${file}: ${errors.join('; ')}`);
    if (`${manifest.host}.json` !== file) throw new Error(`${file}: host "${manifest.host}" does not match file name`);
    result[manifest.host] = manifest;
  }
  return result;
}
