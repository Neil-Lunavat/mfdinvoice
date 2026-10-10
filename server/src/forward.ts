/* "Forward your CAMS mailbacks to us": the first of the three ways CAMS's email reaches the software (then a Gmail
   app password, then by hand). The person's Gmail forwards CAMS's mailbacks, by a filter, to one address of ours
   (Cloudflare Email Routing sends it to this Worker). No code of ours is sent: only the owner of a Gmail can add a
   forwarding address to it, so Gmail's own confirmation mail for that Gmail, or the first CAMS mailback that came
   through it, proves the Gmail is theirs. One PC holds a Gmail's box at a time.

     POST /forward/claim  { email, pub }      → { ok, secret }: this PC asks for the box; the secret is shown once.
                                               Pending until the proof arrives; 'busy' (409) while another PC's
                                               claim is younger than 30 minutes
     GET  /forward/mail   Bearer <secret>     → { ok, proved, mails }: proved once the claim is the box's; Gmail's
                                               confirmation shows to a pending claim too, mailbacks only to the proved
     GET  /forward/mail/<id>  Bearer <secret> one mailback, locked with this PC's public key (the proved secret only)

   A box already proved for one PC keeps working for it until another PC's claim is proved. Nothing is kept readable
   here: a mailback is locked (AES-GCM, its key wrapped with the PC's RSA key) the moment it arrives, and deleted 5
   minutes after the PC takes it (so a retry can take it again), or after 3 days untaken. Mail from anyone but CAMS
   (and Gmail's confirmation) is dropped and logged, never bounced. */
import type { Env } from './index';

const BUSY_MINUTES = 30, CLAIMS_PER_HOUR = 10, KEEP_TAKEN_MIN = 5, KEEP_DAYS = 3, MAIL_MAX = 20 * 1024 * 1024;

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });
const now = () => new Date().toISOString();
const hex = (b: ArrayBuffer) => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('');
const sha = async (s: string) => hex(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)));
const who = (email: string) => sha(email.trim().toLowerCase());
const emails = (s: string) => [...s.matchAll(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g)].map(m => m[0].toLowerCase());
/* RFC 2047 words in a header (=?UTF-8?B?...?=, =?UTF-8?Q?...?=) made plain */
const plain = (s: string) => s.replace(/=\?[^?]+\?([BQ])\?([^?]*)\?=/gi, (_, enc: string, t: string) => {
  try { return enc.toUpperCase() === 'B' ? atob(t) : t.replace(/_/g, ' ').replace(/=([0-9A-F]{2})/gi, (_x, c: string) => String.fromCharCode(parseInt(c, 16))); }
  catch { return t; }
});
/* a mail's readable text: as sent, with quoted-printable and base64 parts undone */
async function readable(message: ForwardableEmailMessage): Promise<string> {
  const raw = await new Response(message.raw).text();
  const out = [raw, raw.replace(/=\r?\n/g, '').replace(/=([0-9A-F]{2})/gi, (_x, c: string) => String.fromCharCode(parseInt(c, 16)))];
  for (const m of raw.matchAll(/\r?\n\r?\n([A-Za-z0-9+/=\r\n]{120,})/g)) {
    try { out.push(atob(m[1].replace(/\s/g, ''))); } catch { /* not base64 */ }
  }
  return out.join('\n');
}

/* columns added to boxes after the first deploy */
const ADDED = ['pending_secret TEXT', 'claimed_at TEXT'];
let ready = false;
async function schema(env: Env) {
  if (ready) return;
  await env.DB.batch([
    /* one box per Gmail that forwards (who: its SHA-256): the proved PC's public key and the hash of its secret; a PC
       that claimed it and waits for the proof (pending_pub, pending_secret, claimed_at). code, tries and verified_at
       served the code emailed until 9 Oct and stay unused; code_at and codes now count the claims in the last hour. */
    env.DB.prepare(`CREATE TABLE IF NOT EXISTS boxes (who TEXT PRIMARY KEY, pub TEXT, secret TEXT, pending_pub TEXT,
      code TEXT, code_at TEXT, codes INTEGER NOT NULL DEFAULT 0, tries INTEGER NOT NULL DEFAULT 0, verified_at TEXT,
      created_at TEXT NOT NULL)`),
    /* what came: a mailback (its body locked in R2, forward/<id>) or Gmail's confirmation code */
    env.DB.prepare(`CREATE TABLE IF NOT EXISTS mails (id INTEGER PRIMARY KEY, who TEXT NOT NULL, kind TEXT NOT NULL,
      subject TEXT, code TEXT, size INTEGER, received_at TEXT NOT NULL, taken_at TEXT)`),
    env.DB.prepare('CREATE INDEX IF NOT EXISTS mails_who ON mails (who)'),
    env.DB.prepare('CREATE UNIQUE INDEX IF NOT EXISTS boxes_secret ON boxes (secret)'),
  ]);
  const has = new Set((await env.DB.prepare('PRAGMA table_info(boxes)').all<{ name: string }>()).results.map(c => c.name));
  for (const col of ADDED) if (!has.has(col.split(' ')[0])) await env.DB.prepare(`ALTER TABLE boxes ADD COLUMN ${col}`).run();
  await env.DB.prepare('CREATE INDEX IF NOT EXISTS boxes_pending ON boxes (pending_secret)').run();
  ready = true;
}

/* ---- setting it up: a PC claims a Gmail; the proof comes by mail (see receive) ---- */

async function claim(req: Request, env: Env): Promise<Response> {
  const b = await req.json<Record<string, unknown>>().catch(() => ({} as Record<string, unknown>));
  const email = String(b.email || '').trim().toLowerCase(), pub = String(b.pub || '');
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(email) || email.length > 200) return json({ ok: false, error: 'bad_email' }, 400);
  if (!/^[A-Za-z0-9+/=]{200,1200}$/.test(pub)) return json({ ok: false, error: 'bad_key' }, 400);
  const w = await who(email);
  const row = await env.DB.prepare('SELECT pending_pub, pending_secret, claimed_at, code_at, codes FROM boxes WHERE who = ?').bind(w)
    .first<{ pending_pub: string | null; pending_secret: string | null; claimed_at: string | null; code_at: string | null; codes: number }>();
  if (row?.pending_secret && row.pending_pub && row.pending_pub !== pub && row.claimed_at
      && Date.now() - Date.parse(row.claimed_at) < BUSY_MINUTES * 60_000) return json({ ok: false, error: 'busy' }, 409);
  const recent = !!row?.code_at && Date.now() - Date.parse(row.code_at) < 3600_000;
  if (recent && row!.codes >= CLAIMS_PER_HOUR) return json({ ok: false, error: 'too_many' }, 429);
  const secret = hex(crypto.getRandomValues(new Uint8Array(32)).buffer);
  await env.DB.prepare(`INSERT INTO boxes (who, pending_pub, pending_secret, claimed_at, code_at, codes, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)
      ON CONFLICT (who) DO UPDATE SET pending_pub = excluded.pending_pub, pending_secret = excluded.pending_secret,
        claimed_at = excluded.claimed_at, code_at = CASE WHEN ? THEN boxes.code_at ELSE excluded.code_at END,
        codes = CASE WHEN ? THEN boxes.codes + 1 ELSE 1 END`)
    .bind(w, pub, await sha(secret), now(), now(), now(), recent ? 1 : 0, recent ? 1 : 0).run();
  return json({ ok: true, secret });
}

/* the proof arrived: the pending claim is the box's now (the previous PC's key and secret stop working) */
async function promote(env: Env, w: string) {
  await env.DB.prepare(`UPDATE boxes SET pub = pending_pub, secret = pending_secret, verified_at = ?, pending_pub = NULL,
      pending_secret = NULL, claimed_at = NULL WHERE who = ? AND pending_pub IS NOT NULL AND pending_secret IS NOT NULL`)
    .bind(now(), w).run();
}

/* ---- fetching: what waits for this PC ---- */

async function boxOf(req: Request, env: Env) {
  const secret = (req.headers.get('authorization') || '').replace(/^Bearer\s+/i, '').trim();
  if (!/^[0-9a-f]{64}$/.test(secret)) return null;
  const h = await sha(secret);
  const box = await env.DB.prepare('SELECT who, secret FROM boxes WHERE secret = ? OR pending_secret = ?').bind(h, h).first<{ who: string; secret: string | null }>();
  return box && { who: box.who, proved: box.secret === h };
}

export async function tidy(env: Env) {
  await schema(env);
  const taken = new Date(Date.now() - KEEP_TAKEN_MIN * 60_000).toISOString(), old = new Date(Date.now() - KEEP_DAYS * 86_400_000).toISOString();
  const gone = await env.DB.prepare('SELECT id, kind FROM mails WHERE (taken_at IS NOT NULL AND taken_at < ?) OR received_at < ? LIMIT 500')
    .bind(taken, old).all<{ id: number; kind: string }>();
  if (!gone.results.length) return;
  const files = gone.results.filter(m => m.kind === 'mailback').map(m => `forward/${m.id}`);
  if (files.length) await env.FILES.delete(files);
  await env.DB.prepare(`DELETE FROM mails WHERE id IN (${gone.results.map(() => '?').join(',')})`).bind(...gone.results.map(m => m.id)).run();
}

async function list(req: Request, env: Env): Promise<Response> {
  const box = await boxOf(req, env);
  if (!box) return json({ ok: false, error: 'bad_secret' }, 401);
  await tidy(env);
  const rows = await env.DB.prepare(`SELECT id, kind, subject, code, size, received_at, taken_at FROM mails WHERE who = ?
      ${box.proved ? '' : "AND kind = 'confirm'"} ORDER BY id`).bind(box.who).all();
  return json({ ok: true, proved: box.proved, mails: rows.results });
}

async function one(req: Request, env: Env, id: number): Promise<Response> {
  const box = await boxOf(req, env);
  if (!box?.proved) return json({ ok: false, error: 'bad_secret' }, 401);
  const row = await env.DB.prepare("SELECT id FROM mails WHERE id = ? AND who = ? AND kind = 'mailback'").bind(id, box.who).first();
  const file = row && (await env.FILES.get(`forward/${id}`));
  if (!file) return json({ ok: false, error: 'not_found' }, 404);
  await env.DB.prepare('UPDATE mails SET taken_at = COALESCE(taken_at, ?) WHERE id = ?').bind(now(), id).run();
  return new Response(file.body, { headers: { 'content-type': 'application/octet-stream', 'cache-control': 'no-store' } });
}

export async function forwardRoutes(req: Request, env: Env, path: string): Promise<Response | null> {
  if (!path.startsWith('/forward/')) return null;
  await schema(env);
  if (req.method === 'POST' && path === '/forward/claim') return claim(req, env);
  if (req.method === 'GET' && path === '/forward/mail') return list(req, env);
  const m = path.match(/^\/forward\/mail\/(\d+)$/);
  if (req.method === 'GET' && m) return one(req, env, Number(m[1]));
  return json({ ok: false, error: 'not_found' }, 404);
}

/* ---- what arrives at the address ---- */

/* The mail locked for one PC: [2 bytes: the wrapped key's length][the AES key, wrapped with the PC's RSA-OAEP key]
   [12 bytes: iv][the mail, AES-GCM]. The software opens it with its private key (hands/forward.py). */
async function seal(pubB64: string, data: ArrayBuffer): Promise<Uint8Array> {
  const pub = await crypto.subtle.importKey('spki', Uint8Array.from(atob(pubB64), c => c.charCodeAt(0)),
    { name: 'RSA-OAEP', hash: 'SHA-256' }, false, ['encrypt']);
  const raw = crypto.getRandomValues(new Uint8Array(32)), iv = crypto.getRandomValues(new Uint8Array(12));
  const aes = await crypto.subtle.importKey('raw', raw, 'AES-GCM', false, ['encrypt']);
  const body = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, aes, data));
  const wrapped = new Uint8Array(await crypto.subtle.encrypt({ name: 'RSA-OAEP' }, pub, raw));
  const out = new Uint8Array(2 + wrapped.length + 12 + body.length);
  out[0] = wrapped.length >> 8; out[1] = wrapped.length & 255;
  out.set(wrapped, 2); out.set(iv, 2 + wrapped.length); out.set(body, 14 + wrapped.length);
  return out;
}

export async function receive(message: ForwardableEmailMessage, env: Env): Promise<void> {
  await schema(env);
  const h = (n: string) => message.headers.get(n) || '';
  const from = h('from').toLowerCase(), subject = h('subject');

  /* Gmail's "confirm forwarding" mail. What the person needs from it is shown in the software: Gmail's code, to type
     in Gmail, or (Gmail today, 8 Oct 2026: no code, only a link) the confirmation link, to open. Kept in `code`.
     The Gmail address is read from the subject, else from the body ("x@gmail.com has requested ..."). */
  if (from.includes('forwarding-noreply@google.com')) {
    const subj = plain(subject), body = await readable(message);
    const theirs = (e: string) => !/@(google\.com|(mailback\.)?mfdinvoice\.co\.in)$/.test(e);
    const code = subj.match(/#(\d{6,})/)?.[1] || body.match(/confirmation code[^0-9]{0,80}?(\d{6,})/i)?.[1];
    const links = [...body.replace(/&amp;/g, '&').matchAll(/https:\/\/(?:mail-settings|mail|isolated\.mail)\.google\.com\/[^\s"'<>()]+/g)]
      .map(m => m[0]).sort((a, b) => b.length - a.length);
    const gmail = emails(subj).find(theirs) || emails(body.match(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\s+has requested/i)?.[0] || '')[0]
      || emails(body).find(theirs);
    const need = code || links[0];
    if (!need || !gmail) {
      const hosts = [...body.matchAll(/https:\/\/[^\s"'<>()/]+\/[^\s"'<>()]{0,20}/g)].map(m => m[0]);
      console.log(`forwarding confirmation not understood: subject ${JSON.stringify(subj)}, code ${code ? 'found' : 'missing'}, link ${links[0] ? 'found' : 'missing'}, gmail ${gmail ? 'found' : 'missing'}, urls ${JSON.stringify([...new Set(hosts)].slice(0, 12))}`);
      return;      // dropped quietly, never bounced: a bounce lands in the person's own Gmail
    }
    await env.DB.prepare("INSERT INTO mails (who, kind, subject, code, size, received_at) VALUES (?, 'confirm', ?, ?, 0, ?)")
      .bind(await who(gmail), subj.slice(0, 300), need, now()).run();
    await promote(env, await who(gmail));      // Gmail confirmed it to us: only that Gmail's owner could have asked
    return;
  }

  /* nothing is ever bounced (a bounce would reach the person's own Gmail): a refused mail is accepted and dropped,
     logged with what it saw (`wrangler tail software` shows why) */
  const refuse = (why: string, saw: string) => { console.log(`refused: ${why} ${saw}`); };

  /* a CAMS mailback: from CAMS, signed by CAMS (Cloudflare refuses mail that fails CAMS's own DMARC) */
  if (!/@camsonline\.com\b/.test(from)) return refuse('This address takes only CAMS mailbacks for MFDInvoice.', `from ${JSON.stringify(from)}`);
  const auth = h('authentication-results') + ' ' + h('arc-authentication-results');
  if (auth.trim() && !/dkim=pass[^;]*camsonline\.com/i.test(auth)) return refuse('Not signed by CAMS.', `auth ${JSON.stringify(auth.slice(0, 1500))}`);
  if (message.rawSize > MAIL_MAX) return refuse('Too large.', `size ${message.rawSize}`);
  /* whose it is: any mailbox it was for or came through. CAMS writes to the ARN's registered email, which often
     forwards on before the mailbox whose filter sends it here (the person's Gmail → another Gmail → us, 8 Oct): To and
     Cc, the Delivered-To / X-Forwarded-For / X-Original-To each mailbox adds, and Gmail's forwarding sender
     (x+caf_=…@gmail.com is x@gmail.com). The box is the Gmail the person named: the one that forwards here. */
  const sender = message.from.toLowerCase().replace(/\+caf_=[^@]*@/, '@');
  /* the mailbox that sent it here first (Gmail's sender, the latest Delivered-To), then the rest of the way */
  const seen = [...new Set([...emails(sender), ...['delivered-to', 'to', 'cc', 'x-original-to', 'x-forwarded-for'].flatMap(n => emails(h(n)))])];
  for (const to of seen) {
    const w = await who(to);
    /* only the Gmail that forwarded it here (the envelope sender) proves a waiting claim: a To or Cc names a mailbox,
       it doesn't show its owner set anything up */
    if (emails(sender).includes(to)) await promote(env, w);
    const box = await env.DB.prepare('SELECT who, pub FROM boxes WHERE who = ? AND pub IS NOT NULL').bind(w).first<{ who: string; pub: string }>();
    if (!box) continue;
    const raw = await new Response(message.raw).arrayBuffer();
    const row = await env.DB.prepare("INSERT INTO mails (who, kind, subject, size, received_at) VALUES (?, 'mailback', ?, ?, ?) RETURNING id")
      .bind(box.who, subject.slice(0, 300), raw.byteLength, now()).first<{ id: number }>();
    await env.FILES.put(`forward/${row!.id}`, await seal(box.pub, raw));
    return;
  }
  return refuse('No MFDInvoice user has set this email up for forwarding.', `seen ${JSON.stringify(seen)}`);
}
