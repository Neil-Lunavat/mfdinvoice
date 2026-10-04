/* GET → the installer (the one file in R2, uploaded with bun run installer). Checked on every request: a signed-in
   account (the website's cookie, or the app's Bearer token) whose plan hasn't ended. One with no plan yet may
   download: its free trial starts in the app. */
import { env } from 'cloudflare:workers';
import { route, fail } from '../../lib/server/http';
import { webSession, appSession, bearer } from '../../lib/server/auth';
import { getPlan, isActive } from '../../lib/server/account';
import { NAME, INSTALLER } from '../../consts';
import { event } from '../../lib/server/events';
export const prerender = false;

export const GET = route(async req => {
  const s = bearer(req) ? await appSession(req) : await webSession(req);
  if (!s) return fail(401, bearer(req) ? 'bad_token' : 'signed_out');
  const plan = await getPlan(s.account_id);
  if (plan && !isActive(plan)) return fail(403, 'no_active_plan');
  const obj = await env.FILES.get(INSTALLER);
  if (!obj) return fail(503, 'installer_missing');
  await event('buyer', 'app.downloaded', s.account_id, null, bearer(req) ? 'by the app (an update)' : 'from the website').run();
  return new Response(obj.body, {
    headers: {
      'content-type': 'application/vnd.microsoft.portable-executable',
      'content-disposition': `attachment; filename="${NAME}-Setup.exe"`,
      'content-length': String(obj.size),
      'cache-control': 'private, no-store',
    },
  });
});
