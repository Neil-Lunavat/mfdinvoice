/* POST multipart { id, subject, message, photo (up to 3) } → { ok, at } · the panel's one reply to a support request,
   from support@ (lib/server/support.ts, replyToRequest). The rest of the conversation happens in the mailbox. */
import { json, fail, str, HttpError } from '../../../../lib/server/http';
import { gated } from '../../../../lib/server/admin';
import { replyToRequest } from '../../../../lib/server/support';
import { SHOT_TYPES, SHOTS } from '../../../../lib/support';
import { ATTACH_MAX } from '../../../../lib/server/mail';
export const prerender = false;

export const POST = gated('control', async (req, _url, me) => {
  if (Number(req.headers.get('content-length') || 0) > ATTACH_MAX + 256 * 1024) return fail(413, 'too_big');
  const form = await req.formData().catch(() => { throw new HttpError(fail(400, 'bad_form')); });
  const subject = str(form.get('subject'), 200).trim(), message = str(form.get('message'), 20000).trim();
  if (!subject) return fail(400, 'no_subject');
  if (message.length < 2) return fail(400, 'no_message');
  const photos = form.getAll('photo').filter((f): f is File => f instanceof File && f.size > 0);
  if (photos.length > SHOTS) return fail(400, 'too_many_files');
  if (photos.some(f => !SHOT_TYPES[f.type])) return fail(415, 'not_an_image');
  if (photos.reduce((n, f) => n + f.size, 0) > ATTACH_MAX) return fail(413, 'too_big');
  const r = await replyToRequest(Number(form.get('id')), { subject, message, photos }, me.email);
  return 'error' in r ? fail(r.error === 'no_request' ? 404 : 502, r.error!) : json(r);
});
