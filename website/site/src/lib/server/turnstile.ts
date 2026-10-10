/* Cloudflare Turnstile on the sign-in code request (stops someone mailing a stranger's inbox over and over).
   On only when both TURNSTILE_SITE (the public site key, a var) and TURNSTILE_SECRET (a secret) are set; off, nothing
   changes. The software's own sign-in (/api/app/code) is not behind it. */
import { env } from 'cloudflare:workers';
import { ip } from './http';

export const turnstileSite = (): string => (env.TURNSTILE_SITE && env.TURNSTILE_SECRET ? env.TURNSTILE_SITE : '');

/* true when the check is off or the token is good; false for a missing or bad token, or when Cloudflare can't be reached */
export async function turnstileOk(req: Request, token: unknown): Promise<boolean> {
  if (!turnstileSite()) return true;
  if (typeof token !== 'string' || !token || token.length > 2048) return false;
  try {
    const r = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
      method: 'POST',
      body: new URLSearchParams({ secret: env.TURNSTILE_SECRET, response: token, remoteip: ip(req) }),
    });
    const j = await r.json<{ success?: boolean }>();
    return j.success === true;
  } catch { return false; }
}
