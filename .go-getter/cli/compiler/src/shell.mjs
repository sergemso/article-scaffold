// Reading a whole shell command for the paths it really names (decision 0126), so a restricted path mentioned as text (a commit
// message, an `echo`, a heredoc body that is only written to a file) is not a use of it, while a real access is still seen:
// an argument, a redirect target, the body of `sh -c`, a heredoc fed to a shell, a string literal in the inline code of an
// interpreter, the inside of a command substitution (also inside double quotes and inside an unquoted heredoc).
//
// `shellOperands` returns null when the command cannot be read with confidence (an unterminated quote, a heredoc without a
// body, nesting that is too deep), and the caller then falls back to scanning the whole text: the conservative reading.
//
// What no reading of text can see is a script that opens a file itself (`node app.js` with `app.js` reading a dotenv file); that
// is covered by the approval of the command and its code, and by scrubbing its output (decision 0126).

const SHELLS = new Set(['sh', 'bash', 'zsh', 'dash', 'ksh', 'ash']);
const INTERPRETERS = new Set(['python', 'python3', 'python2', 'node', 'nodejs', 'deno', 'bun', 'ruby', 'perl', 'php', 'lua', 'Rscript', 'osascript']);
const CODE_FLAGS = new Set(['-c', '-e', '-p', '-r', '--eval', '--print', '-E']);
const TEXT_COMMANDS = new Set(['echo', 'printf']);
const WRAPPERS = new Set(['env', 'sudo', 'nohup', 'time', 'exec', 'command', 'builtin', 'xargs', 'nice', 'stdbuf', 'timeout', 'doas', 'setsid']);
const ASSIGNMENT = /^[A-Za-z_][A-Za-z0-9_]*=/;
const MAX_DEPTH = 6;

class Unreadable extends Error {}

const fresh = () => ({ words: [], redirects: [], heredocs: [], subs: [] });

// --- the lexer -------------------------------------------------------------------------------------------------------------

// Reads simple commands from `text` starting at `start`; with `stop` (')' or a backtick) it reads the inside of a substitution and
// returns after the matching closer. Each command is { words, redirects, heredocs: [{ body, quoted }], subs: [[command]] }:
// `words` are its program and arguments with quotes resolved, `redirects` the targets of `<` `>` `>>` `&>`, `subs` what its
// command substitutions contain. Returns { commands, next }.
function lex(text, start = 0, stop = null, depth = 0) {
  if (depth > MAX_DEPTH) throw new Unreadable('nested too deeply');
  const commands = [];
  let cur = fresh();
  let word = null; // the word being built, or null between words
  let target = null; // 'file' when the next word is a redirect target, 'skip' when it is a descriptor or a here-string
  let pending = []; // heredocs whose bodies follow the next newline
  let parens = 0;
  let i = start;

  const flush = () => {
    if (word === null) return;
    if (target === 'file') cur.redirects.push(word);
    else if (target !== 'skip') cur.words.push(word);
    word = null;
    target = null;
  };
  const endCommand = () => {
    flush();
    if (cur.words.length || cur.redirects.length || cur.heredocs.length || cur.subs.length) commands.push(cur);
    cur = fresh();
  };
  const add = (s) => {
    word = (word ?? '') + s;
  };
  const substitution = (from, closer) => {
    const inner = lex(text, from, closer, depth + 1);
    cur.subs.push(inner.commands);
    return inner.next;
  };
  const readDouble = (from) => {
    let j = from;
    let value = '';
    while (j < text.length && text[j] !== '"') {
      const c = text[j];
      if (c === '\\' && j + 1 < text.length) {
        value += text[j + 1];
        j += 2;
      } else if (c === '$' && text[j + 1] === '(') j = substitution(j + 2, ')');
      else if (c === '`') j = substitution(j + 1, '`');
      else {
        value += c;
        j++;
      }
    }
    if (j >= text.length) throw new Unreadable('an unterminated quote');
    add(value);
    return j + 1;
  };
  const readHeredocBodies = () => {
    for (const h of pending) {
      const lines = [];
      for (;;) {
        if (i >= text.length) throw new Unreadable('an unterminated heredoc');
        const eol = text.indexOf('\n', i);
        const line = eol < 0 ? text.slice(i) : text.slice(i, eol);
        i = eol < 0 ? text.length : eol + 1;
        if ((h.stripTabs ? line.replace(/^\t+/, '') : line) === h.delimiter) break;
        lines.push(line);
        if (eol < 0) throw new Unreadable('an unterminated heredoc');
      }
      h.command.heredocs.push({ body: lines.join('\n'), quoted: h.quoted });
    }
    pending = [];
  };
  const readDelimiter = () => {
    while (text[i] === ' ' || text[i] === '\t') i++;
    let delimiter = '';
    let quoted = false;
    while (i < text.length && !' \t\n;|&<>()'.includes(text[i])) {
      const c = text[i];
      if (c === "'" || c === '"') {
        const close = text.indexOf(c, i + 1);
        if (close < 0) throw new Unreadable('an unterminated quote');
        delimiter += text.slice(i + 1, close);
        i = close + 1;
        quoted = true;
      } else if (c === '\\') {
        delimiter += text[i + 1] ?? '';
        i += 2;
        quoted = true;
      } else {
        delimiter += c;
        i++;
      }
    }
    if (!delimiter) throw new Unreadable('a heredoc with no delimiter');
    return { delimiter, quoted };
  };

  while (i < text.length) {
    const ch = text[i];
    if (stop && ch === stop && parens === 0) {
      endCommand();
      if (pending.length) throw new Unreadable('a heredoc without a body');
      return { commands, next: i + 1 };
    }
    if (ch === "'") {
      const close = text.indexOf("'", i + 1);
      if (close < 0) throw new Unreadable('an unterminated quote');
      add(text.slice(i + 1, close));
      i = close + 1;
    } else if (ch === '"') {
      i = readDouble(i + 1);
    } else if (ch === '\\') {
      if (i + 1 >= text.length) throw new Unreadable('a trailing backslash');
      if (text[i + 1] !== '\n') add(text[i + 1]);
      i += 2;
    } else if (ch === '$' && text[i + 1] === '(') {
      i = substitution(i + 2, ')');
      add('');
    } else if (ch === '`') {
      i = substitution(i + 1, '`');
      add('');
    } else if (ch === ' ' || ch === '\t') {
      flush();
      i++;
    } else if (ch === '\n') {
      endCommand();
      i++;
      if (pending.length) readHeredocBodies();
    } else if (ch === '#' && word === null) {
      const eol = text.indexOf('\n', i);
      i = eol < 0 ? text.length : eol;
    } else if (ch === '(') {
      endCommand();
      parens++;
      i++;
    } else if (ch === ')') {
      endCommand();
      if (parens > 0) parens--;
      else if (stop === null) throw new Unreadable('an unmatched )');
      i++;
    } else if (ch === ';') {
      endCommand();
      i++;
    } else if (ch === '&' && text[i + 1] === '>') {
      flush();
      i += text[i + 2] === '>' ? 3 : 2;
      target = 'file';
    } else if (ch === '|' || ch === '&') {
      endCommand();
      i += text[i + 1] === ch ? 2 : 1;
    } else if (ch === '<' || ch === '>') {
      // a file descriptor glued in front (`2>file`) belongs to the operator
      if (word !== null && /^[0-9]+$/.test(word) && target === null) word = null;
      else flush();
      if (text.startsWith('<<<', i)) {
        i += 3;
        target = 'skip'; // a here-string is text fed to the command
      } else if (text.startsWith('<<', i)) {
        i += 2;
        const stripTabs = text[i] === '-';
        if (stripTabs) i++;
        const { delimiter, quoted } = readDelimiter();
        pending.push({ delimiter, quoted, stripTabs, command: cur });
      } else if (text[i + 1] === '(') {
        i = substitution(i + 2, ')'); // process substitution
      } else {
        i += text.startsWith('>>', i) || text.startsWith('>|', i) || text.startsWith('>&', i) || text.startsWith('<&', i) ? 2 : 1;
        target = 'file';
      }
    } else {
      add(ch);
      i++;
    }
  }
  if (stop) throw new Unreadable('an unterminated substitution');
  endCommand();
  if (pending.length) throw new Unreadable('a heredoc without a body');
  return { commands, next: i };
}

// --- reading what the commands name ----------------------------------------------------------------------------------------

const base = (word) => word.split('/').pop();

// The command name of `words` after wrappers (`env A=b`, `sudo`, `xargs`, ...) and leading assignments, and the words after it.
export function commandOf(words) {
  let k = 0;
  while (k < words.length) {
    if (ASSIGNMENT.test(words[k])) k++;
    else if (WRAPPERS.has(base(words[k]))) {
      k++;
      while (k < words.length && (/^-/.test(words[k]) || ASSIGNMENT.test(words[k]) || /^[0-9]+(\.[0-9]+)?[smhd]?$/.test(words[k]))) k++;
    } else break;
  }
  return { name: k < words.length ? base(words[k]) : null, args: words.slice(k + 1) };
}

// The string literals of a program's source (single, double and backtick quoted), unescaped enough to be compared with a path.
export function stringLiterals(code) {
  const out = [];
  const re = /'((?:[^'\\\n]|\\.)*)'|"((?:[^"\\\n]|\\.)*)"|`((?:[^`\\]|\\.)*)`/g;
  for (const m of code.matchAll(re)) out.push((m[1] ?? m[2] ?? m[3]).replace(/\\(.)/g, '$1'));
  return out;
}

// A literal as a path candidate, and without the open-mode prefix some languages put in it (`"<file"`, `">>file"`, `"+<file"`).
const literalCandidates = (code) => stringLiterals(code).flatMap((lit) => {
  const bare = lit.replace(/^[\s<>+|&]+/, '');
  return bare !== lit && bare ? [lit, bare] : [lit];
});

// The command substitutions inside an unquoted heredoc body, which the shell runs.
function bodySubstitutions(body) {
  const found = [];
  for (let i = 0; i < body.length; i++) {
    if (body[i] === '\\') i++;
    else if (body[i] === '$' && body[i + 1] === '(') {
      const r = lex(body, i + 2, ')');
      found.push(r.commands);
      i = r.next - 1;
    } else if (body[i] === '`') {
      const r = lex(body, i + 1, '`');
      found.push(r.commands);
      i = r.next - 1;
    }
  }
  return found;
}

// Adds to `out` every string of `commands` that names a path in earnest. `top` is whether these are commands a person typed
// (so `echo` arguments are text); a command substitution's output becomes an argument, so nothing inside it is text.
function collect(commands, out, depth, top) {
  if (depth > MAX_DEPTH) throw new Unreadable('nested too deeply');
  const collectText = (text, asTop) => collect(lex(text, 0, null, depth + 1).commands, out, depth + 1, asTop);
  for (const cmd of commands) {
    const { name, args } = commandOf(cmd.words);
    const textOnly = top && name !== null && TEXT_COMMANDS.has(name);
    if (!textOnly) {
      for (const w of cmd.words) {
        out.push(w);
        if (w.includes('=')) out.push(w.slice(w.indexOf('=') + 1));
      }
    }
    for (const target of cmd.redirects) out.push(target);
    // inline code: a shell's -c body is a command line; an interpreter's is a program. A program run after `--` (as in
    // `go-getter secret run --from f -- sh -c '...'`) is read the same way.
    const inspect = (program, programArgs) => {
      for (let k = 0; k < programArgs.length - 1; k++) {
        const flag = programArgs[k];
        if (SHELLS.has(program) && /^-[A-Za-z]*c[A-Za-z]*$/.test(flag)) collectText(programArgs[k + 1], true);
        else if (INTERPRETERS.has(program) && CODE_FLAGS.has(flag)) out.push(...literalCandidates(programArgs[k + 1]));
      }
      if (program === 'eval') collectText(programArgs.join(' '), true);
    };
    inspect(name, args);
    const dash = cmd.words.indexOf('--');
    if (dash >= 0) {
      const inner = commandOf(cmd.words.slice(dash + 1));
      if (inner.name) inspect(inner.name, inner.args);
    }
    // a heredoc fed to a shell is a script, to an interpreter a program; to anything else it is text, except that an unquoted
    // body still runs its command substitutions
    for (const h of cmd.heredocs) {
      if (SHELLS.has(name)) collectText(h.body, true);
      else if (INTERPRETERS.has(name)) out.push(...literalCandidates(h.body));
      else if (!h.quoted) for (const subs of bodySubstitutions(h.body)) collect(subs, out, depth + 1, false);
    }
    for (const subs of cmd.subs) collect(subs, out, depth + 1, false);
  }
}

// The strings of `command` that name a path in earnest, or null when it cannot be read (scan the whole text then).
export function shellOperands(command) {
  try {
    const out = [];
    collect(lex(String(command)).commands, out, 0, true);
    return out.filter((s) => s !== '');
  } catch (err) {
    if (err instanceof Unreadable) return null;
    throw err;
  }
}

// The words of each top-level command of `text` (a script line, an npm script), or null when it cannot be read.
export function commandWords(text) {
  try {
    return lex(String(text)).commands.map((c) => c.words).filter((w) => w.length);
  } catch (err) {
    if (err instanceof Unreadable) return null;
    throw err;
  }
}
