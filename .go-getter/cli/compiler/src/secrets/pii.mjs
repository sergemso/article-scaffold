// PII detectors for tool-output masking (decision 0106). Checksum-validated types keep false positives low; the
// locale-bound ones (phone, national id) are opt-in. Heuristic, like every hook layer: a format not listed is missed.
// No dependencies (guardrail no-runtime-dependencies).

export const DEFAULT_CLASSES = ['email', 'card', 'iban'];
export const ALL_CLASSES = [...DEFAULT_CLASSES, 'phone', 'national-id'];

const digitsOf = (s) => s.replace(/\D/g, '');

// Luhn: from the right, double every second digit, subtract 9 above 9; the sum is a multiple of 10.
export function luhn(digits) {
  let sum = 0;
  for (let i = 0; i < digits.length; i++) {
    let d = Number(digits[digits.length - 1 - i]);
    if (i % 2 === 1) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    sum += d;
  }
  return digits.length > 0 && sum % 10 === 0;
}

// Issuer prefix and length, so a long number that merely passes Luhn (a 13-digit epoch in milliseconds does one time in
// ten) is not a card.
const ISSUERS = [
  { prefix: /^4/, lengths: [13, 16, 19] }, // Visa
  { prefix: /^(?:5[1-5]|2(?:2[2-9][1-9]|2[3-9]\d|[3-6]\d\d|7[01]\d|720))/, lengths: [16] }, // Mastercard
  { prefix: /^3[47]/, lengths: [15] }, // American Express
  { prefix: /^(?:6011|65|64[4-9])/, lengths: [16, 17, 18, 19] }, // Discover
  { prefix: /^(?:36|30[0-5]|3095)/, lengths: [14, 15, 16, 17, 18, 19] }, // Diners Club
  { prefix: /^35(?:2[89]|[3-8]\d)/, lengths: [16, 17, 18, 19] }, // JCB
];
const isCard = (digits) => luhn(digits) && ISSUERS.some((i) => i.prefix.test(digits) && i.lengths.includes(digits.length));

// IBAN length by country; mod 97 of the rearranged number must be 1.
const IBAN_LENGTH = {
  AD: 24, AE: 23, AL: 28, AT: 20, AZ: 28, BA: 20, BE: 16, BG: 22, BH: 22, BR: 29, BY: 28, CH: 21, CR: 22, CY: 28, CZ: 24,
  DE: 22, DK: 18, DO: 28, EE: 20, EG: 29, ES: 24, FI: 18, FO: 18, FR: 27, GB: 22, GE: 22, GI: 23, GL: 18, GR: 27, GT: 28,
  HR: 21, HU: 28, IE: 22, IL: 23, IQ: 23, IS: 26, IT: 27, JO: 30, KW: 30, KZ: 20, LB: 28, LC: 32, LI: 21, LT: 20, LU: 20,
  LV: 21, MC: 27, MD: 24, ME: 22, MK: 19, MR: 27, MT: 31, MU: 30, NL: 18, NO: 15, PK: 24, PL: 28, PS: 29, PT: 25, QA: 29,
  RO: 24, RS: 22, SA: 24, SE: 24, SI: 19, SK: 24, SM: 27, TN: 24, TR: 26, UA: 29, VA: 22, VG: 24, XK: 20,
};
export function isIban(compact) {
  if (!/^[A-Z]{2}\d{2}[A-Z0-9]+$/.test(compact) || IBAN_LENGTH[compact.slice(0, 2)] !== compact.length) return false;
  const rearranged = compact.slice(4) + compact.slice(0, 4);
  let remainder = 0;
  for (const ch of rearranged) {
    const v = /\d/.test(ch) ? ch : String(ch.charCodeAt(0) - 55);
    for (const d of v) remainder = (remainder * 10 + Number(d)) % 97;
  }
  return remainder === 1;
}

const EMAIL = /(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}(?![A-Za-z0-9-])/g;
const CARD = /(?<![\d-])\d(?:[ -]?\d){12,18}(?![\d-])/g;
const IBAN = /(?<![A-Za-z0-9])[A-Z]{2}\d{2}(?: ?[A-Z0-9]{1,4}){2,8}(?![A-Za-z0-9])/g;
const PHONE = /(?<![\w+])\+\d(?:[ .()-]{0,2}\d){7,14}(?!\d)/g;
const SSN = /(?<![\d-])(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}(?![\d-])/g;

// Emails in `text`, leaving out git remotes (`git@host.example:org/repo`, `ssh://git@host.example/org/repo`), which are not people.
function emails(text) {
  const out = [];
  for (const m of text.matchAll(EMAIL)) {
    const next = text[m.index + m[0].length];
    const after = text[m.index + m[0].length + 1];
    if (next === ':' && after !== undefined && !/\s/.test(after)) continue;
    if (next === '/') continue; // `ssh://git@host.example/org/repo`
    out.push({ kind: 'email', index: m.index, length: m[0].length });
  }
  return out;
}

function ibans(text) {
  const out = [];
  for (const m of text.matchAll(IBAN)) {
    const compact = m[0].replace(/ /g, '');
    // A match may swallow trailing words ("DE89 3704 0044 0532 0130 00 and"): shrink to the longest valid prefix.
    for (let len = compact.length; len >= 15; len--) {
      if (isIban(compact.slice(0, len))) {
        let used = 0;
        let seen = 0;
        while (seen < len) if (m[0][used++] !== ' ') seen++;
        out.push({ kind: 'iban', index: m.index, length: used });
        break;
      }
    }
  }
  return out;
}

const cards = (text) => [...text.matchAll(CARD)].filter((m) => isCard(digitsOf(m[0]))).map((m) => ({ kind: 'card', index: m.index, length: m[0].length }));
const phones = (text) => [...text.matchAll(PHONE)].filter((m) => digitsOf(m[0]).length >= 8 && digitsOf(m[0]).length <= 15).map((m) => ({ kind: 'phone', index: m.index, length: m[0].length }));
const nationalIds = (text) => [...text.matchAll(SSN)].map((m) => ({ kind: 'national-id', index: m.index, length: m[0].length }));

const FINDERS = { iban: ibans, card: cards, email: emails, 'national-id': nationalIds, phone: phones };

// PII in `text` as non-overlapping [{ kind, index, length }], in order. `classes` picks the types (default: email, card,
// iban); where two overlap the one checked first wins: iban, card, email, national-id, phone.
export function piiFindings(text, { classes = DEFAULT_CLASSES } = {}) {
  const found = [];
  const overlaps = (a, b) => a.index < b.index + b.length && b.index < a.index + a.length;
  for (const kind of Object.keys(FINDERS)) {
    if (!classes.includes(kind)) continue;
    for (const f of FINDERS[kind](text)) if (!found.some((g) => overlaps(f, g))) found.push(f);
  }
  return found.sort((a, b) => a.index - b.index);
}
