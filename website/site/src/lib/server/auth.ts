/* Sign-in (the same for the site and the app): an email gets a 6-digit code; the right code signs in,
   creating the account if the email is new. Sessions are a random token; only its hash is stored. */
import { env } from 'cloudflare:workers';
import { fail, HttpError, cookie, ip } from './http';
import { now, ago, later, MIN, HOUR, DAY, sha256, token, sixDigits, cleanEmail, same } from './util';
import { send } from './mail';
import { codeMail } from '../emails';
import { record } from './errors';
import { applyGift } from './gifts';
import { event } from './events';

const CODE_LIFE = 10 * MIN, RESEND_AFTER = 45_000, CODES_PER_HOUR = 5, IP_CODES_PER_HOUR = 20, IP_TRIES_PER_HOUR = 30;
export const WEB_KEEP = 30 * DAY, WEB_SHORT = DAY, APP_LIFE = 365 * DAY;

type Code = { id: number; hash: string; created_at: string; expires_at: string; tries_left: number; used_at: string | null };

const latestCode = (email: string) =>
  env.DB.prepare('SELECT * FROM codes WHERE email = ? ORDER BY id DESC LIMIT 1').bind(email).first<Code>();

/* A rate limit: at most perHour hits on this key in the last hour (the `hits` table). */
export async function hit(key: string, perHour: number) {
  const r = await env.DB.prepare('SELECT COUNT(*) AS n FROM hits WHERE key = ? AND at > ?').bind(key, ago(HOUR)).first<{ n: number }>();
  if (r!.n >= perHour) throw new HttpError(fail(429, 'too_many_requests'));
  await env.DB.prepare('INSERT INTO hits (key, at) VALUES (?, ?)').bind(key, now()).run();
}

export function normEmail(v: unknown) {
  const e = cleanEmail(v);
  if (!e) throw new HttpError(fail(400, 'bad_email'));
  return e;
}

/* Sends a code. Refuses: within 45 s of the last one (wait: seconds), more than 5 an hour for the email,
   more than 20 an hour from one IP, or while a code spent on wrong tries is still inside its 10 minutes. */
export async function requestCode(req: Request, email: string) {
  const last = await latestCode(email);
  if (last) {
    const since = Date.now() - Date.parse(last.created_at);
    if (since < RESEND_AFTER) throw new HttpError(fail(429, 'wait', { wait: Math.ceil((RESEND_AFTER - since) / 1000) }));
    if (last.tries_left <= 0 && !last.used_at && Date.parse(last.expires_at) > Date.now())
      throw new HttpError(fail(429, 'locked', { wait: Math.ceil((Date.parse(last.expires_at) - Date.now()) / 1000) }));
  }
  const n = await env.DB.prepare('SELECT COUNT(*) AS n FROM codes WHERE email = ? AND created_at > ?').bind(email, ago(HOUR)).first<{ n: number }>();
  if (n!.n >= CODES_PER_HOUR) throw new HttpError(fail(429, 'too_many_codes'));
  await hit('code:' + ip(req), IP_CODES_PER_HOUR);

  /* test accounts (the owner's, for trying the site): addresses at TEST_LOGIN_DOMAIN get the fixed TEST_LOGIN_CODE
     and no email. Both are Worker secrets; without them there are no test accounts. */
  const test = !!env.TEST_LOGIN_DOMAIN && /^\d{6}$/.test(env.TEST_LOGIN_CODE || '') && email.endsWith('@' + env.TEST_LOGIN_DOMAIN);
  const code = test ? env.TEST_LOGIN_CODE : sixDigits();
  /* a new code replaces any earlier one */
  await env.DB.prepare('UPDATE codes SET tries_left = 0 WHERE email = ? AND used_at IS NULL AND tries_left > 0').bind(email).run();
  const row = await env.DB.prepare('INSERT INTO codes (email, hash, created_at, expires_at, ip) VALUES (?, ?, ?, ?, ?) RETURNING id')
    .bind(email, await sha256(email + ':' + code), now(), later(CODE_LIFE), ip(req)).first<{ id: number }>();
  if (test) return;
  try {
    await send(email, codeMail({ code }));
  } catch (e) {
    /* nobody can sign in while this fails: critical, the owner is emailed */
    await record('signin_email', 'requestCode', e);
    await env.DB.prepare('DELETE FROM codes WHERE id = ?').bind(row!.id).run();
    throw new HttpError(fail(502, 'send_failed'));
  }
}

/* The check alone: throws as verifyCode does (bad_code, expired, locked, wrong; a wrong try is counted), but a right
   code is not used up. The app's "this account is on another PC" question uses it, then the same code is sent again. */
export async function checkCode(req: Request, email: string, code: unknown): Promise<Code> {
  if (typeof code !== 'string' || !/^\d{6}$/.test(code)) throw new HttpError(fail(400, 'bad_code'));
  await hit('try:' + ip(req), IP_TRIES_PER_HOUR);
  const c = await latestCode(email);
  if (!c || c.used_at || Date.parse(c.expires_at) <= Date.now()) throw new HttpError(fail(400, 'expired'));
  if (c.tries_left <= 0) throw new HttpError(fail(400, 'locked'));
  if (!same(c.hash, await sha256(email + ':' + code))) {
    const r = await env.DB.prepare('UPDATE codes SET tries_left = tries_left - 1 WHERE id = ? AND tries_left > 0 RETURNING tries_left').bind(c.id).first<{ tries_left: number }>();
    const left = r ? r.tries_left : 0;
    throw new HttpError(fail(400, left ? 'wrong' : 'locked', { tries_left: left }));
  }
  return c;
}

/* Checks a code and returns the account (a new account for a new email), with delete_after if its deletion is
   pending. A waiting gift for this email starts here (gifts.ts), for the site and the app alike. gift_revoked: this
   sign-in made the account, and the email had a gift that was revoked before it was used (the page says it expired).
   deleted_by: this sign-in made the account, and the email had one before that was deleted: 'buyer' or an admin.
   Errors: wrong (tries_left), locked (three wrong tries), expired (no live code). */
export async function verifyCode(req: Request, email: string, code: unknown): Promise<{ id: number; delete_after: string | null; gift_until: string | null; gift_revoked: boolean; deleted_by: string | null }> {
  const c = await checkCode(req, email, code);
  /* spend the code: only one request can */
  const used = await env.DB.prepare('UPDATE codes SET used_at = ? WHERE id = ? AND used_at IS NULL AND tries_left > 0').bind(now(), c.id).run();
  if (!used.meta.changes) throw new HttpError(fail(400, 'expired'));
  const made = await env.DB.prepare('INSERT INTO accounts (email, created_at, uid) VALUES (?, ?, lower(hex(randomblob(8)))) ON CONFLICT (email) DO NOTHING').bind(email, now()).run();
  const a = (await env.DB.prepare('SELECT id, delete_after FROM accounts WHERE email = ?').bind(email).first<{ id: number; delete_after: string | null }>())!;
  if (made.meta.changes) await event('buyer', 'account.created', a.id).run();
  /* gift_until: a gift started just now (the sign-in page celebrates it) */
  const gift_until = a.delete_after ? null : await applyGift(a.id, email);
  const gift_revoked = !gift_until && !!made.meta.changes
    && !!(await env.DB.prepare('SELECT 1 FROM gifts WHERE email = ? AND revoked_at IS NOT NULL AND used_at IS NULL LIMIT 1').bind(email).first());
  const gone = made.meta.changes
    ? await env.DB.prepare('SELECT deleted_by FROM deletions WHERE email = ? ORDER BY deleted_at DESC LIMIT 1').bind(email).first<{ deleted_by: string | null }>()
    : null;
  return { ...a, gift_until, gift_revoked, deleted_by: gone ? gone.deleted_by ?? 'buyer' : null };
}

/* A new session. Returns the raw token (the only time it exists outside the hash). */
export async function newSession(accountId: number, kind: 'web' | 'app', life: number, device: string | null = null) {
  const t = token();
  await env.DB.prepare('INSERT INTO sessions (hash, account_id, kind, created_at, expires_at, last_seen, device) VALUES (?, ?, ?, ?, ?, ?, ?)')
    .bind(await sha256(t), accountId, kind, now(), later(life), now(), device).run();
  return t;
}

/* The app sessions of an account that are alive (not expired, not ended), the most recently used first. One PC per
   account: normally one. */
export const liveAppSessions = (accountId: number) =>
  env.DB.prepare("SELECT device, last_seen FROM sessions WHERE account_id = ? AND kind = 'app' AND ended_at IS NULL AND expires_at > ? ORDER BY last_seen DESC")
    .bind(accountId, now()).all<{ device: string | null; last_seen: string }>().then(r => r.results);

/* Ends every live app session of the account (another PC signed in): kept, marked, until they expire. */
export const endAppSessions = (accountId: number, by: string | null) =>
  env.DB.prepare("UPDATE sessions SET ended_at = ?, ended_by = ? WHERE account_id = ? AND kind = 'app' AND ended_at IS NULL AND expires_at > ?")
    .bind(now(), by, accountId, now()).run();

export type Session = { id: number; account_id: number; email: string; kind: 'web' | 'app'; expires_at: string; last_seen: string; ended_at: string | null; ended_by: string | null; delete_after: string | null };

/* An account whose deletion is pending has no usable session (pending: true finds it anyway, for "Keep my account"). */
export async function findSession(t: string | null, kind: 'web' | 'app', pending = false): Promise<Session | null> {
  if (!t || t.length > 100) return null;
  const s = await env.DB.prepare(
    `SELECT s.id, s.account_id, s.kind, s.expires_at, s.last_seen, s.ended_at, s.ended_by, a.email, a.delete_after FROM sessions s JOIN accounts a ON a.id = s.account_id
     WHERE s.hash = ? AND s.kind = ? AND s.expires_at > ?${pending ? '' : ' AND a.delete_after IS NULL'}`).bind(await sha256(t), kind, now()).first<Session>();
  if (!s) return null;
  /* a token that another PC signed out: every /api/app/* route (and the download) answers this, once, here */
  if (s.ended_at) throw new HttpError(fail(401, 'signed_in_elsewhere', { device: s.ended_by }));
  /* the app's token stays alive while the software is used: a year from its last use. last_seen is the PC's "last
     used", so it is written at most hourly */
  if (Date.now() - Date.parse(s.last_seen) > HOUR)
    await env.DB.prepare(`UPDATE sessions SET last_seen = ?${kind === 'app' ? ', expires_at = ?' : ''} WHERE id = ?`)
      .bind(...(kind === 'app' ? [now(), later(APP_LIFE), s.id] : [now(), s.id])).run();
  return s;
}

export const endSession = (t: string | null) =>
  t ? sha256(t).then(h => env.DB.prepare('DELETE FROM sessions WHERE hash = ?').bind(h).run()) : Promise.resolve();

/* ---- the site: a cookie ---- */
export const webSession = (req: Request) => findSession(cookie(req, 'sid'), 'web');
export const pendingSession = (req: Request) => findSession(cookie(req, 'sid'), 'web', true);

/* sid: the session, HttpOnly. si: "signed in", readable by the static pages' nav script. Same lifetime. */
export function sessionCookies(t: string, keep: boolean) {
  const age = keep ? `; Max-Age=${WEB_KEEP / 1000}` : '';
  return [`sid=${t}; Path=/; HttpOnly; Secure; SameSite=Lax${age}`, `si=1; Path=/; Secure; SameSite=Lax${age}`];
}
export const clearCookies = () => ['sid=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0', 'si=; Path=/; Secure; SameSite=Lax; Max-Age=0', setupCookie(false)];

/* sb: the billing details aren't set up yet, so the nav's Account button shows a dot (si.js). Set at sign-in and by
   the Account page, cleared once they're saved. */
export const setupCookie = (missing: boolean) =>
  missing ? `sb=1; Path=/; Secure; SameSite=Lax; Max-Age=${WEB_KEEP / 1000}` : 'sb=; Path=/; Secure; SameSite=Lax; Max-Age=0';

/* hp: this account has had a plan, or its email a free trial (account.ts hadPlan), so the site's main button says
   "Buy now", not "Try for
   Free" (si.js, components/Cta.astro). Set at sign-in, by the Account page and whenever a page asks /api/me. It
   stays after signing out: this browser's person has had their trial. */
export const planCookie = (had: boolean) =>
  had ? `hp=1; Path=/; Secure; SameSite=Lax; Max-Age=${WEB_KEEP / 1000}` : 'hp=; Path=/; Secure; SameSite=Lax; Max-Age=0';

export function withCookies(res: Response, cookies: string[]) {
  cookies.forEach(c => res.headers.append('set-cookie', c));
  return res;
}

/* ---- the app: a bearer token ---- */
export const bearer = (req: Request) => (req.headers.get('authorization') || '').replace(/^Bearer\s+/i, '') || null;
export const appSession = (req: Request) => findSession(bearer(req), 'app');
