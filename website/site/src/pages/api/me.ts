/* GET → { signed_in, email, active, had_plan } · for the static pages (Downloads' button; "Try for Free" or "Buy now").
   had_plan: the account has ever had a plan, a free trial included; it is also set as the "hp" cookie. */
import { route, json } from '../../lib/server/http';
import { webSession, clearCookies, withCookies, planCookie } from '../../lib/server/auth';
import { getPlan, isActive } from '../../lib/server/account';
export const prerender = false;

export const GET = route(async req => {
  const s = await webSession(req);
  if (!s) return withCookies(json({ signed_in: false }), clearCookies());
  const plan = await getPlan(s.account_id);
  return withCookies(json({ signed_in: true, email: s.email, active: isActive(plan), had_plan: !!plan }), [planCookie(!!plan)]);
});
