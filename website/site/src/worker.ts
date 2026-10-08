/* The Worker's entry: Astro's handler, with three things around it. (Before all of them, www. is sent to the bare
   domain with a 301.)
   1. Hosts. On CONTROL_HOST only the admin panel exists (its pages, served from src/pages/control/, and
      /api/admin/*); on WRITE_HOST only the blog editor (src/pages/write/, /api/write/*, and the blog's images).
      Both sit behind Cloudflare Access, and the Worker checks the Access JWT itself before anything runs.
      On every other host the panel's and the editor's pages and APIs are a 404.
   2. Security headers on every response (lib/server/headers.ts); the same list is in public/_headers.
   3. The scheduled jobs (Cron Triggers in wrangler.jsonc, lib/server/jobs.ts). */
import handler from '@astrojs/cloudflare/entrypoints/server';
import { appOf, accessUser } from './lib/server/access';
import { withSecurityHeaders } from './lib/server/headers';
import { run } from './lib/server/jobs';
import { record, kindOf } from './lib/server/errors';
import { SITE_URL } from './consts';

const notFound = () => new Response('Not found', { status: 404, headers: { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' } });

/* On a panel host, what passes through as it is; everything else is one of that app's pages, under /control or /write. */
const PASS = {
  control: [/^\/api\/admin\//, /^\/_astro\//, /^\/fonts\//],
  write: [/^\/api\/write\//, /^\/_astro\//, /^\/fonts\//, /^\/blog\/images\//, /^\/si\.js$/],
} as const;
const PRIVATE = /^\/(control|write)(\/|$)|^\/api\/(admin|write)\//;

async function serve(req: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
  const url = new URL(req.url);
  if (url.hostname.toLowerCase() === `www.${new URL(SITE_URL).hostname}`) return Response.redirect(new URL(url.pathname + url.search, SITE_URL).href, 301);
  const app = appOf(url);
  if (!app) {
    if (PRIVATE.test(url.pathname)) return notFound();
    return handler.fetch(req, env, ctx);
  }
  if (!(await accessUser(req, app))) return new Response('Forbidden', { status: 403, headers: { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' } });
  if (!PASS[app].some(r => r.test(url.pathname))) {
    if (/^\/(control|write)(\/|$)/.test(url.pathname)) return notFound();
    url.pathname = `/${app}${url.pathname === '/' ? '' : url.pathname}`;
    req = new Request(url, req);
  }
  const res = await handler.fetch(req, env, ctx);
  /* the public site's 404 page doesn't belong here */
  return res.status === 404 ? notFound() : res;
}

export default {
  async fetch(req: Request, env: Env, ctx: ExecutionContext) {
    let res: Response;
    try {
      res = await serve(req, env, ctx);
    } catch (e) {
      ctx.waitUntil(record(kindOf(e), `${req.method} ${new URL(req.url).pathname}`, e));
      res = new Response('Something went wrong.', { status: 500, headers: { 'content-type': 'text/plain; charset=utf-8' } });
    }
    return withSecurityHeaders(req, res);
  },
  async scheduled(controller: ScheduledController, env: Env, ctx: ExecutionContext) {
    ctx.waitUntil(run(controller.cron).then(r => console.log('jobs', controller.cron, JSON.stringify(r))));
  },
} satisfies ExportedHandler<Env>;
