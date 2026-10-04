/* For server-rendered pages (Account, Checkout, an invoice): signed in, or off to Sign in and back. */
import { webSession, clearCookies, type Session } from './auth';

export async function signedInOr(req: Request, signin: string): Promise<Session | Response> {
  const s = await webSession(req);
  if (s) return s;
  /* a stale "si" cookie would keep the nav saying Account: clear both */
  const h = new Headers({ location: signin, 'cache-control': 'no-store' });
  clearCookies().forEach(c => h.append('set-cookie', c));
  return new Response(null, { status: 302, headers: h });
}
