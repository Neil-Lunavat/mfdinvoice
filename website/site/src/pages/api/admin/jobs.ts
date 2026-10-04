/* POST { job: "hourly" | "daily" } → what it did · runs a scheduled job now (the Overview's buttons). */
import { json, fail, body } from '../../../lib/server/http';
import { gated } from '../../../lib/server/admin';
import { hourly, daily } from '../../../lib/server/jobs';
export const prerender = false;

export const POST = gated('control', async req => {
  const b = await body(req);
  if (b.job === 'hourly') return json({ ok: true, ...(await hourly()) });
  if (b.job === 'daily') return json({ ok: true, ...(await daily()) });
  return fail(400, 'bad_job');
});
