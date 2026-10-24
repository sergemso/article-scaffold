// Zero-dependency parser/serializer for the YAML subset used in Markdown frontmatter:
// scalars, quoted strings, inline lists/maps ([a, b], {k: v}), block lists and maps,
// lists of maps, `>`/`|` block scalars, plain multi-line scalars and `#` comments.
// Dates and versions stay strings; only plain integers/decimals become numbers.

export function parseFrontmatter(text) {
  const match = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)([\s\S]*)$/.exec(text);
  if (!match) return { data: {}, body: text, hasFrontmatter: false };
  return { data: parseYaml(match[1]), body: match[2], hasFrontmatter: true };
}

export function stringifyFrontmatter(data, body = '') {
  return `---\n${stringifyYaml(data)}---\n${body}`;
}

// ---------- parsing ----------

export function parseYaml(source) {
  const lines = source
    .split(/\r?\n/)
    .map((raw, i) => ({ raw, no: i + 1, indent: raw.length - raw.trimStart().length, text: stripComment(raw).trimEnd() }))
    .map((l) => ({ ...l, text: l.text.trimStart() }));
  const state = { lines, pos: 0, endsWithNewline: /\n$/.test(source) };
  skipBlank(state);
  if (state.pos >= lines.length) return {};
  const value = parseBlock(state, lines[state.pos].indent);
  skipBlank(state);
  if (state.pos < lines.length) fail(lines[state.pos], 'unexpected content');
  return value;
}

function fail(line, message) {
  throw new SyntaxError(`frontmatter line ${line.no}: ${message}: ${line.raw.trim()}`);
}

function stripComment(raw) {
  let quote = null;
  for (let i = 0; i < raw.length; i++) {
    const c = raw[i];
    if (quote) {
      if (c === quote && !(quote === '"' && raw[i - 1] === '\\')) quote = null;
    } else if (c === '"' || c === "'") {
      if (i === 0 || /[\s[{,:]/.test(raw[i - 1])) quote = c;
    } else if (c === '#' && (i === 0 || /\s/.test(raw[i - 1]))) {
      return raw.slice(0, i);
    }
  }
  return raw;
}

function skipBlank(state) {
  while (state.pos < state.lines.length && state.lines[state.pos].text === '') state.pos++;
}

function isListItem(text) {
  return text === '-' || text.startsWith('- ');
}

function splitKey(text) {
  // key: value — split at the first ': ' or a trailing ':' outside quotes/brackets.
  let quote = null;
  let depth = 0;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quote) {
      if (c === quote) quote = null;
      continue;
    }
    if (c === '"' || c === "'") quote = c;
    else if (c === '[' || c === '{') depth++;
    else if (c === ']' || c === '}') depth--;
    else if (c === ':' && depth === 0 && (i === text.length - 1 || text[i + 1] === ' ')) {
      const key = text.slice(0, i).trim();
      if (!key || /^[[{]/.test(key)) return null;
      return { key: unquote(key), rest: text.slice(i + 1).trim() };
    }
  }
  return null;
}

function unquote(key) {
  return /^(["']).*\1$/.test(key) ? parseScalar(key) : key;
}

function parseBlock(state, indent) {
  const line = state.lines[state.pos];
  return isListItem(line.text) ? parseList(state, indent) : parseMap(state, indent);
}

function parseMap(state, indent) {
  const result = {};
  while (true) {
    skipBlank(state);
    const line = state.lines[state.pos];
    if (!line || line.indent < indent) return result;
    if (line.indent > indent) fail(line, 'unexpected indentation');
    if (isListItem(line.text)) return result;
    const kv = splitKey(line.text);
    if (!kv) fail(line, 'expected "key: value"');
    state.pos++;
    if (Object.hasOwn(result, kv.key)) fail(line, `duplicate key "${kv.key}"`);
    result[kv.key] = parseValue(state, kv.rest, indent, line);
  }
}

function parseList(state, indent) {
  const result = [];
  while (true) {
    skipBlank(state);
    const line = state.lines[state.pos];
    if (!line || line.indent < indent || !isListItem(line.text) || line.indent > indent) return result;
    const rest = line.text === '-' ? '' : line.text.slice(2).trim();
    state.pos++;
    if (rest === '') {
      skipBlank(state);
      const next = state.lines[state.pos];
      result.push(next && next.indent > indent ? parseBlock(state, next.indent) : null);
      continue;
    }
    const kv = /^[[{"']/.test(rest) ? null : splitKey(rest);
    if (kv) {
      // A map starting on the item line: its keys sit at the column after "- ".
      const column = indent + (line.text.length - line.text.slice(1).trimStart().length);
      const item = { [kv.key]: parseValue(state, kv.rest, column, line) };
      skipBlank(state);
      const next = state.lines[state.pos];
      if (next && next.indent === column && !isListItem(next.text)) {
        Object.assign(item, mergeUnique(item, parseMap(state, column), line));
      }
      result.push(item);
    } else {
      result.push(parseInlineValue(rest, line));
    }
  }
}

function mergeUnique(target, extra, line) {
  for (const k of Object.keys(extra)) if (Object.hasOwn(target, k)) fail(line, `duplicate key "${k}"`);
  return extra;
}

function parseValue(state, rest, indent, line) {
  if (rest === '') {
    skipBlank(state);
    const next = state.lines[state.pos];
    if (next && (next.indent > indent || (next.indent === indent && isListItem(next.text)))) {
      return parseBlock(state, next.indent);
    }
    return null;
  }
  if (/^[>|][+-]?$/.test(rest)) return parseBlockScalar(state, indent, rest);
  if (/^[[{"']/.test(rest)) return parseInlineValue(rest, line);
  // Plain scalar, possibly continued on more-indented lines.
  const parts = [rest];
  while (state.pos < state.lines.length) {
    const next = state.lines[state.pos];
    if (next.text === '' || next.indent <= indent) break;
    if (isListItem(next.text) || splitKey(next.text)) fail(next, 'unexpected indentation');
    parts.push(next.text);
    state.pos++;
  }
  return parts.length > 1 ? parts.join(' ') : parseScalar(rest);
}

function parseBlockScalar(state, indent, header) {
  const literal = header[0] === '|';
  const chomp = header[1] ?? '';
  const raw = [];
  let blockIndent = null;
  while (state.pos < state.lines.length) {
    const line = state.lines[state.pos];
    if (line.raw.trim() === '') {
      raw.push('');
      state.pos++;
      continue;
    }
    if (line.indent <= indent) break;
    blockIndent ??= line.indent;
    raw.push(line.raw.slice(blockIndent));
    state.pos++;
  }
  while (raw.length && raw[raw.length - 1] === '') raw.pop();
  let text;
  if (literal) text = raw.join('\n');
  else {
    // Folding: single newlines become spaces; each blank line becomes one newline.
    text = '';
    raw.forEach((l, i) => {
      if (l === '') text += '\n';
      else if (i === 0 || raw[i - 1] === '') text += l;
      else text += ' ' + l;
    });
  }
  // "Clip" keeps one final newline, except when the scalar ends the input without a line break.
  const atEnd = state.lines.slice(state.pos).every((l) => l.text === '');
  return chomp === '-' || (atEnd && !state.endsWithNewline) ? text : `${text}\n`;
}

function parseInlineValue(text, line) {
  const parser = { s: text, i: 0, line };
  const value = parseFlow(parser);
  skipSpaces(parser);
  if (parser.i < parser.s.length) fail(line, 'trailing characters after value');
  return value;
}

function skipSpaces(p) {
  while (p.i < p.s.length && p.s[p.i] === ' ') p.i++;
}

function parseFlow(p) {
  skipSpaces(p);
  const c = p.s[p.i];
  if (c === '[') {
    p.i++;
    const items = [];
    skipSpaces(p);
    if (p.s[p.i] === ']') {
      p.i++;
      return items;
    }
    while (true) {
      items.push(parseFlow(p));
      skipSpaces(p);
      if (p.s[p.i] === ',') p.i++;
      else if (p.s[p.i] === ']') {
        p.i++;
        return items;
      } else fail(p.line, 'expected "," or "]"');
    }
  }
  if (c === '{') {
    p.i++;
    const obj = {};
    skipSpaces(p);
    if (p.s[p.i] === '}') {
      p.i++;
      return obj;
    }
    while (true) {
      skipSpaces(p);
      const key = readFlowToken(p, ':');
      if (p.s[p.i] !== ':') fail(p.line, 'expected ":" in flow map');
      p.i++;
      const k = unquote(key.trim());
      if (Object.hasOwn(obj, k)) fail(p.line, `duplicate key "${k}"`);
      obj[k] = parseFlow(p);
      skipSpaces(p);
      if (p.s[p.i] === ',') p.i++;
      else if (p.s[p.i] === '}') {
        p.i++;
        return obj;
      } else fail(p.line, 'expected "," or "}"');
    }
  }
  if (c === '"' || c === "'") {
    const start = p.i;
    p.i++;
    while (p.i < p.s.length) {
      if (p.s[p.i] === '\\' && c === '"') p.i += 2;
      else if (p.s[p.i] === c) {
        if (c === "'" && p.s[p.i + 1] === "'") p.i += 2;
        else break;
      } else p.i++;
    }
    if (p.i >= p.s.length) fail(p.line, 'unterminated string');
    p.i++;
    return parseScalar(p.s.slice(start, p.i));
  }
  return parseScalar(readFlowToken(p, ',]}').trim());
}

function readFlowToken(p, stops) {
  const start = p.i;
  while (p.i < p.s.length && !stops.includes(p.s[p.i])) p.i++;
  return p.s.slice(start, p.i);
}

export function parseScalar(token) {
  const t = token.trim();
  if (t.startsWith('"') && t.endsWith('"') && t.length >= 2) {
    return t
      .slice(1, -1)
      .replace(/\\(["\\/nt])/g, (_, ch) => ({ n: '\n', t: '\t' })[ch] ?? ch);
  }
  if (t.startsWith("'") && t.endsWith("'") && t.length >= 2) return t.slice(1, -1).replace(/''/g, "'");
  if (t === '' || t === '~' || t === 'null') return null;
  if (t === 'true') return true;
  if (t === 'false') return false;
  if (/^-?\d+(\.\d+)?$/.test(t)) return Number(t);
  return t;
}

// ---------- serializing ----------

export function stringifyYaml(data, indent = 0) {
  const pad = ' '.repeat(indent);
  let out = '';
  for (const [key, value] of Object.entries(data)) {
    if (isPlainList(value)) out += `${pad}${key}: ${inlineList(value)}\n`;
    else if (Array.isArray(value)) out += `${pad}${key}:\n${blockList(value, indent + 2)}`;
    else if (value !== null && typeof value === 'object') out += `${pad}${key}:\n${stringifyYaml(value, indent + 2)}`;
    else out += `${pad}${key}: ${scalar(value)}\n`;
  }
  return out;
}

function isPlainList(value) {
  return Array.isArray(value) && value.every((v) => v === null || typeof v !== 'object');
}

function inlineList(list) {
  return `[${list.map((v) => scalar(v, true)).join(', ')}]`;
}

function blockList(list, indent) {
  const pad = ' '.repeat(indent);
  return list
    .map((item) => {
      if (item !== null && typeof item === 'object' && !Array.isArray(item)) {
        const body = stringifyYaml(item, indent + 2);
        return `${pad}- ${body.slice(indent + 2)}`;
      }
      if (Array.isArray(item)) return `${pad}- ${inlineList(item)}\n`;
      return `${pad}- ${scalar(item)}\n`;
    })
    .join('');
}

function scalar(value, inFlow = false) {
  if (value === null || value === undefined) return 'null';
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  const s = String(value);
  const needsQuotes =
    s === '' ||
    s !== s.trim() ||
    /^[-?:,[\]{}#&*!|>'"%@`]/.test(s) ||
    /: |\s#|\n/.test(s) ||
    s.endsWith(':') ||
    (inFlow && /[,[\]{}]/.test(s)) ||
    parseScalar(s) !== s;
  return needsQuotes ? JSON.stringify(s) : s;
}
