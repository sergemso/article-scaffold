// Minimal gitignore-style glob matching: `**` crosses directories, `*` and `?` stay within one segment,
// a pattern without "/" matches the basename at any depth, a trailing "/" matches a directory prefix.
export function globToRegExp(pattern) {
  let p = pattern.replace(/^\.\//, '');
  const dirOnly = p.endsWith('/');
  if (dirOnly) p = p.slice(0, -1);
  const anchored = p.includes('/');
  let re = '';
  for (let i = 0; i < p.length; i++) {
    const c = p[i];
    if (c === '*' && p[i + 1] === '*') {
      re += '.*';
      i++;
      if (p[i + 1] === '/') i++;
    } else if (c === '*') re += '[^/]*';
    else if (c === '?') re += '[^/]';
    else re += c.replace(/[.+^${}()|[\]\\]/g, '\\$&');
  }
  const prefix = anchored ? '^' : '(^|/)';
  return new RegExp(`${prefix}${re}${dirOnly ? '(/.*)?$' : '(/.*)?$'}`);
}

export function matchesAny(path, patterns) {
  const normalized = path.replace(/\\/g, '/').replace(/^\.\//, '');
  return patterns.some((p) => globToRegExp(p).test(normalized));
}
