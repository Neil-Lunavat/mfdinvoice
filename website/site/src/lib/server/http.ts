/* Request and response helpers for the server routes (src/pages/api/**). */
import { record, kindOf } from './errors';

export const json = (data: unknown, status = 200, headers: HeadersInit = {}) =>
  new Response(JSON.stringify(data), { status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', ...headers } });

/* An error the caller can act on: { error: 'code', ...details } */
export const fail = (status: number, error: string, extra: Record<string, unknown> = {}, headers: HeadersInit = {}) =>
  json({ error, ...extra }, status, headers);

export class HttpError extends Error {
  constructor(public res: Response) { super('http'); }
}

/* Browser POSTs must come from this site. `optional`: callers that aren't browsers (the app, the app's server)
   send no Origin; if one is sent anyway, it must still be ours. */
export function checkOrigin(req: Request, optional = false) {
  const origin = req.headers.get('origin');
  if (!origin && optional) return;
  if (origin !== new URL(req.url).origin) throw new HttpError(fail(403, 'bad_origin'));
}

/* The JSON body, or a 400. */
export async function body<T = Record<string, unknown>>(req: Request): Promise<T> {
  if (!(req.headers.get('content-type') || '').includes('application/json')) throw new HttpError(fail(415, 'json_only'));
  try { const b = await req.json(); if (b && typeof b === 'object') return b as T; } catch {}
  throw new HttpError(fail(400, 'bad_json'));
}

/* Runs a handler and turns a thrown HttpError into its response. */
export const route = (fn: (req: Request, url: URL) => Promise<Response>) =>
  async ({ request }: { request: Request }) => {
    try { return await fn(request, new URL(request.url)); }
    catch (e) {
      if (e instanceof HttpError) return e.res;
      await record(kindOf(e), `${request.method} ${new URL(request.url).pathname}`, e);
      return fail(500, 'server_error');
    }
  };

export const ip = (req: Request) => req.headers.get('cf-connecting-ip') || '0.0.0.0';

export function cookie(req: Request, name: string) {
  const m = (req.headers.get('cookie') || '').match(new RegExp('(?:^|;\\s*)' + name + '=([^;]*)'));
  return m ? decodeURIComponent(m[1]) : null;
}

export const str = (v: unknown, max = 500) => (typeof v === 'string' ? v.trim().slice(0, max) : '');
