/* The software's own server. Small on purpose.

     GET  /automation/latest.json, /automation/<version>.zip    the portal steps: static files, not served from here
     POST /report                                               Send to support, from the app → { ok, id, key }
     PUT  /report/<id>/record?key=<key>                         that report's run record, one zip
     GET  /admin/reports[?limit=50&kind=ours&email=a@b.com&before=<id>]  the latest reports ┐
     GET  /admin/stats                                          every report counted (below)│
     GET  /admin/reports/<id>                                   one, with its log lines     │
     POST /admin/reports/<id>/state  { state }                  '', 'seen' or 'fixed'       ├ x-admin-key
     GET  /admin/reports/<id>/record                            its run record, the zip     │
     GET  /admin/reports/<id>/files                             the names of the files in it│
     GET  /admin/reports/<id>/file?name=<name>                  one of them, unpacked       ┘
     /forward/*, and mail to the forwarding address               CAMS's mailbacks forwarded to us (forward.ts)

   Nobody signs in here. A report says which account and ARN it is from in its own words; that is information for
   whoever reads it, not a check. What keeps the endpoint from being filled is its size limits and a count per sender.

   Every day (the cron in wrangler.jsonc) a report older than KEEP_DAYS is deleted, with its record: the website's
   Privacy page promises it (KEEP in website/site/src/consts.ts says the same number). */

import { forwardRoutes, receive, tidy } from './forward';

export interface Env {
  DB: D1Database;
  FILES: R2Bucket;
  ADMIN_KEY: string;
  EMAIL: { send(m: { to: string; from: { name: string; email: string }; subject: string; text: string }): Promise<unknown> };
}

const LOG_MAX = 80_000, RECORD_MAX = 20 * 1024 * 1024, PER_HOUR = 60, KEEP_DAYS = 90;

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });
const str = (v: unknown, max: number) => (typeof v === 'string' ? v.slice(0, max) : '');
const now = () => new Date().toISOString();

let ready = false;
/* The one table, made the first time it is needed, so a new database needs no separate step. Columns added later are
   added the same way (ADDED): the app from 1.0.0 sends them.
     run      the run's id on the person's PC (its folder in workspace\runs). A Send to support carries the id of the
              run whose record it attaches, so the two are read together.
     ended    how a run ended: 'well', 'stopped' (the person pressed Stop), or the stop's kind ('ours', 'setup',
              'mismatch' ...: the app's errors.Stop kinds)
     seconds  how long it took
     state    for whoever fixes things: '', 'seen' or 'fixed' */
const ADDED = ['run TEXT', 'ended TEXT', 'seconds INTEGER', "state TEXT NOT NULL DEFAULT ''"];
async function schema(env: Env) {
  if (ready) return;
  await env.DB.prepare(`CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY, key TEXT NOT NULL, kind TEXT NOT NULL, email TEXT, arn TEXT, message TEXT, place TEXT,
    version TEXT, steps TEXT, pc TEXT, log TEXT, record INTEGER NOT NULL DEFAULT 0, sender TEXT, created_at TEXT NOT NULL)`).run();
  const has = new Set((await env.DB.prepare('PRAGMA table_info(reports)').all<{ name: string }>()).results.map(c => c.name));
  for (const col of ADDED) if (!has.has(col.split(' ')[0])) await env.DB.prepare(`ALTER TABLE reports ADD COLUMN ${col}`).run();
  await env.DB.prepare('CREATE INDEX IF NOT EXISTS reports_created ON reports (created_at)').run();
  await env.DB.prepare('CREATE INDEX IF NOT EXISTS reports_run ON reports (run)').run();
  await env.DB.prepare('CREATE INDEX IF NOT EXISTS reports_email ON reports (email)').run();
  ready = true;
}

async function report(req: Request, env: Env): Promise<Response> {
  if (Number(req.headers.get('content-length') || 0) > 256 * 1024) return json({ ok: false, error: 'too_big' }, 413);
  let b: Record<string, unknown>;
  try { b = await req.json(); } catch { return json({ ok: false, error: 'bad_json' }, 400); }
  await schema(env);
  const sender = req.headers.get('cf-connecting-ip') || '';
  const recent = await env.DB.prepare('SELECT COUNT(*) AS n FROM reports WHERE sender = ? AND created_at > ?')
    .bind(sender, new Date(Date.now() - 3600_000).toISOString()).first<{ n: number }>();
  if ((recent?.n ?? 0) >= PER_HOUR) return json({ ok: false, error: 'too_many' }, 429);
  const key = crypto.randomUUID().replace(/-/g, '');
  const kind = ['problem', 'ours', 'idea', 'run'].includes(String(b.kind)) ? String(b.kind) : 'problem';
  const seconds = Number.isFinite(b.seconds) ? Math.max(0, Math.round(b.seconds as number)) : null;
  const row = await env.DB.prepare(`INSERT INTO reports (key, kind, email, arn, message, place, version, steps, pc, log, sender, created_at,
        run, ended, seconds)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id`)
    .bind(key, kind, str(b.email, 200), str(b.arn, 40), str(b.message, 4000), str(b.where, 200), str(b.version, 40),
      str(b.steps, 40), str(b.pc, 400), typeof b.log === 'string' ? b.log.slice(-LOG_MAX) : '', sender, now(),
      str(b.run, 80) || null, str(b.ended, 40) || null, seconds).first<{ id: number }>();
  return json({ ok: true, id: row!.id, key });
}

async function record(req: Request, env: Env, id: number, key: string): Promise<Response> {
  await schema(env);
  const row = await env.DB.prepare('SELECT key, record FROM reports WHERE id = ?').bind(id).first<{ key: string; record: number }>();
  if (!row || row.key !== key) return json({ ok: false, error: 'not_found' }, 404);
  if (Number(req.headers.get('content-length') || 0) > RECORD_MAX) return json({ ok: false, error: 'too_big' }, 413);
  const body = await req.arrayBuffer();
  if (!body.byteLength || body.byteLength > RECORD_MAX) return json({ ok: false, error: 'too_big' }, 413);
  await env.FILES.put(`records/${id}.zip`, body, { httpMetadata: { contentType: 'application/zip' } });
  await env.DB.prepare('UPDATE reports SET record = ? WHERE id = ?').bind(body.byteLength, id).run();
  return json({ ok: true });
}

/* A run's record is one zip. These read it where it lies: the list at its end, and one file out of it. */
type Entry = { name: string; method: number; size: number; packed: number; at: number };
export function entries(buf: ArrayBuffer): Entry[] {
  const v = new DataView(buf), n = buf.byteLength, td = new TextDecoder();
  let end = -1;
  for (let i = n - 22; i >= Math.max(0, n - 65557); i--) if (v.getUint32(i, true) === 0x06054b50) { end = i; break; }
  if (end < 0) return [];
  const count = v.getUint16(end + 10, true), out: Entry[] = [];
  let p = v.getUint32(end + 16, true);
  for (let k = 0; k < count && p + 46 <= n && v.getUint32(p, true) === 0x02014b50; k++) {
    const nameLen = v.getUint16(p + 28, true), extra = v.getUint16(p + 30, true), comment = v.getUint16(p + 32, true);
    out.push({ name: td.decode(new Uint8Array(buf, p + 46, nameLen)), method: v.getUint16(p + 10, true),
      packed: v.getUint32(p + 20, true), size: v.getUint32(p + 24, true), at: v.getUint32(p + 42, true) });
    p += 46 + nameLen + extra + comment;
  }
  return out;
}
export async function unpack(buf: ArrayBuffer, e: Entry): Promise<ArrayBuffer | null> {
  const v = new DataView(buf);
  if (e.at + 30 > buf.byteLength || v.getUint32(e.at, true) !== 0x04034b50) return null;
  const start = e.at + 30 + v.getUint16(e.at + 26, true) + v.getUint16(e.at + 28, true);
  const raw = buf.slice(start, start + e.packed);
  if (e.method === 0) return raw;
  if (e.method !== 8) return null;                      /* stored or deflated: what the app writes */
  return new Response(new Blob([raw]).stream().pipeThrough(new DecompressionStream('deflate-raw'))).arrayBuffer();
}
/* Pictures as pictures; everything else as plain text, so a saved page's HTML is read, never run. */
const TYPES: Record<string, string> = { jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png' };

const LIST = 'id, kind, email, arn, message, place, version, steps, pc, record, created_at, run, ended, seconds, state';

/* Every report kept (the last KEEP_DAYS), counted here so the panel's numbers are whole, not a sample. A run is a
   report of kind run or ours (a run, a check or a download). Its result: ours; well (the stops that end well, as
   WELL in website/site/src/lib/software.ts); theirs (any other stop: the person's side); none (sent before 1.0.0
   said how a run ended). Days are India's. */
const RESULT_SQL = `CASE WHEN kind = 'ours' OR ended = 'ours' THEN 'ours' WHEN ended IN ('well', 'nothing_to_do', 'not_listed') THEN 'well'
  WHEN ended IS NULL OR ended = '' THEN 'none' ELSE 'theirs' END`;
const RUNS = `kind IN ('run', 'ours')`, DAY = `date(created_at, '+330 minutes')`;
async function stats(env: Env) {
  const today = new Date(Date.now() + 330 * 60_000).toISOString().slice(0, 10);
  const ago = (n: number) => new Date(Date.parse(today) - n * 86_400_000).toISOString().slice(0, 10);
  const q = (sql: string, ...b: unknown[]) => env.DB.prepare(sql).bind(...b);
  const [days, open, stops, ours, people, last, versions] = (await env.DB.batch([
    /* runs per day, the last 14 days, by result */
    q(`SELECT ${DAY} AS day, ${RESULT_SQL} AS result, COUNT(*) AS n FROM reports WHERE ${RUNS} AND ${DAY} >= ? GROUP BY day, result`, ago(13)),
    /* what waits on someone: ours not fixed, what people sent not fixed, ideas */
    q(`SELECT kind, COUNT(*) AS n FROM reports WHERE state != 'fixed' AND (kind IN ('ours', 'problem', 'idea') OR ended = 'ours') GROUP BY kind`),
    /* why runs stopped on the person's side, the last 30 days */
    q(`SELECT ended, COUNT(*) AS n FROM reports WHERE ${RUNS} AND ${RESULT_SQL} = 'theirs' AND ${DAY} >= ? GROUP BY ended ORDER BY n DESC`, ago(29)),
    /* ours, the last 30 days, the same words together: how often, where, the latest one, how many not fixed */
    q(`SELECT message, place, COUNT(*) AS n, MAX(id) AS latest, SUM(state != 'fixed') AS open FROM reports
        WHERE (kind = 'ours' OR ended = 'ours') AND ${DAY} >= ? GROUP BY message ORDER BY n DESC LIMIT 20`, ago(29)),
    /* each email: how many runs, the last one */
    q(`SELECT lower(email) AS email, SUM(${RUNS}) AS runs, MAX(CASE WHEN ${RUNS} THEN created_at END) AS last FROM reports
        WHERE email != '' GROUP BY lower(email)`),
    /* each email's last run, how it ended (SQLite gives the row the MAX came from) */
    q(`SELECT lower(email) AS email, kind, ended, MAX(id) AS id FROM reports WHERE email != '' AND ${RUNS} GROUP BY lower(email)`),
    /* each email's software version, from its latest report of any kind */
    q(`SELECT lower(email) AS email, version, MAX(id) AS id FROM reports WHERE email != '' GROUP BY lower(email)`),
  ])).map(r => r.results as any[]);
  const lastOf = new Map(last.map(r => [r.email, r])), versionOf = new Map(versions.map(r => [r.email, r.version]));
  return {
    today, keep_days: KEEP_DAYS, days, open, stops, ours,
    people: people.map(p => ({ email: p.email, runs: p.runs, last: p.last, kind: lastOf.get(p.email)?.kind ?? null,
      ended: lastOf.get(p.email)?.ended ?? null, version: versionOf.get(p.email) ?? '' })),
  };
}

async function admin(req: Request, env: Env, path: string, url: URL): Promise<Response> {
  if (!env.ADMIN_KEY || req.headers.get('x-admin-key') !== env.ADMIN_KEY) return json({ ok: false, error: 'forbidden' }, 403);
  await schema(env);
  const state = path.match(/^\/admin\/reports\/(\d+)\/state$/);
  if (state && req.method === 'POST') {
    let b: Record<string, unknown>;
    try { b = await req.json(); } catch { return json({ ok: false, error: 'bad_json' }, 400); }
    if (!['', 'seen', 'fixed'].includes(String(b.state))) return json({ ok: false, error: 'bad_state' }, 400);
    const r = await env.DB.prepare('UPDATE reports SET state = ? WHERE id = ?').bind(String(b.state), Number(state[1])).run();
    return r.meta.changes ? json({ ok: true }) : json({ ok: false, error: 'not_found' }, 404);
  }
  if (req.method !== 'GET') return json({ ok: false, error: 'not_found' }, 404);
  const inside = path.match(/^\/admin\/reports\/(\d+)\/(files|file)$/);
  if (inside) {
    const zip = await env.FILES.get(`records/${inside[1]}.zip`);
    if (!zip) return json({ ok: false, error: 'not_found' }, 404);
    const buf = await zip.arrayBuffer(), list = entries(buf);
    if (inside[2] === 'files') return json({ ok: true, files: list.map(e => ({ name: e.name, size: e.size })) });
    const entry = list.find(e => e.name === url.searchParams.get('name'));
    const body = entry ? await unpack(buf, entry) : null;
    if (!body) return json({ ok: false, error: 'not_found' }, 404);
    const type = TYPES[entry!.name.split('.').pop()!.toLowerCase()] ?? 'text/plain; charset=utf-8';
    return new Response(body, { headers: { 'content-type': type, 'cache-control': 'no-store', 'x-content-type-options': 'nosniff' } });
  }
  const one = path.match(/^\/admin\/reports\/(\d+)(\/record)?$/);
  if (one?.[2]) {
    const file = await env.FILES.get(`records/${one[1]}.zip`);
    return file ? new Response(file.body, { headers: { 'content-type': 'application/zip', 'cache-control': 'no-store' } }) : json({ ok: false, error: 'not_found' }, 404);
  }
  if (one) {
    const row = await env.DB.prepare(`SELECT ${LIST}, log FROM reports WHERE id = ?`).bind(Number(one[1])).first<{ id: number; run: string | null }>();
    if (!row) return json({ ok: false, error: 'not_found' }, 404);
    /* the same run's other reports: the run's own (kind run or ours), and what a person sent about it */
    const same = row.run ? (await env.DB.prepare(`SELECT ${LIST} FROM reports WHERE run = ? AND id != ? ORDER BY id`)
      .bind(row.run, row.id).all()).results : [];
    return json({ ok: true, report: row, same });
  }
  if (path === '/admin/reports') {
    const limit = Math.min(200, Math.max(1, Number(url.searchParams.get('limit')) || 50));
    const kind = url.searchParams.get('kind'), email = url.searchParams.get('email'), before = Number(url.searchParams.get('before')) || 0;
    const where = [kind && 'kind = ?', email && 'email = ?', before && 'id < ?'].filter(Boolean);
    const rows = await env.DB.prepare(`SELECT ${LIST} FROM reports ${where.length ? 'WHERE ' + where.join(' AND ') : ''}
        ORDER BY id DESC LIMIT ?`).bind(...[kind, email, before].filter(Boolean), limit).all();
    return json({ ok: true, reports: rows.results });
  }
  if (path === '/admin/stats') return json({ ok: true, ...(await stats(env)) });
  return json({ ok: false, error: 'not_found' }, 404);
}

/* Deletes what is past KEEP_DAYS: the zips first, then their rows, so a row never points at nothing it would need.
   A thousand at a time (R2's limit for one delete); a day with more carries on the next day. */
export async function forget(env: Env) {
  await schema(env);
  const before = new Date(Date.now() - KEEP_DAYS * 86_400_000).toISOString();
  const old = await env.DB.prepare('SELECT id, record FROM reports WHERE created_at < ? ORDER BY id LIMIT 1000')
    .bind(before).all<{ id: number; record: number }>();
  const ids = old.results.map(r => r.id);
  if (!ids.length) return 0;
  const zips = old.results.filter(r => r.record > 0).map(r => `records/${r.id}.zip`);
  if (zips.length) await env.FILES.delete(zips);
  await env.DB.prepare(`DELETE FROM reports WHERE id IN (${ids.map(() => '?').join(',')})`).bind(...ids).run();
  console.log(`forgot ${ids.length} reports from before ${before}, ${zips.length} with a record`);
  return ids.length;
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url), path = url.pathname.replace(/\/+$/, '') || '/';
    try {
      if (req.method === 'POST' && path === '/report') return await report(req, env);
      const rec = path.match(/^\/report\/(\d+)\/record$/);
      if (req.method === 'PUT' && rec) return await record(req, env, Number(rec[1]), url.searchParams.get('key') || '');
      if ((req.method === 'GET' || req.method === 'POST') && path.startsWith('/admin/')) return await admin(req, env, path, url);
      const fw = await forwardRoutes(req, env, path);
      if (fw) return fw;
      if (path === '/') return new Response('ok', { headers: { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' } });
      return json({ ok: false, error: 'not_found' }, 404);
    } catch (e) {
      console.error(req.method, path, e);
      return json({ ok: false, error: 'failed' }, 500);
    }
  },
  async scheduled(_: ScheduledController, env: Env, ctx: ExecutionContext) {
    ctx.waitUntil(forget(env));
    ctx.waitUntil(tidy(env));
  },
  /* mail to the forwarding address (Cloudflare Email Routing → this Worker) */
  async email(message: ForwardableEmailMessage, env: Env) {
    await receive(message, env);
  },
} satisfies ExportedHandler<Env>;
