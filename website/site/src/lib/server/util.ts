/* Time, hashing and random values for the server. */
import { env } from 'cloudflare:workers';

export const now = () => new Date().toISOString();
export const ago = (ms: number) => new Date(Date.now() - ms).toISOString();
export const later = (ms: number) => new Date(Date.now() + ms).toISOString();
export const MIN = 60_000, HOUR = 3_600_000, DAY = 86_400_000;

/* Plans run by the calendar day in India. '2026-09-26' */
export const todayIST = () => new Date(Date.now() + 5.5 * HOUR).toISOString().slice(0, 10);
export const istDay = (iso: string) => new Date(Date.parse(iso) + 5.5 * HOUR).toISOString().slice(0, 10);

/* A day n days on: plusDays('2026-10-01', 15) → '2026-10-16'. */
export const plusDays = (day: string, n: number) => new Date(Date.parse(day) + n * DAY).toISOString().slice(0, 10);

/* The same day a year on (29 Feb → 28 Feb). */
export function plusYear(day: string) {
  const [y, m, d] = day.split('-');
  return `${+y + 1}-${m}-${m === '02' && d === '29' ? '28' : d}`;
}

/* The financial year a day falls in: '26-27' for 1 Apr 2026 to 31 Mar 2027. */
export function fy(day: string) {
  const y = +day.slice(2, 4), m = +day.slice(5, 7);
  const s = m >= 4 ? y : y - 1;
  return `${String(s).padStart(2, '0')}-${String(s + 1).padStart(2, '0')}`;
}

const enc = new TextEncoder();
const hex = (b: ArrayBuffer) => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('');

export const sha256 = async (s: string) => hex(await crypto.subtle.digest('SHA-256', enc.encode(s)));

export async function hmac(secret: string, msg: string) {
  const key = await crypto.subtle.importKey('raw', enc.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return hex(await crypto.subtle.sign('HMAC', key, enc.encode(msg)));
}

/* Constant-time string comparison. */
export function same(a: string, b: string) {
  const x = enc.encode(a), y = enc.encode(b);
  if (x.length !== y.length) return false;
  let d = 0;
  for (let i = 0; i < x.length; i++) d |= x[i] ^ y[i];
  return d === 0;
}

/* 32 random bytes, URL-safe: session cookies and app tokens. */
export function token() {
  const b = crypto.getRandomValues(new Uint8Array(32));
  return btoa(String.fromCharCode(...b)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/* A 6-digit code, uniform over 000000–999999. */
export function sixDigits() {
  const buf = new Uint32Array(1);
  do crypto.getRandomValues(buf); while (buf[0] >= 4_294_000_000);
  return String(buf[0] % 1_000_000).padStart(6, '0');
}

export const validEmail = (v: string) => v.length <= 254 && /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(v);

/* Mail services where a+anything@ reaches a@ (and, for Gmail, dots in the name are ignored): one inbox there is one
   account here, so an alias can't make a second account. Other domains are kept as typed: we can't know. */
const PLUS = new Set(['gmail.com', 'googlemail.com', 'outlook.com', 'hotmail.com', 'live.com', 'msn.com', 'icloud.com', 'me.com', 'mac.com', 'proton.me', 'protonmail.com', 'pm.me']);

/* The email as we store it: lower case, aliases removed ('R.K.Mehta+tax@Gmail.com' → 'rkmehta@gmail.com'). null if it isn't an email. */
export function cleanEmail(v: unknown): string | null {
  const e = typeof v === 'string' ? v.trim().toLowerCase() : '';
  if (!validEmail(e)) return null;
  let [name, domain] = [e.slice(0, e.lastIndexOf('@')), e.slice(e.lastIndexOf('@') + 1)];
  if (domain === 'googlemail.com') domain = 'gmail.com';
  if (PLUS.has(domain)) name = name.split('+')[0];
  if (domain === 'gmail.com') name = name.replace(/\./g, '');
  return name ? `${name}@${domain}` : null;
}

/* '2026-09-30T09:45:00Z' → '30 September 2026, 3:15 pm' (India time) */
export function istWhen(iso: string) {
  const d = new Date(Date.parse(iso) + 5.5 * HOUR);
  const M = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const h = d.getUTCHours(), m = String(d.getUTCMinutes()).padStart(2, '0');
  return `${d.getUTCDate()} ${M[d.getUTCMonth()]} ${d.getUTCFullYear()}, ${h % 12 || 12}:${m} ${h < 12 ? 'am' : 'pm'}`;
}

/* The public site's address for links in emails (SITE_ORIGIN: workers.dev until launch, then the domain),
   and the admin panel's. */
export const siteOrigin = () => ((env.SITE_ORIGIN as string) || 'https://mfdinvoice.co.in').replace(/\/$/, '');
export const controlOrigin = () => `https://${(env.CONTROL_HOST as string) || 'control.mfdinvoice.co.in'}`;

/* '2026-09-30T09:45:00Z' → '30 Sep 2026, 3:15 pm' (India time), for tables */
export const istShort = (iso: string | null) => {
  if (!iso) return '—';
  const [d, t] = istWhen(iso).split(', ');
  const [day, month, year] = d.split(' ');
  return `${day} ${month.slice(0, 3)} ${year}, ${t}`;
};
