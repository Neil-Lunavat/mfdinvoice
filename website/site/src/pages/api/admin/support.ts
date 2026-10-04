/* POST { id, status: "open" | "solved" } → { ok } · a support request's status. */
import { json, fail, body } from '../../../lib/server/http';
import { gated } from '../../../lib/server/admin';
import { setRequestStatus } from '../../../lib/server/support';
export const prerender = false;

export const POST = gated('control', async (req, _url, me) => {
  const b = await body(req);
  if (b.status !== 'open' && b.status !== 'solved') return fail(400, 'bad_status');
  const r = await setRequestStatus(Number(b.id), b.status, me.email);
  return 'error' in r ? fail(404, r.error!) : json(r);
});
