// Issue references (decision 0117): the text a plan step's `Issue:` field, a `Refs:` trailer or a branch name uses to name
// an issue. Nothing here reaches a tracker; a reference is parsed, never resolved.
//   GitHub: `#123`, `owner/repo#123`, `https://github.com/owner/repo/issues/123`
//   Jira:   `PROJ-123`, `https://<host>/browse/PROJ-123`
// `parseRef` returns { tracker, key, text, repo? } or null. `key` is the issue number (GitHub) or the issue key (Jira); `text`
// is the reference as it is written back (`#123`, `owner/repo#123`, `PROJ-123`), the same for a URL and its short form.
const NUMBER = '[1-9][0-9]{0,8}';
const OWNER = '[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})';
const REPO = '[A-Za-z0-9._-]{1,100}';
const JIRA_KEY = '[A-Z][A-Z0-9_]+-[1-9][0-9]{0,8}';

const GITHUB_SHORT = new RegExp(`^(?:(${OWNER}/${REPO}))?#(${NUMBER})$`);
const GITHUB_URL_PATH = new RegExp(`^/(${OWNER}/${REPO})/issues/(${NUMBER})/?$`);
const JIRA_SHORT = new RegExp(`^(${JIRA_KEY})$`);
const JIRA_URL_PATH = new RegExp(`^/browse/(${JIRA_KEY})/?$`);

const github = (repo, number) => ({ tracker: 'github', key: number, text: repo ? `${repo}#${number}` : `#${number}`, ...(repo ? { repo } : {}) });
const jira = (key) => ({ tracker: 'jira', key, text: key });

export function parseRef(value) {
  if (typeof value !== 'string') return null;
  const text = value.trim();
  let m = GITHUB_SHORT.exec(text);
  if (m) return github(m[1], m[2]);
  m = JIRA_SHORT.exec(text);
  if (m) return jira(m[1]);
  if (!text.startsWith('https://') || /\s/.test(text)) return null;
  let url;
  try {
    url = new URL(text);
  } catch {
    return null;
  }
  if (url.username || url.password || url.search || url.hash) return null;
  if (url.hostname === 'github.com') {
    m = GITHUB_URL_PATH.exec(url.pathname);
    return m ? github(m[1], m[2]) : null;
  }
  m = JIRA_URL_PATH.exec(url.pathname);
  return m ? jira(m[1]) : null;
}

// What makes two references the same issue: the tracker, the repository where it is written and the key.
export const refId = (ref) => `${ref.tracker}:${ref.repo ?? ''}#${ref.key}`;
