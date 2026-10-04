/* POST multipart/form-data { order_id, screenshot (JPEG, PNG or WebP, 8 MB at most), utr? } → { ok, ref, email }
   The UPI payment's screenshot: the order goes to review and the owner is emailed. The one POST that isn't JSON,
   because it carries a file; the Origin check is the same. */
import { route, checkOrigin, json, fail, HttpError } from '../../../lib/server/http';
import { webSession } from '../../../lib/server/auth';
import { getOrder } from '../../../lib/server/orders';
import { submitProof, PROOF_TYPES, PROOF_MAX } from '../../../lib/server/upi';
export const prerender = false;

export const POST = route(async req => {
  checkOrigin(req);
  const s = await webSession(req);
  if (!s) return fail(401, 'signed_out');
  if (Number(req.headers.get('content-length') || 0) > PROOF_MAX + 64 * 1024) return fail(413, 'too_big');
  const form = await req.formData().catch(() => { throw new HttpError(fail(400, 'bad_form')); });
  const o = await getOrder(String(form.get('order_id') || '').slice(0, 20));
  if (!o || o.account_id !== s.account_id || o.provider !== 'upi') return fail(404, 'no_order');
  if (o.status === 'review') return fail(409, 'in_review');
  if (o.status !== 'created') return fail(409, 'not_open', { status: o.status });
  const file = form.get('screenshot');
  if (!(file instanceof File) || !file.size) return fail(400, 'no_screenshot');
  if (!PROOF_TYPES[file.type]) return fail(415, 'not_an_image');
  if (file.size > PROOF_MAX) return fail(413, 'too_big');
  /* the UTR is optional: 12 digits on most UPI apps; kept as typed, letters and digits only */
  const utr = String(form.get('utr') || '').toUpperCase().replace(/[^0-9A-Z]/g, '').slice(0, 22) || null;
  await submitProof(o, file, utr);
  return json({ ok: true, ref: o.id, email: s.email });
});
