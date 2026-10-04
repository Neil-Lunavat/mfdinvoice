/* POST { name, address, gstin? } → { ok, bill } · saves the billing details (a GSTIN only while SALES.gst is on;
   its checksum is checked here too). */
import { route, checkOrigin, body, json, fail } from '../../../lib/server/http';
import { webSession, withCookies, setupCookie } from '../../../lib/server/auth';
import { billing, saveBilling } from '../../../lib/server/account';
export const prerender = false;

export const POST = route(async req => {
  checkOrigin(req);
  const s = await webSession(req);
  if (!s) return fail(401, 'signed_out');
  const bill = billing(await body(req));
  if ('error' in bill) return fail(400, bill.error);
  await saveBilling(s.account_id, bill);
  return withCookies(json({ ok: true, bill }), [setupCookie(false)]);
});
