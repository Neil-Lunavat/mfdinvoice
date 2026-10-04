/* The software's own server. Small on purpose.

     GET  /automation/latest.json, /automation/<version>.zip    the portal steps: static files, not served from here
     POST /report                                               Send to support, from the app → { ok, id, key }
     PUT  /report/<id>/record?key=<key>                         that report's run record, one zip
     GET  /admin/reports[?limit=50&kind=ours]                   the latest reports          ┐
     GET  /admin/reports/<id>                                   one, with its log lines     ├ x-admin-key
     GET  /admin/reports/<id>/record                            its run record, the zip     │
     GET  /admin/reports/<id>/files                             the names of the files in it│
     GET  /admin/reports/<id>/file?name=<name>                  one of them, unpacked       ┘

   Nobody signs in here. A report says which account and ARN it is from in its own words; that is information for
   whoever reads it, not a check. What keeps the endpoint from being filled is its size limits and a count per sender. */

export interface Env {
  DB: D1Database;
  FILES: R2Bucket;
  ADMIN_KEY: string;
}

const LOG_MAX = 80_000, RECORD_MAX = 20 * 1024 * 1024, PER_HOUR = 60;

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });
const str = (v: unknown, max: number) => (typeof v === 'string' ? v.slice(0, max) : '');
const now = () => new Date().toISOString();

let ready = false;
/* The one table, made the first time it is needed, so a new database needs no separate step. */
async function schema(env: Env) {
  if (ready) return;
  await env.DB.prepare(`CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY, key TEXT NOT NULL, kind TEXT NOT NULL, email TEXT, arn TEXT, message TEXT, place TEXT,
    version TEXT, steps TEXT, pc TEXT, log TEXT, record INTEGER NOT NULL DEFAULT 0, sender TEXT, created_at TEXT NOT NULL)`).run();
  await env.DB.prepare('CREATE INDEX IF NOT EXISTS reports_created ON reports (created_at)').run();
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
  const row = await env.DB.prepare(`INSERT INTO reports (key, kind, email, arn, message, place, version, steps, pc, log, sender, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id`)
    .bind(key, kind, str(b.email, 200), str(b.arn, 40), str(b.message, 4000), str(b.where, 200), str(b.version, 40),
      str(b.steps, 40), str(b.pc, 400), typeof b.log === 'string' ? b.log.slice(-LOG_MAX) : '', sender, now()).first<{ id: number }>();
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

async function admin(req: Request, env: Env, path: string, url: URL): Promise<Response> {
  if (!env.ADMIN_KEY || req.headers.get('x-admin-key') !== env.ADMIN_KEY) return json({ ok: false, error: 'forbidden' }, 403);
  await schema(env);
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
    const row = await env.DB.prepare('SELECT id, kind, email, arn, message, place, version, steps, pc, log, record, created_at FROM reports WHERE id = ?').bind(Number(one[1])).first();
    return row ? json({ ok: true, report: row }) : json({ ok: false, error: 'not_found' }, 404);
  }
  if (path === '/admin/reports') {
    const limit = Math.min(200, Math.max(1, Number(url.searchParams.get('limit')) || 50));
    const kind = url.searchParams.get('kind');
    const rows = await env.DB.prepare(`SELECT id, kind, email, arn, message, place, version, steps, pc, record, created_at FROM reports
        ${kind ? 'WHERE kind = ?' : ''} ORDER BY id DESC LIMIT ?`).bind(...(kind ? [kind, limit] : [limit])).all();
    return json({ ok: true, reports: rows.results });
  }
  return json({ ok: false, error: 'not_found' }, 404);
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url), path = url.pathname.replace(/\/+$/, '') || '/';
    try {
      if (req.method === 'POST' && path === '/report') return await report(req, env);
      const rec = path.match(/^\/report\/(\d+)\/record$/);
      if (req.method === 'PUT' && rec) return await record(req, env, Number(rec[1]), url.searchParams.get('key') || '');
      if (req.method === 'GET' && path.startsWith('/admin/')) return await admin(req, env, path, url);
      if (path === '/') return new Response('ok', { headers: { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' } });
      return json({ ok: false, error: 'not_found' }, 404);
    } catch (e) {
      console.error(req.method, path, e);
      return json({ ok: false, error: 'failed' }, 500);
    }
  },
} satisfies ExportedHandler<Env>;
