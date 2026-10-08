/* "Forward your CAMS mailbacks to us": the first of the three ways CAMS's email reaches the software (then a Gmail
   app password, then by hand). The person's Gmail forwards CAMS's mailbacks, by a filter, to one address of ours
   (Cloudflare Email Routing sends it to this Worker). Each mailback names the email CAMS sent it to (its To), so one
   address serves everyone.

     POST /forward/start   { email, pub }      a code is emailed to that address (it proves the email is theirs)
     POST /forward/verify  { email, code }     → { ok, secret }: this PC's key for the box from now on
     GET  /forward/mail    Bearer <secret>     what waits: mailbacks, and Gmail's forwarding confirmation code
     GET  /forward/mail/<id>  Bearer <secret>  one mailback, locked with this PC's public key

   Nothing is kept readable here: a mailback is locked (AES-GCM, its key wrapped with the PC's RSA key) the moment it
   arrives, and deleted 5 minutes after the PC takes it (so a retry can take it again), or after 3 days untaken.
   Mail from anyone but CAMS (and Gmail's confirmation) is refused. */
import type { Env } from './index';

const CODE_MINUTES = 15, CODES_PER_HOUR = 5, TRIES = 5, KEEP_TAKEN_MIN = 5, KEEP_DAYS = 3, MAIL_MAX = 20 * 1024 * 1024;

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

let ready = false;
async function schema(env: Env) {
  if (ready) return;
  await env.DB.batch([
    /* one box per CAMS email (who: its SHA-256): the PC's public key and the hash of its secret, once a code proved
       the email; a code waiting to be typed */
    env.DB.prepare(`CREATE TABLE IF NOT EXISTS boxes (who TEXT PRIMARY KEY, pub TEXT, secret TEXT, pending_pub TEXT,
      code TEXT, code_at TEXT, codes INTEGER NOT NULL DEFAULT 0, tries INTEGER NOT NULL DEFAULT 0, verified_at TEXT,
      created_at TEXT NOT NULL)`),
    /* what came: a mailback (its body locked in R2, forward/<id>) or Gmail's confirmation code */
    env.DB.prepare(`CREATE TABLE IF NOT EXISTS mails (id INTEGER PRIMARY KEY, who TEXT NOT NULL, kind TEXT NOT NULL,
      subject TEXT, code TEXT, size INTEGER, received_at TEXT NOT NULL, taken_at TEXT)`),
    env.DB.prepare('CREATE INDEX IF NOT EXISTS mails_who ON mails (who)'),
    env.DB.prepare('CREATE UNIQUE INDEX IF NOT EXISTS boxes_secret ON boxes (secret)'),
  ]);
  ready = true;
}

/* ---- setting it up: a code to the CAMS email, typed in the software ---- */

async function start(req: Request, env: Env): Promise<Response> {
  const b = await req.json<Record<string, unknown>>().catch(() => ({} as Record<string, unknown>));
  const email = String(b.email || '').trim().toLowerCase(), pub = String(b.pub || '');
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(email) || email.length > 200) return json({ ok: false, error: 'bad_email' }, 400);
  if (!/^[A-Za-z0-9+/=]{200,1200}$/.test(pub)) return json({ ok: false, error: 'bad_key' }, 400);
  const w = await who(email);
  const row = await env.DB.prepare('SELECT code_at, codes FROM boxes WHERE who = ?').bind(w).first<{ code_at: string | null; codes: number }>();
  const recent = row?.code_at && Date.now() - Date.parse(row.code_at) < 3600_000;
  if (recent && row!.codes >= CODES_PER_HOUR) return json({ ok: false, error: 'too_many' }, 429);
  const code = String(crypto.getRandomValues(new Uint32Array(1))[0] % 1_000_000).padStart(6, '0');
  await env.DB.prepare(`INSERT INTO boxes (who, pending_pub, code, code_at, codes, tries, created_at) VALUES (?, ?, ?, ?, 1, 0, ?)
      ON CONFLICT (who) DO UPDATE SET pending_pub = excluded.pending_pub, code = excluded.code, code_at = excluded.code_at,
        codes = CASE WHEN ? THEN boxes.codes + 1 ELSE 1 END, tries = 0`)
    .bind(w, pub, await sha(code), now(), now(), recent ? 1 : 0).run();
  await env.EMAIL.send({
    to: email, from: { name: 'MFDInvoice', email: 'no-reply@mfdinvoice.co.in' },
    subject: `${code} is your MFDInvoice code`,
    text: `${code}\n\nType this code in MFDInvoice to receive CAMS's invoice emails through us, forwarded from your mailbox.\n\nIt works for ${CODE_MINUTES} minutes. If you didn't ask for it, ignore this email: nothing changes.\n\n-- MFDInvoice`,
  });
  return json({ ok: true });
}

async function verify(req: Request, env: Env): Promise<Response> {
  const b = await req.json<Record<string, unknown>>().catch(() => ({} as Record<string, unknown>));
  const w = await who(String(b.email || '')), code = String(b.code || '').replace(/\D/g, '');
  const row = await env.DB.prepare('SELECT code, code_at, tries, pending_pub FROM boxes WHERE who = ?').bind(w)
    .first<{ code: string | null; code_at: string | null; tries: number; pending_pub: string | null }>();
  if (!row?.code || !row.code_at || !row.pending_pub) return json({ ok: false, error: 'no_code' }, 400);
  if (Date.now() - Date.parse(row.code_at) > CODE_MINUTES * 60_000) return json({ ok: false, error: 'expired' }, 400);
  if (row.tries >= TRIES) return json({ ok: false, error: 'too_many' }, 429);
  if ((await sha(code)) !== row.code) {
    await env.DB.prepare('UPDATE boxes SET tries = tries + 1 WHERE who = ?').bind(w).run();
    return json({ ok: false, error: 'wrong_code' }, 400);
  }
  const secret = hex(crypto.getRandomValues(new Uint8Array(32)).buffer);
  /* the newest PC proved the email: the box is its own from now on */
  await env.DB.prepare(`UPDATE boxes SET pub = pending_pub, secret = ?, pending_pub = NULL, code = NULL, tries = 0,
      verified_at = ? WHERE who = ?`).bind(await sha(secret), now(), w).run();
  return json({ ok: true, secret });
}

/* ---- fetching: what waits for this PC ---- */

async function boxOf(req: Request, env: Env) {
  const secret = (req.headers.get('authorization') || '').replace(/^Bearer\s+/i, '').trim();
  if (!/^[0-9a-f]{64}$/.test(secret)) return null;
  return env.DB.prepare('SELECT who FROM boxes WHERE secret = ?').bind(await sha(secret)).first<{ who: string }>();
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
  const rows = await env.DB.prepare('SELECT id, kind, subject, code, size, received_at, taken_at FROM mails WHERE who = ? ORDER BY id')
    .bind(box.who).all();
  return json({ ok: true, mails: rows.results });
}

async function one(req: Request, env: Env, id: number): Promise<Response> {
  const box = await boxOf(req, env);
  if (!box) return json({ ok: false, error: 'bad_secret' }, 401);
  const row = await env.DB.prepare("SELECT id FROM mails WHERE id = ? AND who = ? AND kind = 'mailback'").bind(id, box.who).first();
  const file = row && (await env.FILES.get(`forward/${id}`));
  if (!file) return json({ ok: false, error: 'not_found' }, 404);
  await env.DB.prepare('UPDATE mails SET taken_at = COALESCE(taken_at, ?) WHERE id = ?').bind(now(), id).run();
  return new Response(file.body, { headers: { 'content-type': 'application/octet-stream', 'cache-control': 'no-store' } });
}

export async function forwardRoutes(req: Request, env: Env, path: string): Promise<Response | null> {
  if (!path.startsWith('/forward/')) return null;
  await schema(env);
  if (req.method === 'POST' && path === '/forward/start') return start(req, env);
  if (req.method === 'POST' && path === '/forward/verify') return verify(req, env);
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
      return message.setReject('Not a forwarding confirmation this address understands.');
    }
    await env.DB.prepare("INSERT INTO mails (who, kind, subject, code, size, received_at) VALUES (?, 'confirm', ?, ?, 0, ?)")
      .bind(await who(gmail), subj.slice(0, 300), need, now()).run();
    return;
  }

  /* every refusal is logged with what it saw (`wrangler tail software`): the sender only gets a bounce */
  const refuse = (why: string, saw: string) => { console.log(`refused: ${why} ${saw}`); message.setReject(why); };

  /* a CAMS mailback: from CAMS, signed by CAMS (Cloudflare refuses mail that fails CAMS's own DMARC) */
  if (!/@camsonline\.com\b/.test(from)) return refuse('This address takes only CAMS mailbacks for MFDInvoice.', `from ${JSON.stringify(from)}`);
  const auth = h('authentication-results') + ' ' + h('arc-authentication-results');
  if (auth.trim() && !/dkim=pass[^;]*camsonline\.com/i.test(auth)) return refuse('Not signed by CAMS.', `auth ${JSON.stringify(auth.slice(0, 1500))}`);
  if (message.rawSize > MAIL_MAX) return refuse('Too large.', `size ${message.rawSize}`);
  /* whose it is: any mailbox it was for or came through. CAMS writes to the ARN's registered email, which often
     forwards on before the mailbox whose filter sends it here (pritamutha@ → neillunavat3192@ → us, 8 Oct): To and
     Cc, the Delivered-To / X-Forwarded-For / X-Original-To each mailbox adds, and Gmail's forwarding sender
     (x+caf_=…@gmail.com is x@gmail.com). The box is the email proved in the software: the one that forwards here. */
  const sender = message.from.toLowerCase().replace(/\+caf_=[^@]*@/, '@');
  /* the mailbox that sent it here first (Gmail's sender, the latest Delivered-To), then the rest of the way */
  const seen = [...new Set([...emails(sender), ...['delivered-to', 'to', 'cc', 'x-original-to', 'x-forwarded-for'].flatMap(n => emails(h(n)))])];
  for (const to of seen) {
    const box = await env.DB.prepare('SELECT who, pub FROM boxes WHERE who = ? AND pub IS NOT NULL').bind(await who(to)).first<{ who: string; pub: string }>();
    if (!box) continue;
    const raw = await new Response(message.raw).arrayBuffer();
    const row = await env.DB.prepare("INSERT INTO mails (who, kind, subject, size, received_at) VALUES (?, 'mailback', ?, ?, ?) RETURNING id")
      .bind(box.who, subject.slice(0, 300), raw.byteLength, now()).first<{ id: number }>();
    await env.FILES.put(`forward/${row!.id}`, await seal(box.pub, raw));
    return;
  }
  return refuse('No MFDInvoice user has set this email up for forwarding.', `seen ${JSON.stringify(seen)}`);
}
