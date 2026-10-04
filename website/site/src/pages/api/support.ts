/* GET → { requests: [{ id, topic, about, status, created_at }], arns: ["123456", …] } · the signed-in account's own
   requests, newest first, and its ARNs (for "Change an ARN on my plan").
   POST multipart/form-data { topic, arn?, new_email?, message?, screenshot (up to 3; JPEG, PNG or WebP, 8 MB each) }
   → { ok, id, email } · a support request from a signed-in account (lib/server/support.ts). Multipart because it
   carries files; the Origin check is the same as for JSON. */
import { env } from 'cloudflare:workers';
import { route, checkOrigin, json, fail, str, HttpError } from '../../lib/server/http';
import { webSession } from '../../lib/server/auth';
import { normArn } from '../../lib/server/arn';
import { submitRequest } from '../../lib/server/support';
import { getArns } from '../../lib/server/account';
import { TOPICS, SHOT_TYPES, SHOT_MAX, SHOTS } from '../../lib/support';
import { cleanEmail } from '../../lib/server/util';
export const prerender = false;

export const GET = route(async req => {
  const s = await webSession(req);
  if (!s) return fail(401, 'signed_out');
  const r = await env.DB.prepare('SELECT id, topic, status, created_at FROM requests WHERE account_id = ? ORDER BY created_at DESC LIMIT 100')
    .bind(s.account_id).all<{ id: number; topic: string; status: string; created_at: string }>();
  return json({ requests: r.results.map(x => ({ ...x, about: TOPICS[x.topic]?.label ?? x.topic })), arns: (await getArns(s.account_id)).map(a => a.arn) });
});

export const POST = route(async req => {
  checkOrigin(req);
  const s = await webSession(req);
  if (!s) return fail(401, 'signed_out');
  if (Number(req.headers.get('content-length') || 0) > SHOTS * SHOT_MAX + 256 * 1024) return fail(413, 'too_big');
  const form = await req.formData().catch(() => { throw new HttpError(fail(400, 'bad_form')); });
  const topic = String(form.get('topic') || '');
  const t = TOPICS[topic];
  if (!t) return fail(400, 'bad_topic');
  const arn = t.arn ? normArn(form.get('arn')) : null;
  if (t.arn === 2 && !arn) return fail(400, 'bad_arn');
  if (t.mine && !(await getArns(s.account_id)).some(a => a.arn === arn)) return fail(400, 'not_your_arn');
  const newEmail = t.newEmail ? cleanEmail(str(form.get('new_email'), 254)) : null;
  if (t.newEmail && !newEmail) return fail(400, 'bad_new_email');
  const message = t.noMsg ? null : str(form.get('message'), 5000) || null;
  if (!t.noMsg && !t.newEmail && (!message || message.length < 4)) return fail(400, 'no_message');
  const shots = t.noMsg ? [] : form.getAll('screenshot').filter((f): f is File => f instanceof File && f.size > 0);
  if (shots.length > SHOTS) return fail(400, 'too_many_files');
  if (shots.some(f => !SHOT_TYPES[f.type])) return fail(415, 'not_an_image');
  if (shots.some(f => f.size > SHOT_MAX)) return fail(413, 'too_big');
  const r = await submitRequest(s, { topic, arn, newEmail, message, shots });
  return json({ ok: true, id: r.id, email: s.email });
});
