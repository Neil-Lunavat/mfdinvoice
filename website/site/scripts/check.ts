/* bun run check [-- --no-build] [-- --keep]
   Builds the site, applies the migrations to a fresh local database (.check/), and runs the Worker under
   `wrangler dev` three times over that database: as the public site, as the admin panel's host and as the blog
   editor's host (each with --local-upstream, so the Worker sees that host). Emails are printed (EMAIL_CONSOLE=1)
   and read back from the logs. Cloudflare Access is played by a local key server: the check makes its own RSA key,
   serves it as the team's certs, and signs test JWTs with it. The live verification is the same code, pointed at
   the real team's certs. Prints PASS or FAIL for each check; exits 1 if any failed.
   --keep: afterwards, leave the three running (with the check's data) to look around in a browser: the panel on
   http://localhost:8800 and the blog editor on http://localhost:8801, each through a small proxy that adds the
   Access JWT a browser can't (also written to .check/tokens.json). */
import { spawn, spawnSync, type Subprocess } from 'bun';
import { rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { monthsLeft, quote, extraFor } from '../src/lib/price';
import { TERMS_VERSION } from '../src/consts';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const PERSIST = '.check';
const PORTS = { site: 8788, control: 8789, write: 8790 } as const;
const HOSTS = { site: 'site.test', control: 'control.test', write: 'write.test' } as const;
const TEAM = 'http://127.0.0.1:8799', AUD = { control: 'aud-control', write: 'aud-write' };
const ADMIN = 'admin@check.test', WRITER = 'writer@check.test', OWNER = 'neillunavat3192@gmail.com', SUPPORT = 'support@mfdinvoice.co.in';

/* ---- output ---- */
let failed = 0, passed = 0;
function result(name: string, ok: boolean, detail = '') {
  if (ok) passed++; else failed++;
  console.log(`${ok ? '\x1b[32mPASS\x1b[0m' : '\x1b[31mFAIL\x1b[0m'} ${name}${!ok && detail ? ` — ${detail}` : ''}`);
}
async function check(name: string, fn: () => Promise<true | string>) {
  try { const r = await fn(); result(name, r === true, r === true ? '' : r); }
  catch (e) { result(name, false, e instanceof Error ? e.message : String(e)); }
}
const expect = (cond: unknown, why: string) => { if (!cond) throw new Error(why); };

/* ---- processes ---- */
const procs: Subprocess[] = [];
let LOG = '';
function run(cmd: string[], opts: { quiet?: boolean } = {}) {
  const r = spawnSync(cmd, { cwd: ROOT, stdout: 'pipe', stderr: 'pipe' });
  if (r.exitCode !== 0) { console.error(r.stdout.toString(), r.stderr.toString()); throw new Error(`${cmd.slice(0, 4).join(' ')} failed`); }
  if (!opts.quiet) process.stdout.write('.');
  return r.stdout.toString();
}
async function pump(stream: ReadableStream<Uint8Array>) {
  const dec = new TextDecoder();
  for await (const chunk of stream) LOG += dec.decode(chunk);
}
function stopAll() {
  for (const p of procs) { try { spawnSync(['taskkill', '/PID', String(p.pid), '/T', '/F'], { stdout: 'ignore', stderr: 'ignore' }); } catch {} try { p.kill(); } catch {} }
}
process.on('exit', stopAll);
process.on('SIGINT', () => { stopAll(); process.exit(130); });

const sql = (command: string) => run(['bunx', 'wrangler', 'd1', 'execute', 'site-db', '--local', '--persist-to', PERSIST, '--command', command], { quiet: true });

/* ---- Cloudflare Access, played locally ---- */
const b64u = (b: ArrayBuffer | Uint8Array | string) =>
  Buffer.from(typeof b === 'string' ? b : b instanceof Uint8Array ? b : new Uint8Array(b)).toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const alg = { name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' };
const teamKey = await crypto.subtle.generateKey(alg, true, ['sign', 'verify']) as CryptoKeyPair;
const forgedKey = await crypto.subtle.generateKey(alg, true, ['sign', 'verify']) as CryptoKeyPair;
const jwk = await crypto.subtle.exportKey('jwk', teamKey.publicKey);
const certs = Bun.serve({ port: 8799, hostname: '127.0.0.1', fetch: () => Response.json({ keys: [{ ...jwk, kid: 'check', alg: 'RS256', use: 'sig' }] }) });
/* The software's own server, played here: three things the app sent, one with a record of two files, and a person's
   message about the first run. */
const SOFT = 'http://127.0.0.1:8798', SOFT_KEY = 'check-admin-key';
const sent: Record<string, any>[] = [
  { id: 3, kind: 'problem', email: 'buyer@check.test', arn: 'ARN-111111', message: 'Axis looks wrong to me', place: 'Overview',
    version: '1.0.0', steps: '2026.10.04.0233', pc: 'DESKTOP-4K2P', record: 0, created_at: '2026-10-04T04:06:51.983Z', run: 'r1', ended: null, seconds: null, state: '' },
  { id: 2, kind: 'ours', email: 'buyer@check.test', arn: 'ARN-111111', message: 'A page isn’t what the app expects', place: 'run · OCT-2026',
    version: '1.0.0', steps: '2026.10.04.0233', pc: 'DESKTOP-4K2P', record: 2048, created_at: '2026-10-04T03:06:51.983Z', run: 'r2', ended: 'ours', seconds: 95, state: '' },
  { id: 1, kind: 'run', email: 'buyer@check.test', arn: 'ARN-111111', message: '17 invoices submitted for October.', place: 'run · OCT-2026',
    version: '1.0.0', steps: '2026.10.04.0233', pc: 'DESKTOP-4K2P', record: 0, created_at: '2026-10-04T02:06:51.983Z', run: 'r1', ended: 'well', seconds: 312, state: '' },
  /* the rest: only to look at (--keep) */
  { id: 9, kind: 'idea', email: 'gift1@check.test', arn: 'ARN-333333', message: 'Could it also do the TDS certificates?', place: 'Settings',
    version: '1.0.0', steps: '2026.10.04.0233', pc: 'OFFICE-PC · Windows 11 · 8 GB · 120 GB free', record: 0, created_at: '2026-10-03T09:10:00.000Z', run: null, ended: null, seconds: null, state: 'seen' },
  { id: 8, kind: 'run', email: 'gift1@check.test', arn: 'ARN-333333', message: 'CAMS says the figures differ for Axis', place: 'run · OCT-2026',
    version: '1.0.0', steps: '2026.10.04.0233', pc: 'OFFICE-PC · Windows 11 · 8 GB · 120 GB free', record: 0, created_at: '2026-10-03T08:40:00.000Z', run: 'r8', ended: 'mismatch', seconds: 141, state: '' },
  { id: 7, kind: 'run', email: 'gift1@check.test', arn: 'ARN-333333', message: 'stopped', place: 'check · OCT-2026',
    version: '1.0.0', steps: '2026.10.04.0233', pc: 'OFFICE-PC · Windows 11 · 8 GB · 120 GB free', record: 0, created_at: '2026-10-03T08:20:00.000Z', run: 'r7', ended: 'stopped', seconds: 22, state: '' },
  { id: 6, kind: 'run', email: 'trial@check.test', arn: 'ARN-222222', message: 'October isn’t listed yet', place: 'run · OCT-2026',
    version: '1.0.0', steps: '2026.10.04.0233', pc: 'LAPTOP-RM · Windows 11 · 16 GB · 300 GB free', record: 0, created_at: '2026-10-02T11:00:00.000Z', run: 'r6', ended: 'not_listed', seconds: 48, state: '' },
  { id: 5, kind: 'ours', email: 'trial@check.test', arn: 'ARN-222222', message: 'Something in MFDInvoice went wrong', place: 'download · SEP-2026',
    version: '1.0.0', steps: '2026.10.02.1010', pc: 'LAPTOP-RM · Windows 11 · 16 GB · 300 GB free', record: 0, created_at: '2026-10-02T10:00:00.000Z', run: 'r5', ended: 'ours', seconds: 63, state: 'fixed' },
  { id: 4, kind: 'run', email: 'trial@check.test', arn: 'ARN-222222', message: '6 invoices read for September.', place: 'download · SEP-2026',
    version: '1.0.3', steps: '2026.10.01.0900', pc: 'LAPTOP-RM', record: 0, created_at: '2026-10-01T10:00:00.000Z', run: null, ended: null, seconds: null, state: '' },
];
Bun.serve({ port: 8798, hostname: '127.0.0.1', fetch: async req => {
  const u = new URL(req.url);
  if (req.headers.get('x-admin-key') !== SOFT_KEY) return Response.json({ ok: false, error: 'forbidden' }, { status: 403 });
  if (u.pathname === '/admin/reports') {
    const k = u.searchParams.get('kind'), e = u.searchParams.get('email'), before = Number(u.searchParams.get('before')) || 0;
    return Response.json({ ok: true, reports: sent.filter(r => (!k || r.kind === k) && (!e || r.email === e) && (!before || r.id < before)) });
  }
  /* the counts, as the real server makes them in SQL (server/src/index.ts, stats) */
  if (u.pathname === '/admin/stats') {
    const ist = (t: string) => new Date(Date.parse(t) + 330 * 60_000).toISOString().slice(0, 10);
    const today = ist(new Date().toISOString()), ago = (n: number) => new Date(Date.parse(today) - n * 864e5).toISOString().slice(0, 10);
    const res = (r: any) => r.kind === 'ours' || r.ended === 'ours' ? 'ours' : ['well', 'nothing_to_do', 'not_listed'].includes(r.ended) ? 'well' : !r.ended ? 'none' : 'theirs';
    const count = (xs: any[], key: (x: any) => string) => Object.entries(xs.reduce((m, x) => (m[key(x)] = (m[key(x)] ?? 0) + 1, m), {} as Record<string, number>));
    const runs = sent.filter(r => r.kind === 'run' || r.kind === 'ours');
    const days = count(runs.filter(r => ist(r.created_at) >= ago(13)), r => `${ist(r.created_at)}|${res(r)}`).map(([k, n]) => ({ day: k.split('|')[0], result: k.split('|')[1], n }));
    const open = count(sent.filter(r => r.state !== 'fixed' && (['ours', 'problem', 'idea'].includes(r.kind) || r.ended === 'ours')), r => r.kind).map(([kind, n]) => ({ kind, n }));
    const stops = count(runs.filter(r => res(r) === 'theirs' && ist(r.created_at) >= ago(29)), r => r.ended).map(([ended, n]) => ({ ended, n }));
    const oursRows = sent.filter(r => (r.kind === 'ours' || r.ended === 'ours') && ist(r.created_at) >= ago(29));
    const ours = count(oursRows, r => r.message).map(([message, n]) => {
      const g = oursRows.filter(r => r.message === message);
      return { message, place: g[0].place, n, latest: Math.max(...g.map(r => r.id)), open: g.filter(r => r.state !== 'fixed').length };
    });
    const people = [...new Set(sent.map(r => r.email))].map(email => {
      const mine = sent.filter(r => r.email === email).sort((a, b) => b.id - a.id), rr = mine.filter(r => r.kind === 'run' || r.kind === 'ours');
      return { email, runs: rr.length, last: rr[0]?.created_at ?? null, kind: rr[0]?.kind ?? null, ended: rr[0]?.ended ?? null, version: mine[0].version };
    });
    return Response.json({ ok: true, today, keep_days: 90, days, open, stops, ours, people });
  }
  const st = u.pathname.match(/^\/admin\/reports\/(\d+)\/state$/);
  if (st && req.method === 'POST') {
    const r = sent.find(x => x.id === +st[1]), b = await req.json() as { state: string };
    if (!r) return Response.json({ ok: false, error: 'not_found' }, { status: 404 });
    r.state = b.state; return Response.json({ ok: true });
  }
  const m = u.pathname.match(/^\/admin\/reports\/(\d+)(\/files|\/file|\/record)?$/);
  const one = m && sent.find(r => r.id === +m[1]);
  if (!m || !one) return Response.json({ ok: false, error: 'not_found' }, { status: 404 });
  if (!m[2]) return Response.json({ ok: true, report: { ...one, log: 'the app’s last log lines' }, same: sent.filter(r => r.run === one.run && r.id !== one.id) });
  if (m[2] === '/files') return Response.json({ ok: true, files: [{ name: '01-cams-status.png', size: PNG.length }, { name: 'log.txt', size: 9 }] });
  if (m[2] === '/file') return u.searchParams.get('name') === '01-cams-status.png' ? new Response(PNG, { headers: { 'content-type': 'image/png' } }) : new Response('log lines');
  return new Response('zip', { headers: { 'content-type': 'application/zip' } });
} });
async function jwt(email: string, aud: string, o: { key?: CryptoKey; exp?: number; iss?: string } = {}) {
  const now = Math.floor(Date.now() / 1000);
  const h = b64u(JSON.stringify({ alg: 'RS256', kid: 'check', typ: 'JWT' }));
  const p = b64u(JSON.stringify({ aud: [aud], email, exp: o.exp ?? now + 600, iat: now, nbf: now, iss: o.iss ?? TEAM, sub: email, type: 'app' }));
  const sig = await crypto.subtle.sign('RSASSA-PKCS1-v1_5', o.key ?? teamKey.privateKey, new TextEncoder().encode(`${h}.${p}`));
  return `${h}.${p}.${b64u(sig)}`;
}

/* ---- HTTP, like a browser (cookies, Origin) or like the app ---- */
type Res = { status: number; json: any; text: string; headers: Headers };
class Client {
  cookies = new Map<string, string>();
  constructor(public app: keyof typeof PORTS = 'site', public ip = '10.0.0.1', public token = '') {}
  async req(method: string, path: string, body?: object | FormData | Uint8Array, extra: Record<string, string> = {}): Promise<Res> {
    const headers: Record<string, string> = { 'cf-connecting-ip': this.ip, 'user-agent': 'check', ...extra };
    if (this.cookies.size) headers.cookie = [...this.cookies].map(([k, v]) => `${k}=${v}`).join('; ');
    if (method !== 'GET') headers.origin = `https://${HOSTS[this.app]}`;
    if (this.token) headers['cf-access-jwt-assertion'] = this.token;
    let payload: BodyInit | undefined;
    if (body instanceof FormData || body instanceof Uint8Array) payload = body;
    else if (body) { payload = JSON.stringify(body); headers['content-type'] = 'application/json'; }
    let r = await fetch(`http://127.0.0.1:${PORTS[this.app]}${path}`, { method, headers, body: payload, redirect: 'manual' });
    /* the local runtime drops a request now and then while another process holds the database file: once more */
    if (r.status >= 500 && r.headers.get('content-type')?.includes('text/plain')) {
      const t = await r.clone().text();
      if (/Network connection lost/i.test(t)) { await Bun.sleep(500); r = await fetch(`http://127.0.0.1:${PORTS[this.app]}${path}`, { method, headers, body: payload, redirect: 'manual' }); }
    }
    for (const c of r.headers.getSetCookie()) { const [kv] = c.split(';'); const [k, v] = kv.split('='); if (v) this.cookies.set(k, v); else this.cookies.delete(k); }
    const text = await r.text();
    let json: any = null; try { json = JSON.parse(text); } catch {}
    return { status: r.status, json, text, headers: r.headers };
  }
  get = (p: string, h?: Record<string, string>) => this.req('GET', p, undefined, h);
  post = (p: string, b?: object | FormData, h?: Record<string, string>) => this.req('POST', p, b ?? {}, h);
}

/* ---- emails, read back from the logs ---- */
type Email = { to: string; from: string; replyTo: string; subject: string; text: string };
function emailsSince(mark: number): Email[] {
  return [...LOG.slice(mark).matchAll(/--- email to (\S+) ---\r?\nFrom: (\S+)\r?\nReply-To: (\S+)\r?\nSubject: (.*)\r?\n([\s\S]*?)--- end ---/g)]
    .map(m => ({ to: m[1], from: m[2], replyTo: m[3], subject: m[4].trim(), text: m[5] }));
}
const settle = () => Bun.sleep(250);
async function mailTo(addr: string, mark: number, match?: RegExp) {
  for (let i = 0; i < 20; i++) {
    const m = emailsSince(mark).filter(e => e.to === addr && (!match || match.test(e.subject + '\n' + e.text)));
    if (m.length) return m[m.length - 1];
    await Bun.sleep(150);
  }
  return null;
}

let ipN = 1;
const freshIp = () => `10.1.${Math.floor(ipN / 250)}.${(ipN++ % 250) + 1}`;

/* Signs in on the website: a code by email, then the code. */
async function signIn(email: string, c = new Client('site', freshIp())) {
  let mark = LOG.length;
  let r1 = await c.post('/api/auth/code', { email });
  if (r1.json?.error === 'wait') {
    /* signed in under 45 seconds ago: move the last code back in time rather than wait */
    sql(`UPDATE codes SET created_at = '2020-01-01T00:00:00.000Z' WHERE email = '${email}'`);
    mark = LOG.length;
    r1 = await c.post('/api/auth/code', { email });
  }
  expect(r1.status === 200, `code for ${email}: ${r1.status} ${r1.text}`);
  const m = await mailTo(email, mark, /is your/);
  expect(m, `no code email for ${email}`);
  const code = m!.subject.match(/^(\d{6})/)![1];
  const r2 = await c.post('/api/auth/verify', { email, code, keep: true });
  expect(r2.status === 200, `verify ${email}: ${r2.status} ${r2.text}`);
  return { c, verify: r2.json };
}
/* The app, signed in as an account: its token (asked for once, and again if it was ended), and what it calls. */
const appTokens = new Map<number, string>();
async function appToken(id: number) {
  if (appTokens.has(id)) return appTokens.get(id)!;
  const email = (sql(`SELECT email FROM accounts WHERE id = ${id}`).match(/"email": "([^"]+)"/) ?? [])[1];
  sql(`UPDATE codes SET created_at = '2020-01-01T00:00:00.000Z' WHERE email = '${email}'`);
  const app = new Client('site', freshIp()), mark = LOG.length;
  await app.post('/api/app/code', { email });
  const code = (await mailTo(email, mark, /is your/))!.subject.slice(0, 6);
  const token = (await app.post('/api/app/verify', { email, code, replace: true })).json.token as string;
  appTokens.set(id, token);
  return token;
}
async function asApp(id: number | null, method: 'GET' | 'POST', path: string, body?: object): Promise<Res> {
  const call = async () => new Client('site', freshIp()).req(method, path, body, { authorization: `Bearer ${await appToken(id!)}` });
  const r = await call();
  if (r.status !== 401) return r;
  appTokens.delete(id!);                 /* signed out everywhere since: the app signs in again */
  return call();
}
/* Add an ARN in the app (/api/app/bind), and the plan as the app is told it (/api/app/me). */
const appBind = (id: number | null, arn: string, holder: string) => asApp(id, 'POST', '/api/app/bind', { arn, holder });
const licence = (id: number | null) => asApp(id, 'GET', '/api/app/me');
const uidOf = async (id: number | null) => (sql(`SELECT uid FROM accounts WHERE id = ${id}`).match(/"uid": "([0-9a-f]{16})"/) ?? [])[1];
const accountId = async (email: string) => {
  const out = sql(`SELECT id FROM accounts WHERE email = '${email}'`);
  const m = out.match(/"id":\s*(\d+)/);
  return m ? +m[1] : null;
};
const PNG = new Uint8Array(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==', 'base64'));
const png = (name = 'shot.png') => new File([PNG], name, { type: 'image/png' });

/* ======================================================================================= */
async function main() {
  process.chdir(ROOT);
  if (!process.argv.includes('--no-build')) { console.log('Building…'); run(['bun', 'run', 'build']); }
  rmSync(PERSIST, { recursive: true, force: true });
  console.log('\nA fresh local database…');
  run(['bunx', 'wrangler', 'd1', 'migrations', 'apply', 'site-db', '--local', '--persist-to', PERSIST]);
  const vars = {
    EMAIL_CONSOLE: '1', SITE_ORIGIN: 'https://site.test', CONTROL_HOST: HOSTS.control, WRITE_HOST: HOSTS.write,
    ACCESS_TEAM: TEAM, ACCESS_AUD_CONTROL: AUD.control, ACCESS_AUD_WRITE: AUD.write,
    ADMINS: ADMIN, WRITERS: WRITER, PAYMENTS: 'upi', SOFTWARE_SERVER: SOFT, SOFTWARE_ADMIN_KEY: SOFT_KEY,
  };
  console.log('\nStarting the Worker three times (site, control, write)…');
  let inspector = 9330;
  for (const [app, port] of Object.entries(PORTS)) {
    const p = spawn(['bunx', 'wrangler', 'dev', '--port', String(port), '--inspector-port', String(inspector++), '--persist-to', PERSIST,
      '--local-upstream', HOSTS[app as keyof typeof HOSTS], '--upstream-protocol', 'https', ...(app === 'site' ? ['--test-scheduled'] : []),
      ...Object.entries(vars).flatMap(([k, v]) => ['--var', `${k}:${v}`])], { cwd: ROOT, stdout: 'pipe', stderr: 'pipe' });
    procs.push(p); pump(p.stdout); pump(p.stderr);
    /* one at a time: three runtimes opening the same database at once trip over its lock */
    for (let i = 0; ; i++) {
      try { await fetch(`http://127.0.0.1:${port}/robots.txt`); break; } catch {}
      if (i > 90) throw new Error(`wrangler dev on ${port} didn't start:\n${LOG.slice(-3000)}`);
      await Bun.sleep(1000);
    }
  }
  console.log('Ready.\n');
  const admin = new Client('control', '10.9.0.1', await jwt(ADMIN, AUD.control));
  const writer = new Client('write', '10.9.0.2', await jwt(WRITER, AUD.write));
  /* the Worker's scheduled handler, as the Cron Trigger calls it (Miniflare's local trigger) */
  const cron = async (c: string) => {
    const r = await fetch(`http://127.0.0.1:${PORTS.site}/cdn-cgi/local/scheduled?cron=${encodeURIComponent(c)}`);
    expect(r.ok, `the scheduled trigger: ${r.status} ${await r.text()}`);
    await Bun.sleep(1500);
  };
  const HOURLY = '0 * * * *', DAILY = '30 20 * * *';

  /* ---- sign-in ---- */
  await check('sign-in: a new email gets a code, and the code creates the account', async () => {
    const { c } = await signIn('new@check.test');
    const me = await c.get('/api/me');
    return me.json?.signed_in === true && me.json.email === 'new@check.test' ? true : me.text;
  });
  await check('sign-in: a Gmail alias is the same account (+tag and dots dropped)', async () => {
    const c = new Client('site', freshIp()), mark = LOG.length;
    const r = await c.post('/api/auth/code', { email: 'R.K.Mehta+tax@Gmail.com' });
    expect(r.status === 200, `code: ${r.text}`);
    const code = (await mailTo('rkmehta@gmail.com', mark, /is your/))!.subject.slice(0, 6);
    const v = await c.post('/api/auth/verify', { email: 'rkmehta+other@gmail.com', code, keep: true });
    expect(v.status === 200 && v.json.email === 'rkmehta@gmail.com', `verify: ${v.text}`);
    const me = await c.get('/api/me');
    return me.json?.email === 'rkmehta@gmail.com' ? true : me.text;
  });
  await check('sign-in: three wrong codes lock it, then the right code is refused', async () => {
    const c = new Client('site', freshIp()), email = 'wrong@check.test', mark = LOG.length;
    await c.post('/api/auth/code', { email });
    const code = (await mailTo(email, mark))!.subject.slice(0, 6);
    const bad = code === '000000' ? '111111' : '000000';
    const a = await c.post('/api/auth/verify', { email, code: bad }), b = await c.post('/api/auth/verify', { email, code: bad }), d = await c.post('/api/auth/verify', { email, code: bad });
    const e = await c.post('/api/auth/verify', { email, code });
    return a.json.error === 'wrong' && a.json.tries_left === 2 && b.json.tries_left === 1 && d.json.error === 'locked' && e.json.error === 'locked' ? true : [a, b, d, e].map(x => x.text).join(' | ');
  });
  await check('sign-in: a resend within 45 seconds is refused', async () => {
    const c = new Client('site', freshIp());
    await c.post('/api/auth/code', { email: 'resend@check.test' });
    const r = await c.post('/api/auth/code', { email: 'resend@check.test' });
    return r.status === 429 && r.json.error === 'wait' && r.json.wait > 0 ? true : r.text;
  });

  /* ---- UPI ---- */
  let buyerId = 0, buyer: Client;
  await check('UPI: order → screenshot → the owner is emailed a link to the panel', async () => {
    ({ c: buyer } = await signIn('buyer@check.test'));
    const o = await buyer.post('/api/checkout/order', { kind: 'new', arns: 1, name: 'Neil Lunavat', address: '1 Main Road, Pune' });
    expect(o.status === 200 && o.json.provider === 'upi' && /^MFD-[A-Z0-9]{6}$/.test(o.json.order_id), `order: ${o.text}`);
    expect(o.json.amount === 400000, `amount ${o.json.amount}`);
    const fd = new FormData(); fd.append('order_id', o.json.order_id); fd.append('screenshot', png()); fd.append('utr', '123456789012');
    const mark = LOG.length;
    const p = await buyer.post('/api/checkout/proof', fd);
    expect(p.status === 200, `proof: ${p.text}`);
    const m = await mailTo(OWNER, mark, /Payment to check/);
    expect(await mailTo(SUPPORT, mark, /Payment to check/), 'support@ didn’t get the payment to check');
    expect(m && m.text.includes(`https://control.mfdinvoice.co.in/payments#${o.json.order_id}`) || m?.text.includes(`/payments#${o.json.order_id}`), 'no panel link in the owner email');
    const got = await mailTo('buyer@check.test', mark, /received your/);
    expect(got && got.text.includes(o.json.order_id) && got.text.includes('₹4,000.00'), 'no “we’ve received your payment” email to the buyer');
    buyerId = (await accountId('buyer@check.test'))!;
    (globalThis as any).ref1 = o.json.order_id;
    return true;
  });
  await check('UPI: approve in the panel → the plan starts and receipt MFDI/…/0001 is emailed', async () => {
    const ref = (globalThis as any).ref1, mark = LOG.length;
    const r = await admin.post('/api/admin/payments', { action: 'approve', ref });
    expect(r.status === 200 && /^MFDI\/\d{2}-\d{2}\/0001$/.test(r.json.invoice), `approve: ${r.text}`);
    const m = await mailTo('buyer@check.test', mark, /payment is confirmed/);
    expect(m && m.text.includes(r.json.invoice) && m.text.includes('https://site.test/downloads'), 'no “payment is confirmed” email with the download and the receipt');
    const lic = await licence(buyerId);
    expect(lic.json.active === true && lic.json.source === 'paid' && lic.json.slots === 1, `licence: ${lic.text}`);
    const page = await admin.get(`/accounts/${await uidOf(buyerId)}`);
    return page.text.includes('Payment approved') ? true : 'no activity row';
  });
  await check('UPI: reject, reason ticked → emailed with it, nothing applies, and they can’t pay again', async () => {
    const { c } = await signIn('rejected@check.test');
    const o = await c.post('/api/checkout/order', { kind: 'new', arns: 1, name: 'A B', address: 'Somewhere' });
    const fd = new FormData(); fd.append('order_id', o.json.order_id); fd.append('screenshot', png());
    await c.post('/api/checkout/proof', fd);
    const mark = LOG.length;
    const r = await admin.post('/api/admin/payments', { action: 'reject', ref: o.json.order_id, note: 'The money didn’t arrive.', tell: true });
    expect(r.status === 200, `reject: ${r.text}`);
    const m = await mailTo('rejected@check.test', mark, /couldn’t verify/);
    expect(m && m.text.includes('The money didn’t arrive.'), 'no rejection email with the reason');
    expect((await c.get('/api/me')).json.active === false, 'a plan applied');
    const again = await c.post('/api/checkout/order', { kind: 'new', arns: 1, name: 'A B', address: 'Somewhere' });
    expect(again.status === 409 && again.json.error === 'rejected', `paid again: ${again.text}`);
    const page = await c.get('/checkout');
    expect(page.text.includes('couldn’t verify your payment') && page.text.includes('The money didn’t arrive.'), 'Checkout doesn’t say so, with the reason');
    const list = await admin.get('/payments');
    expect(list.text.includes(o.json.order_id) && list.text.includes('The money didn’t arrive.'), 'not listed in Payments');
    (globalThis as any).rejRef = o.json.order_id;
    return true;
  });
  await check('UPI: Unblock → the same reference opens again; a new screenshot → back to check → approved', async () => {
    const { c } = await signIn('rejected@check.test');
    const ref = (globalThis as any).rejRef;
    const um = LOG.length;
    const u = await admin.post('/api/admin/payments', { action: 'unblock', ref, tell: true });
    expect(u.status === 200, `unblock: ${u.text}`);
    expect(await mailTo('rejected@check.test', um, /can pay again/), 'not told they can pay again');
    expect((await admin.post('/api/admin/payments', { action: 'unblock', ref })).json.error === 'not_blocked', 'unblocked twice');
    expect(!(await admin.get('/payments')).text.includes(ref), 'still listed after unblocking');
    const o = await c.post('/api/checkout/order', { kind: 'new', arns: 1, name: 'A B', address: 'Somewhere' });
    expect(o.status === 200 && o.json.order_id === ref, `order after unblock: ${o.text}`);
    const fd = new FormData(); fd.append('order_id', ref); fd.append('screenshot', png()); fd.append('utr', '111122223333');
    expect((await c.post('/api/checkout/proof', fd)).status === 200, 'screenshot refused');
    const a = await admin.post('/api/admin/payments', { action: 'approve', ref });
    expect(a.status === 200 && a.json.invoice, `approve: ${a.text}`);
    return (await c.get('/api/me')).json.active === true ? true : 'no plan';
  });
  await check('UPI: reject, reason not ticked → not emailed nor shown; the block survives deleting the account', async () => {
    const { c } = await signIn('rejected2@check.test');
    const o = await c.post('/api/checkout/order', { kind: 'new', arns: 1, name: 'C D', address: 'Elsewhere' });
    const fd = new FormData(); fd.append('order_id', o.json.order_id); fd.append('screenshot', png()); fd.append('utr', '998877665544');
    await c.post('/api/checkout/proof', fd);
    const mark = LOG.length;
    await admin.post('/api/admin/payments', { action: 'reject', ref: o.json.order_id, note: 'Sent the same screenshot twice.' });
    const m = await mailTo('rejected2@check.test', mark, /couldn’t verify/);
    expect(m && !m.text.includes('Sent the same screenshot twice.'), 'the private reason was emailed');
    expect(!(await c.get('/checkout')).text.includes('Sent the same screenshot twice.'), 'the private reason is on Checkout');
    expect((await admin.get('/payments')).text.includes('Sent the same screenshot twice.'), 'reason not in the panel');
    await admin.post('/api/admin/accounts', { action: 'delete', accounts: [await accountId('rejected2@check.test')] });
    const { c: c2 } = await signIn('rejected2@check.test');
    const again = await c2.post('/api/checkout/order', { kind: 'new', arns: 1, name: 'C D', address: 'Elsewhere' });
    expect(again.status === 409 && again.json.error === 'rejected', `paid again after deletion: ${again.text}`);
    const ap = await admin.post('/api/admin/payments', { action: 'approve', ref: o.json.order_id });
    return ap.json.error === 'no_account' ? true : `approve for a deleted account: ${ap.text}`;
  });
  await check('UPI: a rejected payment approved after all → the plan starts', async () => {
    const { c } = await signIn('rejected3@check.test');
    const o = await c.post('/api/checkout/order', { kind: 'new', arns: 1, name: 'E F', address: 'Here' });
    const fd = new FormData(); fd.append('order_id', o.json.order_id); fd.append('screenshot', png());
    await c.post('/api/checkout/proof', fd);
    await admin.post('/api/admin/payments', { action: 'reject', ref: o.json.order_id });
    const a = await admin.post('/api/admin/payments', { action: 'approve', ref: o.json.order_id });
    expect(a.status === 200 && a.json.invoice, `approve: ${a.text}`);
    expect((await admin.post('/api/admin/payments', { action: 'approve', ref: o.json.order_id })).json.error === 'already_paid', 'approved twice');
    return (await c.get('/api/me')).json.active === true ? true : 'no plan';
  });

  await check('Sales: the paid order with its receipt and approver; filters; account links by uid, never the number', async () => {
    const ref = (globalThis as any).ref1;
    const all = await admin.get('/sales');
    expect(all.text.includes(ref) && /MFDI\/\d{2}-\d{2}\/0001/.test(all.text) && all.text.includes(ADMIN), 'the sale, receipt or approver is missing');
    expect(all.text.includes(`/accounts/${await uidOf(buyerId)}`), 'no uid link');
    expect(!(await admin.get('/sales?q=nothing-like-this')).text.includes(ref), 'search didn’t filter');
    expect(!(await admin.get('/sales?kind=add')).text.includes(ref), 'kind didn’t filter');
    const num = all.text.match(/MFDI\/\d{2}-\d{2}\/0001/)![0];
    const rc = await admin.get(`/receipts/${num}`);
    expect(rc.status === 200 && rc.text.includes(num) && rc.text.includes('Neil Lunavat'), `the receipt in the panel: ${rc.status}`);
    return (await admin.get(`/accounts/${buyerId}`)).status === 404 ? true : 'the number still opens an account';
  });
  await check('the Terms version is saved with the order, and Checkout says so', async () => {
    const out = sql(`SELECT terms FROM orders WHERE id = '${(globalThis as any).ref1}'`);
    expect(out.includes(`"terms": "${TERMS_VERSION}"`), `terms not saved: ${out.slice(out.indexOf('"results"'), out.indexOf('"results"') + 120)}`);
    const { c } = await signIn('terms@check.test');
    const page = await c.get('/checkout');
    return page.text.includes('By paying, you agree to the') ? true : 'no agree line on Checkout';
  });
  await check('survey: bad answers refused; answers saved; in the panel (counts, the account, “other”)', async () => {
    const bad = await buyer.post('/api/survey', { size: 'huge' });
    expect(bad.status === 400, `bad answer: ${bad.status}`);
    const r = await buyer.post('/api/survey', { heard: 'other', heard_other: 'A friend at AMFI', kind: 'firm', size: '2-5', invoices: '10-50' });
    expect(r.status === 200, `survey: ${r.text}`);
    const [page, acct] = await Promise.all([admin.get('/survey'), admin.get(`/accounts/${await uidOf(buyerId)}`)]);
    return page.text.includes('A friend at AMFI') && acct.text.includes('2–5 people') && acct.text.includes('A distribution firm with a team') ? true : 'not shown in the panel';
  });
  await check('download: none uploaded yet → the installer is missing; a bad token → 401', async () => {
    /* the app's token, for an account with an active plan */
    sql(`UPDATE codes SET created_at = '2020-01-01T00:00:00.000Z' WHERE email = 'buyer@check.test'`);
    const app = new Client('site', freshIp()), mark = LOG.length;
    await app.post('/api/app/code', { email: 'buyer@check.test' });
    const code = (await mailTo('buyer@check.test', mark, /is your/))!.subject.slice(0, 6);
    const tok = (await app.post('/api/app/verify', { email: 'buyer@check.test', code, replace: true })).json.token;
    const dl = await new Client('site', freshIp()).get('/api/download', { authorization: `Bearer ${tok}` });
    expect(dl.status === 503 && dl.json.error === 'installer_missing', `download: ${dl.status}`);
    const bad = await new Client('site', freshIp()).get('/api/download', { authorization: 'Bearer nope' });
    return bad.status === 401 ? true : `bad token: ${bad.status}`;
  });

  /* ---- gifts ---- */
  await check('gift before sign-up: emailed, then starts at sign-in (source grant)', async () => {
    const mark = LOG.length;
    const g = await admin.post('/api/admin/gifts', { action: 'give', email: 'gift1@check.test' });
    expect(g.status === 200 && g.json.started === false, `give: ${g.text}`);
    expect(await mailTo('gift1@check.test', mark, /gifted/), 'no gift email');
    const { verify } = await signIn('gift1@check.test');
    expect(verify.gift_until && verify.gift_until_text, `sign-in didn't say the gift started: ${JSON.stringify(verify)}`);
    const lic = await licence(await accountId('gift1@check.test'));
    return lic.json.active && lic.json.source === 'grant' ? true : lic.text;
  });
  await check('gift: used exactly once (signing in again changes nothing)', async () => {
    const id = await accountId('gift1@check.test');
    const before = (await licence(id)).json.paid_until;
    await signIn('gift1@check.test');
    const out = sql(`SELECT COUNT(*) AS n FROM gifts WHERE email = 'gift1@check.test' AND used_at IS NOT NULL`);
    const after = (await licence(id)).json.paid_until;
    return /"n":\s*1\b/.test(out) && before === after ? true : `${out} ${before} ${after}`;
  });
  await check('gift after sign-up (no plan): starts at once, “has started” email', async () => {
    await signIn('gift2@check.test');
    const mark = LOG.length;
    const g = await admin.post('/api/admin/gifts', { action: 'give', email: 'gift2@check.test' });
    expect(g.json.started === true, `give: ${g.text}`);
    expect(await mailTo('gift2@check.test', mark, /has started/), 'no “started” email');
    return (await licence(await accountId('gift2@check.test'))).json.active === true ? true : 'no plan';
  });
  await check('gift for someone who has had a plan: refused', async () => {
    const g = await admin.post('/api/admin/gifts', { action: 'give', email: 'gift1@check.test' });
    return g.status === 400 && g.json.error === 'had_plan' ? true : `give: ${g.text}`;
  });
  await check('gift revoked: never starts; the first sign-in is told it expired, the next isn’t', async () => {
    const g = await admin.post('/api/admin/gifts', { action: 'give', email: 'gift3@check.test' });
    const r = await admin.post('/api/admin/gifts', { action: 'revoke', id: g.json.id });
    expect(r.status === 200, `revoke: ${r.text}`);
    const again = await admin.post('/api/admin/gifts', { action: 'revoke', id: g.json.id });
    expect(again.status === 400, 'revoked twice');
    const { c, verify } = await signIn('gift3@check.test');
    expect(verify.gift_revoked === true, `first sign-in: ${JSON.stringify(verify)}`);
    expect((await signIn('gift3@check.test')).verify.gift_revoked === undefined, 'told twice');
    return (await c.get('/api/me')).json.active === false ? true : 'a revoked gift started';
  });

  /* ---- the free trial: started by the app adding the first ARN, once per email ---- */
  const istToday = () => new Date(Date.now() + 5.5 * 3_600_000).toISOString().slice(0, 10);
  const dayPlus = (d: string, n: number) => new Date(Date.parse(d) + n * 86_400_000).toISOString().slice(0, 10);
  const yearOn = (d: string) => `${+d.slice(0, 4) + 1}${d.slice(4)}`;
  await check('trial: no plan yet → the download is open; the app adding the first ARN starts 15 days; Buy now from then on', async () => {
    const { c } = await signIn('trial@check.test');
    const id = (await accountId('trial@check.test'))!;
    const me0 = await c.get('/api/me');
    expect(me0.json.had_plan === false && !c.cookies.has('hp'), `before: ${me0.text}`);
    const dl = await c.get('/api/download');
    expect(dl.status === 503 && dl.json.error === 'installer_missing', `download with no plan: ${dl.status} ${dl.text}`);
    const b = await appBind(id, 'ARN-222222', 'T Rial');
    expect(b.status === 200 && b.json.trial_until === dayPlus(istToday(), 15) && b.json.used === 1, `bind: ${b.text}`);
    const lic = await licence(id);
    expect(lic.json.active && lic.json.source === 'trial' && lic.json.arns[0]?.arn === '222222', `licence: ${lic.text}`);
    const me = await c.get('/api/me');
    expect(me.json.had_plan === true && c.cookies.get('hp') === '1', `the hp cookie isn’t set: ${me.text}`);
    const acct = await c.get('/account');
    expect(acct.text.includes('Free trial') && acct.text.includes('>Buy now</a>'), 'Account doesn’t show the trial, with Buy now');
    const page = await admin.get(`/accounts/${await uidOf(id)}`);
    return page.text.includes('Free trial started') ? true : 'not in the activity';
  });
  await check('trial: once per account; an ARN whose account was deleted starts one again under another email, both on record', async () => {
    await signIn('trial3@check.test');
    const id3 = (await accountId('trial3@check.test'))!;
    expect((await appBind(id3, 'ARN-444444', 'A')).json.trial_until, 'no trial');
    await signIn('trial2@check.test');
    const id2 = (await accountId('trial2@check.test'))!;
    const taken = await appBind(id2, 'ARN-444444', 'A');
    expect(taken.status === 409 && taken.json.error === 'arn_taken', `while another account has it: ${taken.text}`);
    await admin.post('/api/admin/accounts', { action: 'delete', accounts: [id3] });
    const again = await appBind(id2, 'ARN-444444', 'A');
    expect(again.status === 200 && again.json.trial_until, `after deleting that account: ${again.text}`);
    expect(/"n":\s*2/.test(sql(`SELECT COUNT(*) AS n FROM trials WHERE arn = '444444'`)), 'the record doesn’t hold both trials');
    const second = await appBind(id2, 'ARN-555555', 'B');
    return second.status === 409 && second.json.error === 'no_free_slot' ? true : `a second ARN on a trial: ${second.text}`;
  });
  await check('trial: once per email; the account deleted above, made again with its email, gets none and is shown Buy now', async () => {
    const { c } = await signIn('trial3@check.test');
    const id = (await accountId('trial3@check.test'))!;
    const b = await appBind(id, 'ARN-888888', 'A');
    expect(b.status === 403 && b.json.error === 'no_active_plan' && b.json.trial_used === true, `bind: ${b.text}`);
    expect((await licence(id)).json.trial_used === true, 'the licence doesn’t say trial_used');
    const me = await c.get('/api/me');
    expect(me.json.had_plan === true && c.cookies.get('hp') === '1', `had_plan: ${me.text}`);
    const acct = await c.get('/account');
    return acct.text.includes('This email has had its free trial') && acct.text.includes('>Buy now</a>') ? true : 'Account doesn’t say so, with Buy now';
  });
  await check('trial: “ends on” then “has ended”, once each (hourly job); after it, the app and the download are refused', async () => {
    const id = (await accountId('trial2@check.test'))!;
    sql(`UPDATE plans SET ends_on = '${dayPlus(istToday(), 1)}' WHERE account_id = ${id}`);
    let mark = LOG.length;
    await cron(HOURLY);
    expect(await mailTo('trial2@check.test', mark, /trial ends on/), 'no “ends on” email');
    mark = LOG.length;
    await cron(HOURLY);
    expect(!emailsSince(mark).some(e => e.to === 'trial2@check.test'), 'emailed twice');
    sql(`UPDATE plans SET ends_on = '${dayPlus(istToday(), -3)}' WHERE account_id = ${id}`);
    mark = LOG.length;
    await cron(HOURLY);
    expect(await mailTo('trial2@check.test', mark, /free trial has ended/), 'no “has ended” email');
    const { c } = await signIn('trial2@check.test');
    expect((await c.get('/api/download')).status === 403, 'downloads after the trial');
    const b = await appBind(id, 'ARN-555555', 'B');
    return b.status === 403 && b.json.error === 'no_active_plan' ? true : `the app after the trial: ${b.text}`;
  });
  await check('an ARN on an account whose plan has ended: another account takes it, if it has a slot; on a running plan it is refused', async () => {
    const from = (await accountId('trial2@check.test'))!;         /* its trial has ended, and it holds ARN-444444 */
    const arnsOf = async (id: number) => (await licence(id)).json.arns.map((a: { arn: string }) => a.arn).join();
    expect(await arnsOf(from) === '444444', `before: ${await arnsOf(from)}`);
    /* a running plan with its one slot full: refused, and the ARN stays where it was */
    await signIn('full@check.test');
    const full = (await accountId('full@check.test'))!;
    expect((await appBind(full, 'ARN-777777', 'F')).json.trial_until, 'no trial');
    const none = await appBind(full, 'ARN-444444', 'A');
    expect(none.status === 409 && none.json.error === 'no_free_slot' && await arnsOf(from) === '444444', `no slot: ${none.text}`);
    /* an account that has never had a plan: its trial starts with it */
    await signIn('taker@check.test');
    const to = (await accountId('taker@check.test'))!;
    const b = await appBind(to, 'ARN-444444', 'A');
    expect(b.status === 200 && b.json.trial_until && b.json.used === 1, `the trial path: ${b.text}`);
    expect(await arnsOf(from) === '' && await arnsOf(to) === '444444', `after: ${await arnsOf(from)} / ${await arnsOf(to)}`);
    expect((await admin.get(`/accounts/${await uidOf(from)}`)).text.includes('ARN freed'), 'not in the old account’s activity');
    /* now it is on a running plan: nobody takes it */
    const back = await appBind(full, 'ARN-444444', 'A');
    expect(back.status === 409 && back.json.error === 'arn_taken', `on a running plan: ${back.text}`);
    /* an account on a plan with a free slot takes it once that plan has ended too */
    const g = await admin.post('/api/admin/gifts', { action: 'give', email: 'taker2@check.test' });
    expect(g.status === 200, `give: ${g.text}`);
    await signIn('taker2@check.test');
    const to2 = (await accountId('taker2@check.test'))!;
    sql(`UPDATE plans SET ends_on = '${dayPlus(istToday(), -1)}' WHERE account_id = ${to}`);
    const b2 = await appBind(to2, 'ARN-444444', 'A');
    expect(b2.status === 200 && !b2.json.trial_until && b2.json.already === false && b2.json.used === 1, `the plan path: ${b2.text}`);
    return await arnsOf(to) === '' && await arnsOf(to2) === '444444' ? true : `${await arnsOf(to)} / ${await arnsOf(to2)}`;
  });
  await check('trial: bought during it → the year starts when the trial ends; the ARN stays; no trial emails after', async () => {
    const { c } = await signIn('trial@check.test');
    const id = (await accountId('trial@check.test'))!;
    expect((await c.get('/checkout')).text.includes('Your year starts when your free trial ends'), 'Checkout doesn’t say when the year starts');
    const o = await c.post('/api/checkout/order', { kind: 'new', arns: 1, name: 'T Rial', address: 'Pune' });
    expect(o.status === 200, `order: ${o.text}`);
    const fd = new FormData(); fd.append('order_id', o.json.order_id); fd.append('screenshot', png());
    expect((await c.post('/api/checkout/proof', fd)).status === 200, 'screenshot refused');
    const a = await admin.post('/api/admin/payments', { action: 'approve', ref: o.json.order_id });
    expect(a.status === 200 && a.json.invoice, `approve: ${a.text}`);
    const lic = await licence(id);
    expect(lic.json.source === 'paid' && lic.json.paid_until === yearOn(dayPlus(istToday(), 15)) && lic.json.arns[0]?.arn === '222222', `licence: ${lic.text}`);
    sql(`UPDATE plans SET ends_on = '${dayPlus(istToday(), 1)}' WHERE account_id = ${id}`);
    const mark = LOG.length;
    await cron(HOURLY);
    sql(`UPDATE plans SET ends_on = '${lic.json.paid_until}' WHERE account_id = ${id}`);
    return !emailsSince(mark).some(e => e.to === 'trial@check.test') ? true : 'a bought plan got a trial email';
  });
  await check('trial: a gift takes over a running trial, its year from the trial’s end', async () => {
    await signIn('trial4@check.test');
    const id = (await accountId('trial4@check.test'))!;
    expect((await appBind(id, 'ARN-666666', 'C')).json.trial_until, 'no trial');
    const g = await admin.post('/api/admin/gifts', { action: 'give', email: 'trial4@check.test' });
    expect(g.status === 200 && g.json.started === true, `give: ${g.text}`);
    const lic = await licence(id);
    return lic.json.source === 'grant' && lic.json.paid_until === yearOn(dayPlus(istToday(), 15)) && lic.json.arns.length === 1 ? true : lic.text;
  });
  await check('a payment left unfinished for a day: one email, once', async () => {
    const { c } = await signIn('unfinished@check.test');
    const o = await c.post('/api/checkout/order', { kind: 'new', arns: 1, name: 'U N', address: 'Nashik' });
    expect(o.status === 200, `order: ${o.text}`);
    sql(`UPDATE orders SET created_at = '2020-01-01T00:00:00.000Z' WHERE id = '${o.json.order_id}'`);
    let mark = LOG.length;
    await cron(HOURLY);
    const m = await mailTo('unfinished@check.test', mark, /one step away/);
    expect(m && m.text.includes('/checkout'), 'no email, or without the way back to Checkout');
    mark = LOG.length;
    await cron(HOURLY);
    return !emailsSince(mark).some(e => e.to === 'unfinished@check.test') ? true : 'emailed twice';
  });

  /* ---- deleting waits a day ---- */
  await check('delete → signed out → sign in within the day → keep', async () => {
    const { c } = await signIn('del1@check.test');
    const mark = LOG.length;
    const d = await c.post('/api/account/delete', { confirm: 'DELETE MY ACCOUNT' });
    expect(d.status === 200, `delete: ${d.text}`);
    expect(await mailTo('del1@check.test', mark, /will be deleted/), 'no deletion email');
    expect((await c.get('/api/me')).json.signed_in === false, 'still signed in');
    const { c: c2, verify } = await signIn('del1@check.test');
    expect(verify.delete_after && verify.delete_on, `verify didn't ask: ${JSON.stringify(verify)}`);
    /* (not /api/me: finding no session, it clears the cookies, as it should) */
    expect((await c2.get('/api/download')).status === 401, 'a pending account opened a session before Keep');
    const k = await c2.post('/api/account/keep');
    expect(k.status === 200, `keep: ${k.text}`);
    const me = await c2.get('/api/me');
    return me.json.signed_in === true && !sql(`SELECT delete_after FROM accounts WHERE email = 'del1@check.test'`).includes('"delete_after": "') ? true : me.text;
  });
  await check('the app’s sign-in refuses during the day: 409 pending_deletion, and its token is dead', async () => {
    const { c } = await signIn('del2@check.test');
    const app = new Client('site', freshIp());
    const appCode = async () => {
      sql(`UPDATE codes SET created_at = '2020-01-01T00:00:00.000Z' WHERE email = 'del2@check.test'`);
      const mark = LOG.length;
      await app.req('POST', '/api/app/code', { email: 'del2@check.test' });
      return (await mailTo('del2@check.test', mark, /is your/))!.subject.slice(0, 6);
    };
    const token = (await app.req('POST', '/api/app/verify', { email: 'del2@check.test', code: await appCode(), replace: true })).json.token;
    const me = () => new Client('site', freshIp()).get('/api/app/me', { authorization: `Bearer ${token}` });
    expect((await me()).status === 200, 'the app’s token doesn’t work before');
    await c.post('/api/account/delete', { confirm: 'DELETE MY ACCOUNT' });
    const v = await app.req('POST', '/api/app/verify', { email: 'del2@check.test', code: await appCode() });
    expect(v.status === 409 && v.json.error === 'pending_deletion' && v.json.delete_after, `app sign-in: ${v.text}`);
    const dead = await me();
    return dead.status === 401 && dead.json.error === 'bad_token' ? true : `the token still works: ${dead.text}`;
  });
  await check('delete → the daily job → gone, and the deletions row written', async () => {
    const id = await accountId('del2@check.test');
    sql(`UPDATE accounts SET delete_after = '2020-01-01T00:00:00.000Z' WHERE id = ${id}`);
    await cron(DAILY);
    expect(await accountId('del2@check.test') === null, 'the account is still there');
    expect(/"n":\s*1/.test(sql(`SELECT COUNT(*) AS n FROM deletions WHERE account_id = ${id}`)), 'no deletions row');
    const { verify } = await signIn('del2@check.test');
    return verify.was_deleted === 'self' ? true : `signing in again: ${JSON.stringify(verify)}`;
  });
  await check('admin deletes accounts at once, no email; signing in again says so, once', async () => {
    await signIn('gone1@check.test'); await signIn('gone2@check.test');
    const ids = [await accountId('gone1@check.test'), await accountId('gone2@check.test')];
    const mark = LOG.length;
    const r = await admin.post('/api/admin/accounts', { action: 'delete', accounts: ids });
    expect(r.status === 200 && r.json.deleted === 2, `delete: ${r.text}`);
    expect(await accountId('gone1@check.test') === null && await accountId('gone2@check.test') === null, 'still there');
    expect(!emailsSince(mark).some(e => e.to === 'gone1@check.test'), 'they were emailed');
    const first = (await signIn('gone1@check.test')).verify;
    expect(first.was_deleted === 'admin', `first sign-in: ${JSON.stringify(first)}`);
    const next = (await signIn('gone1@check.test')).verify;
    return next.was_deleted === undefined ? true : 'told twice';
  });

  /* ---- support ---- */
  let reqId = 0;
  await check('support: signed out → 401; signed in → sent to support@, reply-to them, a 6-digit number', async () => {
    const out = await new Client('site', freshIp()).post('/api/support', new FormData());
    expect(out.status === 401, `signed out: ${out.status}`);
    const { c } = await signIn('help@check.test');
    const fd = new FormData(); fd.append('topic', 'setup'); fd.append('arn', 'ARN-123456'); fd.append('message', 'It stopped at the mailbox step.'); fd.append('screenshot', png('a.png')); fd.append('screenshot', png('b.png'));
    const mark = LOG.length;
    const r = await c.post('/api/support', fd);
    expect(r.status === 200 && r.json.id >= 100000 && r.json.id <= 999999, `send: ${r.text}`);
    reqId = r.json.id;
    const m = await mailTo(SUPPORT, mark, /Setting up/);
    expect(m && m.replyTo === 'help@check.test' && m.subject === `#${r.json.id} · Setting up · help@check.test`, `support email: ${JSON.stringify(m)}`);
    expect(m!.text.includes('[attached: '), 'screenshots not attached');
    await settle();
    expect(await mailTo('help@check.test', mark, /received your request/), 'they didn’t get “we’ve received your request”');
    return !emailsSince(mark).some(e => e.to === OWNER) ? true : 'the owner got a copy of a topic that isn’t his';
  });
  await check('support: the owner’s Gmail gets Change email and A payment I made (ARN changes: see below)', async () => {
    const { c } = await signIn('help@check.test');
    const got: string[] = [];
    for (const [topic, extra] of [['newemail', { new_email: 'new-address@check.test' }], ['payment', {}], ['install', {}]] as const) {
      const fd = new FormData(); fd.append('topic', topic); fd.append('message', 'Please help with this.');
      for (const [k, v] of Object.entries(extra)) fd.append(k, v);
      const mark = LOG.length;
      const r = await c.post('/api/support', fd);
      expect(r.status === 200, `${topic}: ${r.text}`);
      await mailTo(SUPPORT, mark);
      if (emailsSince(mark).some(e => e.to === OWNER)) got.push(topic);
    }
    return got.join(',') === 'newemail,payment' ? true : `owner copies: ${got.join(',')}`;
  });
  await check('support: “a copy of my data” emails nobody, then the hourly job sends it and solves it', async () => {
    const { c } = await signIn('buyer@check.test', buyer);
    const fd = new FormData(); fd.append('topic', 'data');
    const mark = LOG.length;
    const r = await c.post('/api/support', fd);
    expect(r.status === 200, `send: ${r.text}`);
    await settle();
    expect(emailsSince(mark).length === 0, 'an email went out at once');
    sql(`UPDATE requests SET due_at = '2020-01-01T00:00:00.000Z' WHERE id = ${r.json.id}`);
    const mark2 = LOG.length;
    await cron(HOURLY);
    const m = await mailTo('buyer@check.test', mark2, /A copy of your data/);
    expect(m && m.text.includes('-data.json') && m.text.includes('MFDI/'), 'no data email with the JSON and the receipt');
    return /"status":\s*"solved"/.test(sql(`SELECT status FROM requests WHERE id = ${r.json.id}`)) ? true : 'not solved';
  });
  await check('one PC per account: a second PC gets 409 other_pc, the same code works with replace, the first token is signed_in_elsewhere', async () => {
    const email = 'onepc@check.test';
    await signIn(email);
    const app = new Client('site', freshIp());
    const newCode = async () => {
      sql(`UPDATE codes SET created_at = '2020-01-01T00:00:00.000Z' WHERE email = '${email}'`);
      const mark = LOG.length;
      await app.req('POST', '/api/app/code', { email });
      return (await mailTo(email, mark, /is your/))!.subject.slice(0, 6);
    };
    const verify = (code: string, device: string, replace?: boolean) => new Client('site', freshIp()).req('POST', '/api/app/verify', { email, code, device, replace });
    const first = await verify(await newCode(), 'PC-ONE');
    expect(first.status === 200 && first.json.token, `first PC: ${first.text}`);
    const me = (t: string) => new Client('site', freshIp()).get('/api/app/me', { authorization: `Bearer ${t}` });
    const code = await newCode();
    const wrong = await verify(code === '000000' ? '111111' : '000000', 'PC-TWO');
    expect(wrong.status === 400 && wrong.json.error === 'wrong', `a wrong code: ${wrong.text}`);
    const ask = await verify(code, 'PC-TWO');
    expect(ask.status === 409 && ask.json.error === 'other_pc' && ask.json.device === 'PC-ONE' && ask.json.last_seen, `second PC: ${ask.text}`);
    expect((await me(first.json.token)).status === 200, 'the first PC was signed out by the question alone');
    const again = await verify(code, 'PC-TWO', true);
    expect(again.status === 200 && again.json.token, `replace with the same code: ${again.text}`);
    expect((await verify(code, 'PC-TWO', true)).status === 400, 'the code was used twice');
    const dead = await me(first.json.token);
    expect(dead.status === 401 && dead.json.error === 'signed_in_elsewhere' && dead.json.device === 'PC-TWO', `first token: ${dead.text}`);
    const out = await new Client('site', freshIp()).req('POST', '/api/app/signout', {}, { authorization: `Bearer ${first.json.token}` });
    expect(out.status === 200, `signout with an ended token: ${out.status}`);
    return (await me(again.json.token)).status === 200 ? true : 'the new PC’s token does not work';
  });
  await check('survey: written in the panel, sent live, asked by /api/app/me, answered once, closed with the X, results in the panel', async () => {
    await signIn('survey1@check.test'); await signIn('survey2@check.test');
    const a = await accountId('survey1@check.test'), b = await accountId('survey2@check.test');
    const bad = await admin.post('/api/admin/surveys', { action: 'save', title: 'x', questions: [{ q: 'Pick', type: 'one', options: ['only'] }] });
    expect(bad.status === 400 && bad.json.error === 'few_options', `one option saved: ${bad.text}`);
    const s = await admin.post('/api/admin/surveys', { action: 'save', title: 'First month', questions: [
      { q: 'How was it?', type: 'one', options: ['Good', 'Bad'], other: true }, { q: 'What should change?', type: 'text', options: [] }] });
    expect(s.status === 200 && s.json.id, `save: ${s.text}`);
    const id = s.json.id;
    expect((await licence(a)).json.survey === null, 'a draft is asked');
    expect((await admin.post('/api/admin/surveys', { action: 'live', id })).status === 200, 'not sent live');
    const asked = (await licence(a)).json.survey;
    expect(asked?.id === id && asked.questions.length === 2, `not asked: ${JSON.stringify(asked)}`);
    const r = await asApp(a, 'POST', '/api/app/survey', { id, answers: { q1: { picked: ['Good', 'Nope'], text: 'great' }, q2: { picked: [], text: 'More months at once' } } });
    expect(r.status === 200, `answer: ${r.text}`);
    expect((await asApp(a, 'POST', '/api/app/survey', { id, answers: { q1: { picked: ['Bad'] } } })).status === 409, 'answered twice');
    expect((await licence(a)).json.survey === null, 'asked again after answering');
    expect((await asApp(b, 'POST', '/api/app/survey', { id, closed: true })).status === 200, 'the X refused');
    expect((await licence(b)).json.survey === null, 'asked again after the X');
    expect((await admin.post('/api/admin/surveys', { action: 'save', id, title: 'Changed', questions: [{ q: 'x', type: 'text' }] })).status === 409, 'a live survey changed');
    const page = await admin.get(`/survey/${id}`);
    expect(page.status === 200 && page.text.includes('More months at once') && page.text.includes('survey1@check.test') && page.text.includes('1 closed it'), `results page: ${page.status}`);
    expect((await admin.get('/survey?view=software')).text.includes('First month'), 'no card');
    expect((await admin.get('/survey/new')).status === 200, 'the builder');
    expect((await admin.post('/api/admin/surveys', { action: 'close', id })).status === 200, 'not closed');
    return (await asApp(b, 'POST', '/api/app/survey', { id, closed: true })).status === 409 ? true : 'a closed survey took a reply';
  });
  await check('support: Reply in the panel goes from support@ to them, a copy to support@ that answers them, and is logged', async () => {
    const mark = LOG.length;
    const fd = new FormData(); fd.append('id', String(reqId)); fd.append('subject', `Your support request #${reqId}: Setting up`);
    fd.append('message', 'Hello,\n\nTry the mailbox step again.\n\nBest regards,\nMFDInvoice Support'); fd.append('photo', png());
    const r = await admin.post('/api/admin/support/reply', fd);
    expect(r.status === 200 && r.json.ok, `reply: ${r.text}`);
    const to = await mailTo('help@check.test', mark, /Try the mailbox step again/);
    expect(to && to.from === 'support@mfdinvoice.co.in' && to.replyTo === 'support@mfdinvoice.co.in' && /attached: \S+-1\.png/.test(to.text), `to them: ${JSON.stringify(to)}`);
    const copy = await mailTo('support@mfdinvoice.co.in', mark, /Try the mailbox step again/);
    expect(copy && copy.replyTo === 'help@check.test', `the copy: ${JSON.stringify(copy)}`);
    const page = await admin.get('/support');
    return page.text.includes('Replied ') ? true : 'the table doesn’t say it was answered';
  });
  await check('support: marked solved in the panel, and logged', async () => {
    const r = await admin.post('/api/admin/support', { id: reqId, status: 'solved' });
    expect(r.status === 200, r.text);
    const page = await admin.get(`/accounts/${await uidOf(await accountId('help@check.test'))}`);
    return page.text.includes('Support request solved') ? true : 'no activity row';
  });
  await check('support: the customer sees their requests and each status; solved can be opened again; search finds it', async () => {
    const { c } = await signIn('help@check.test');
    const mine = await c.get('/api/support');
    const one = (r: any) => r.json.requests?.find((x: any) => x.id === reqId);
    expect(one(mine)?.status === 'solved', `theirs: ${mine.text}`);
    expect((await admin.post('/api/admin/support', { id: reqId, status: 'open' })).status === 200, 'couldn’t reopen');
    expect(one(await c.get('/api/support'))?.status === 'open', 'not open again');
    expect((await new Client('site', freshIp()).get('/api/support')).status === 401, 'signed out could read');
    const found = await admin.get('/support?q=mailbox step');
    return found.text.includes(`#${reqId}`) && found.text.includes('It stopped at the mailbox step.') ? true : 'search or View data missing';
  });

  /* ---- email change ---- */
  await check('email change: both addresses told, sessions end, the new email signs in to the same account', async () => {
    const { c } = await signIn('old@check.test');
    const id = await accountId('old@check.test');
    const taken = await admin.post('/api/admin/accounts', { account: id, action: 'change_email', email: 'buyer@check.test' });
    expect(taken.status === 400 && taken.json.error === 'email_taken', `taken: ${taken.text}`);
    const mark = LOG.length;
    const r = await admin.post('/api/admin/accounts', { account: id, action: 'change_email', email: 'renamed@check.test' });
    expect(r.status === 200, r.text);
    expect(await mailTo('old@check.test', mark, /changed/) && await mailTo('renamed@check.test', mark, /now your/), 'both addresses weren’t emailed');
    expect((await c.get('/api/me')).json.signed_in === false, 'the old session still works');
    await signIn('renamed@check.test');
    return (await accountId('renamed@check.test')) === id ? true : 'a different account';
  });

  /* ---- changing an ARN: asked in Support, freed in the panel, the new one comes in through the app ---- */
  await check('ARN change: only their own ARN can be asked about; the owner is copied; Free logs it and Support shows the history', async () => {
    const b1 = await appBind(buyerId, 'ARN-111111', 'Neil Lunavat');
    expect(b1.status === 200, `bind: ${b1.text}`);
    const { c } = await signIn('buyer@check.test', buyer);
    const mineList = await c.get('/api/support');
    expect(mineList.json.arns?.join() === '111111', `their ARNs: ${mineList.text}`);
    const ask = (arn: string) => { const fd = new FormData(); fd.append('topic', 'arn'); fd.append('arn', arn); fd.append('message', 'We moved to our firm’s ARN.'); return c.post('/api/support', fd); };
    const notMine = await ask('ARN-999999');
    expect(notMine.status === 400 && notMine.json.error === 'not_your_arn', `someone else’s ARN: ${notMine.text}`);
    const mark = LOG.length;
    const ok = await ask('ARN-111111');
    expect(ok.status === 200, `ask: ${ok.text}`);
    await mailTo(SUPPORT, mark);
    expect(emailsSince(mark).some(e => e.to === OWNER), 'the owner wasn’t copied');
    expect((await admin.post('/api/admin/accounts', { account: buyerId, action: 'correct_arn', from: '111111', to: 'ARN-333333' })).json.error === 'bad_action', 'Correct still works');
    const fm = LOG.length;
    const free = await admin.post('/api/admin/accounts', { account: buyerId, action: 'free_arn', arn: '111111', tell: true });
    expect(free.status === 200, free.text);
    expect(await mailTo('buyer@check.test', fm, /slot is free/), 'not told the slot is free');
    expect((await licence(buyerId)).json.arns.length === 0, 'not freed');
    const page = await admin.get(`/accounts/${await uidOf(buyerId)}`);
    expect(page.text.includes('ARN freed'), 'not in the activity');
    return (await admin.get('/support?q=firm')).text.includes('ARNs freed before: 1') ? true : 'Support doesn’t show the history';
  });
  await check('receipt: a billing change is logged; Resend carries the new details to the email of now', async () => {
    const { c } = await signIn('buyer@check.test', buyer);
    expect((await c.post('/api/account/billing', { name: 'Lunavat Wealth LLP', address: '2 New Road, Pune' })).status === 200, 'billing not saved');
    const page = await admin.get(`/accounts/${await uidOf(buyerId)}`);
    expect(page.text.includes('Billing details changed') && page.text.includes('Lunavat Wealth LLP'), 'change not in the activity');
    const num = (page.text.match(/MFDI\/\d{2}-\d{2}\/0001/) ?? [])[0];
    const mark = LOG.length;
    const r = await admin.post('/api/admin/accounts', { account: buyerId, action: 'resend', number: num });
    expect(r.status === 200, `resend: ${r.text}`);
    const m = await mailTo('buyer@check.test', mark);
    expect(m && m.text.includes('Lunavat Wealth LLP'), 'the resent receipt has the old name');
    expect(!m!.text.includes('/downloads'), 'Resend carried the download button');
    const rc = await admin.get(`/receipts/${num}`);
    return rc.text.includes('Lunavat Wealth LLP') && rc.text.includes('2 New Road') ? true : 'the receipt page still has the old details';
  });

  /* ---- part-year price ---- */
  await check('part-year price: 15 Mar 2027 → 30 Sep 2027 is 7 months, ₹1,167 per ARN, ₹3,501 for 3', async () => {
    const m = monthsLeft('2027-03-15', '2027-09-30');
    const q = quote('add', 3, m);
    return m === 7 && extraFor(m) === 1167 && q.subtotal === 350100 && monthsLeft('2026-10-01', '2027-09-30') === 12 ? true : `${m} ${extraFor(m)} ${q.subtotal}`;
  });

  /* ---- the blog ---- */
  let postId = 0;
  const draft = { title: 'Check post', seo_title: 'Check post: a search title', slug: 'check-post', description: 'A post made by the check.',
    body: '## First\n\nHello.\n\n![A caption under the picture](/blog/images/x.png)\n' };
  await check('blog: preview is the real page, with Publish; nothing saved until then; missing fields keep Publish off', async () => {
    const fd = new FormData(); fd.append('data', JSON.stringify(draft));
    const pv = await writer.post('/posts/preview', fd);
    expect(pv.status === 200 && pv.text.includes('<title>Check post: a search title</title>') && pv.text.includes('Publish') && pv.text.includes('class="nav'), `preview: ${pv.status}`);
    expect(pv.text.includes('<figcaption>A caption under the picture</figcaption>'), 'no caption under the image');
    expect((await new Client().get('/blog/check-post')).status === 404, 'the preview saved it');
    const half = new FormData(); half.append('data', JSON.stringify({ ...draft, seo_title: '' }));
    const pv2 = await writer.post('/posts/preview', half);
    return pv2.text.includes('Add the search title before publishing') && /id="publish" disabled/.test(pv2.text) ? true : 'Publish not held back';
  });
  await check('blog: Publish puts it at /blog/<slug> with its search title, and in the sitemap; the fields are required', async () => {
    const no = await writer.post('/api/write/posts', { action: 'save', ...draft, slug: '' });
    expect(no.status === 400 && no.json.error === 'no_slug', `no address: ${no.text}`);
    const s = await writer.post('/api/write/posts', { action: 'save', ...draft });
    expect(s.status === 200 && s.json.id && s.json.path === '/blog/check-post', `publish: ${s.text}`);
    postId = s.json.id;
    const [pub, list, sm] = await Promise.all([new Client().get('/blog/check-post'), new Client().get('/blog'), new Client().get('/sitemap.xml')]);
    return pub.status === 200 && pub.text.includes('<title>Check post: a search title</title>') && pub.text.includes('<h1>Check post</h1>') && list.text.includes('Check post') && sm.text.includes('/blog/check-post')
      ? true : `${pub.status}`;
  });
  await check('blog: a changed address keeps every old one working (301); no other post can take them', async () => {
    const a = await writer.post('/api/write/posts', { action: 'save', id: postId, ...draft, slug: 'check-post-2' });
    const b = await writer.post('/api/write/posts', { action: 'save', id: postId, ...draft, slug: 'check-post-3' });
    expect(a.status === 200 && b.status === 200 && b.json.path === '/blog/check-post-3', `${a.text} ${b.text}`);
    const [old1, old2, now] = await Promise.all(['/blog/check-post', '/blog/check-post-2', '/blog/check-post-3'].map(x => new Client().get(x)));
    expect(old1.status === 301 && old1.headers.get('location')?.endsWith('/blog/check-post-3') && old2.status === 301 && now.status === 200, `old ${old1.status} ${old2.status}, now ${now.status}`);
    const dup = await writer.post('/api/write/posts', { action: 'save', ...draft, title: 'Another', slug: 'check-post' });
    expect(dup.status === 400 && dup.json.error === 'slug_taken', `took an old address: ${dup.text}`);
    const back = await writer.post('/api/write/posts', { action: 'save', id: postId, ...draft, slug: 'check-post' });
    return back.status === 200 && (await new Client().get('/blog/check-post')).status === 200 ? true : `going back to an old address: ${back.text}`;
  });
  await check('images: uploaded ones are listed with the posts that use them; Delete takes one out, logged', async () => {
    const fd = new FormData(); fd.append('image', png('lib.png'));
    const up = await writer.post('/api/write/image', fd);
    expect(up.status === 200 && up.json.key, `upload: ${up.text}`);
    await writer.post('/api/write/posts', { action: 'save', id: postId, ...draft, body: draft.body + `
![](${up.json.url})
` });
    const lib = await writer.get('/images');
    expect(lib.text.includes(up.json.key.replace('blog/', '')) && lib.text.includes('In '), 'not listed, or not shown as used');
    const del = await writer.post('/api/write/image', { action: 'delete', key: up.json.key });
    expect(del.status === 200, `delete: ${del.text}`);
    expect(!(await writer.get('/images')).text.includes(up.json.key.replace('blog/', '')), 'still listed');
    return /image\.deleted/.test(sql(`SELECT action FROM events WHERE ref = '${up.json.key}'`)) ? true : 'not logged';
  });
  await check('blog: delete takes it off with every address, and it’s logged', async () => {
    const d = await writer.post('/api/write/posts', { action: 'delete', id: postId });
    expect(d.status === 200, d.text);
    const gone = await Promise.all(['/blog/check-post', '/blog/check-post-2', '/blog/check-post-3'].map(x => new Client().get(x)));
    expect(gone.every(g => g.status === 404), `still there: ${gone.map(g => g.status)}`);
    return /post\.deleted/.test(sql(`SELECT action FROM events WHERE ref = 'post ${postId}'`)) ? true : 'not logged';
  });

  /* ---- the activity log, deleting, signing out everywhere ---- */
  await check('activity: created, signed in, payment sent, ARN added by the software, support sent and reopened', async () => {
    const page = (await admin.get(`/accounts/${await uidOf(buyerId)}`)).text;
    const want = ['Account created', 'Signed in on the website', 'Payment sent for checking', 'ARN added by the software', 'Support request sent'];
    const missing = want.filter(w => !page.includes(w));
    expect(!missing.length, `missing: ${missing.join(', ')}`);
    const help = (await admin.get(`/accounts/${await uidOf(await accountId('help@check.test'))}`)).text;
    return help.includes('Support request reopened') ? true : 'reopening not logged';
  });
  await check('a payment being checked blocks deleting; the app’s sign-in is logged with its version; Sign out everywhere ends the app too', async () => {
    const { c } = await signIn('waiting@check.test');
    const o = await c.post('/api/checkout/order', { kind: 'new', arns: 1, name: 'W X', address: 'There' });
    const fd = new FormData(); fd.append('order_id', o.json.order_id); fd.append('screenshot', png());
    await c.post('/api/checkout/proof', fd);
    const del = await c.post('/api/account/delete', { confirm: 'DELETE MY ACCOUNT' });
    expect(del.status === 409 && del.json.error === 'payment_in_review', `deleted while checking: ${del.text}`);
    expect((await c.get('/account')).text.includes('once we’ve checked your payment'), 'the Account page doesn’t say why');
    sql(`UPDATE codes SET created_at = '2020-01-01T00:00:00.000Z' WHERE email = 'waiting@check.test'`);
    const app = new Client('site', freshIp()), mark = LOG.length;
    await app.post('/api/app/code', { email: 'waiting@check.test' });
    const code = (await mailTo('waiting@check.test', mark, /is your/))!.subject.slice(0, 6);
    const tok = (await app.post('/api/app/verify', { email: 'waiting@check.test', code, version: '1.0.0', device: 'DESKTOP-4K2P' })).json.token;
    const page = (await admin.get(`/accounts/${await uidOf(await accountId('waiting@check.test'))}`)).text;
    expect(page.includes('Signed in to the software') && page.includes('v1.0.0 · DESKTOP-4K2P'), 'app sign-in not logged');
    expect((await c.post('/api/account/signout-all', {})).status === 200, 'sign out everywhere failed');
    const me = await new Client('site', freshIp()).get('/api/app/me', { authorization: `Bearer ${tok}` });
    expect(me.status === 401, `the app is still signed in: ${me.status}`);
    return (await c.get('/api/me')).json.signed_in === false ? true : 'this browser is still signed in';
  });

  /* ---- Access ---- */
  await check('panel: refused without a JWT, with a forged, expired or wrong-app JWT, and for a writer', async () => {
    const tries = {
      none: new Client('control', freshIp()),
      forged: new Client('control', freshIp(), await jwt(ADMIN, AUD.control, { key: forgedKey.privateKey })),
      expired: new Client('control', freshIp(), await jwt(ADMIN, AUD.control, { exp: Math.floor(Date.now() / 1000) - 60 })),
      wrongApp: new Client('control', freshIp(), await jwt(ADMIN, AUD.write)),
      wrongIssuer: new Client('control', freshIp(), await jwt(ADMIN, AUD.control, { iss: 'https://evil.cloudflareaccess.com' })),
      writer: new Client('control', freshIp(), await jwt(WRITER, AUD.control)),
    };
    const bad: string[] = [];
    for (const [k, c] of Object.entries(tries)) {
      for (const [m, path] of [['GET', '/'], ['POST', '/api/admin/gifts']] as const) {
        const r = await c.req(m, path, m === 'POST' ? { action: 'give', email: 'x@check.test' } : undefined);
        if (r.status !== 403) bad.push(`${k} ${m} ${path}: ${r.status}`);
      }
    }
    const ok = await admin.get('/');
    return !bad.length && ok.status === 200 && ok.text.includes('Payments to check') ? true : bad.join('; ') || `admin: ${ok.status}`;
  });
  await check('editor: refused without a JWT; a writer gets in; nothing about accounts there', async () => {
    const none = await new Client('write', freshIp()).get('/');
    const w = await writer.get('/');
    const cross = await writer.get('/api/admin/file?key=proofs/x.png');
    return none.status === 403 && w.status === 200 && cross.status === 404 ? true : `${none.status} ${w.status} ${cross.status}`;
  });
  await check('the panel’s Software tab: what the app sent, one in full with its picture; the public site gets nothing', async () => {
    expect((await admin.get('/fonts/Geist-Variable.woff2')).status === 200, 'the panel’s fonts');
    const page = await admin.get('/software?view=db');
    expect(page.status === 200 && page.text.includes('Ours to fix') && page.text.includes('17 invoices submitted for October.'), `the tab: ${page.status}`);
    expect(page.text.includes('>Ended well<') && page.text.includes('5m 12s') && page.text.includes('1m 35s'), 'the result’s colour or how long it took');
    expect(/Axis looks wrong to me.{0,300}about.{0,200}data-view="1"/s.test(page.text), 'a person’s message doesn’t say which run it is about');
    const same = await admin.get('/api/admin/software?id=3');
    expect(same.json.same?.length === 1 && same.json.same[0].id === 1, `the same run: ${same.text}`);
    const seen = await admin.post('/api/admin/software', { id: 2, state: 'seen' });
    expect(seen.status === 200 && (await admin.get('/software?view=db')).text.includes('>Seen<'), `Seen: ${seen.text}`);
    expect((await admin.post('/api/admin/software', { id: 2, state: 'gone' })).status === 400, 'a state that isn’t one');
    const acct = await admin.get(`/accounts/${await uidOf((await accountId('buyer@check.test'))!)}`);
    expect(acct.text.includes('id="runs"') && acct.text.includes('17 invoices submitted for October.'), 'the account’s page doesn’t list its runs');
    const ours = await admin.get('/software?view=db&kind=ours');
    expect(ours.text.includes('buyer@check.test') && !ours.text.includes('17 invoices submitted'), 'the filter by kind');
    const one = await admin.get('/api/admin/software?id=2');
    expect(one.status === 200 && one.json.report.log && one.json.files.length === 2, `one in full: ${one.text}`);
    const pic = await admin.get('/api/admin/software?id=2&file=01-cams-status.png');
    expect(pic.status === 200 && pic.headers.get('content-type') === 'image/png', `a picture: ${pic.status}`);
    const dash = await admin.get('/software');
    expect(dash.status === 200 && dash.text.includes('Ours, last 30 days') && dash.text.includes('A page isn’t what the app expects') && dash.text.includes('Versions in use'), `the dashboard: ${dash.status}`);
    const accts = await admin.get('/accounts?q=buyer%40check.test');
    expect(accts.text.includes('Last run') && accts.text.includes('Ours to fix') && accts.text.includes('1.0.0'), 'Accounts doesn’t show the last run or the version');
    const out = await new Client('site', freshIp()).get('/api/admin/software?id=2');
    return out.status === 403 || out.status === 404 ? true : `from the public site: ${out.status}`;
  });
  await check('the public host: the panel and the editor are 404', async () => {
    const c = new Client('site', freshIp(), await jwt(ADMIN, AUD.control));
    const rs = await Promise.all(['/control', '/control/payments', '/write', '/api/admin/payments', '/api/write/posts'].map(p => c.get(p)));
    return rs.every(r => r.status === 404) ? true : rs.map(r => r.status).join(',');
  });
  await check('security headers on a static page and a server page', async () => {
    const [s, d, h] = await Promise.all([new Client().get('/pricing'), new Client().get('/api/me'), new Client().get('/api/health')]);
    const has = (x: Headers) => ['strict-transport-security', 'x-content-type-options', 'referrer-policy', 'x-frame-options', 'permissions-policy', 'content-security-policy'].every(k => x.get(k));
    return has(s.headers) && has(d.headers) && d.json?.signed_in === false && h.status === 404 ? true : `missing (health ${h.status})`;
  });
}

try {
  await main();
} catch (e) {
  result('the check itself', false, e instanceof Error ? e.message : String(e));
} finally {
  if (process.argv.includes('--keep') && procs.length) {
    const long = { exp: Math.floor(Date.now() / 1000) + 8 * 3600 };
    const t = { control: await jwt(ADMIN, AUD.control, long), write: await jwt(ADMIN, AUD.write, long), writer: await jwt(WRITER, AUD.write, long) };
    await Bun.write(`${PERSIST}/tokens.json`, JSON.stringify(t, null, 2));
    /* a browser can't send the Access JWT: these add it, and make Origin and redirects match the host the Worker sees */
    const proxy = (port: number, to: keyof typeof PORTS, token: string) => Bun.serve({ port, hostname: '127.0.0.1', async fetch(req) {
      const u = new URL(req.url), headers = new Headers(req.headers);
      headers.set('cf-access-jwt-assertion', token);
      if (headers.has('origin')) headers.set('origin', `https://${HOSTS[to]}`);
      const r = await fetch(`http://127.0.0.1:${PORTS[to]}${u.pathname}${u.search}`, { method: req.method, headers,
        body: ['GET', 'HEAD'].includes(req.method) ? undefined : await req.arrayBuffer(), redirect: 'manual' });
      const out = new Headers(r.headers);
      const loc = out.get('location'); if (loc) out.set('location', loc.replace(`https://${HOSTS[to]}`, `http://localhost:${port}`));
      /* fetch has already unpacked the body: its old length and encoding no longer hold */
      out.delete('strict-transport-security'); out.delete('content-encoding'); out.delete('content-length');
      return new Response(r.body, { status: r.status, headers: out });
    } });
    proxy(8800, 'control', t.control); proxy(8801, 'write', t.writer);
    console.log(`
${passed} passed, ${failed} failed. Still running, with the check's data: the panel on http://localhost:8800, the blog editor on http://localhost:8801, the site on http://127.0.0.1:${PORTS.site}. Ctrl+C to stop.`);
    await new Promise(() => {});
  }
  stopAll();
  certs.stop(true);
  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
}
