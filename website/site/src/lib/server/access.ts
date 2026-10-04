/* The admin panel (CONTROL_HOST) and the blog editor (WRITE_HOST) sit behind Cloudflare Access. Access is the gate,
   and the Worker checks it again itself, so a missing or forged header gets nothing: the Cf-Access-Jwt-Assertion
   JWT must be signed by one of the team's keys (ACCESS_TEAM's /cdn-cgi/access/certs), be for that application
   (ACCESS_AUD_CONTROL / ACCESS_AUD_WRITE), be unexpired, and carry an email on the list for that host (ADMINS;
   WRITERS). There is no password and no login page of our own. */
import { env } from 'cloudflare:workers';

export type App = 'control' | 'write';
export type Person = { email: string };

const list = (v: unknown) => String(v ?? '').split(',').map(s => s.trim().toLowerCase()).filter(Boolean);

/* Which of the two, if any, this request's host is. */
export function appOf(url: URL): App | null {
  const h = url.hostname.toLowerCase();
  if (h === String(env.CONTROL_HOST || '').toLowerCase()) return 'control';
  if (h === String(env.WRITE_HOST || '').toLowerCase()) return 'write';
  return null;
}

/* The team's address: 'myteam.cloudflareaccess.com' → https://…. Plain http only for a local test server. */
function team() {
  const t = String(env.ACCESS_TEAM || '').trim().replace(/\/$/, '');
  if (!t) return null;
  if (/^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(t)) return t;
  return t.startsWith('https://') ? t : /^[a-z0-9.-]+$/i.test(t) ? `https://${t}` : null;
}

const b64u = (s: string) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4)), c => c.charCodeAt(0));
const utf8 = (s: string) => JSON.parse(new TextDecoder().decode(b64u(s)));

/* The team's signing keys, kept for 10 minutes; fetched again when a token names a key we don't have. */
let keys: { at: number; team: string; byKid: Map<string, CryptoKey> } | null = null;
async function key(kid: string, origin: string) {
  const fresh = keys && keys.team === origin && Date.now() - keys.at < 600_000;
  if (!fresh || !keys!.byKid.has(kid)) {
    const r = await fetch(`${origin}/cdn-cgi/access/certs`);
    if (!r.ok) return null;
    const { keys: jwks } = await r.json<{ keys: (JsonWebKey & { kid: string })[] }>();
    const byKid = new Map<string, CryptoKey>();
    for (const k of jwks ?? []) {
      if (k.kty !== 'RSA') continue;
      byKid.set(k.kid, await crypto.subtle.importKey('jwk', { kty: k.kty, n: k.n, e: k.e, alg: 'RS256', ext: true }, { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['verify']));
    }
    keys = { at: Date.now(), team: origin, byKid };
  }
  return keys!.byKid.get(kid) ?? null;
}

/* The person behind this request, or null. */
export async function accessUser(req: Request, app: App): Promise<Person | null> {
  try {
    const origin = team();
    const aud = String((app === 'control' ? env.ACCESS_AUD_CONTROL : env.ACCESS_AUD_WRITE) || '');
    const jwt = req.headers.get('cf-access-jwt-assertion') || '';
    const parts = jwt.split('.');
    if (!origin || !aud || parts.length !== 3) return null;
    const head = utf8(parts[0]), body = utf8(parts[1]);
    if (head.alg !== 'RS256' || typeof head.kid !== 'string') return null;
    const k = await key(head.kid, origin);
    if (!k) return null;
    const ok = await crypto.subtle.verify('RSASSA-PKCS1-v1_5', k, b64u(parts[2]), new TextEncoder().encode(parts[0] + '.' + parts[1]));
    if (!ok) return null;
    const now = Date.now() / 1000;
    const auds = Array.isArray(body.aud) ? body.aud : [body.aud];
    if (!auds.includes(aud) || typeof body.exp !== 'number' || body.exp <= now || (typeof body.nbf === 'number' && body.nbf > now + 60)) return null;
    if (body.iss !== origin) return null;
    const email = String(body.email || '').toLowerCase();
    if (!email) return null;
    return list(app === 'control' ? env.ADMINS : env.WRITERS).includes(email) ? { email } : null;
  } catch {
    return null;
  }
}
