/* POST multipart/form-data { image } → { ok, key, url } · an image for a post, kept in R2 (blog/…), served at
   /blog/images/<name>. JPEG, PNG, WebP, GIF or SVG, 5 MB at most.
   POST JSON { action: "delete", key } → { ok } · takes one out of the library (the Images tab). */
import { json, fail, body, str, HttpError } from '../../../lib/server/http';
import { gated } from '../../../lib/server/admin';
import { saveImage, deleteImage, IMAGE_TYPES, IMAGE_MAX } from '../../../lib/server/blog';
export const prerender = false;

export const POST = gated('write', async (req, _url, me) => {
  if ((req.headers.get('content-type') || '').includes('application/json')) {
    const b = await body(req);
    if (b.action !== 'delete') return fail(400, 'bad_action');
    const r = await deleteImage(str(b.key, 120), me.email);
    return 'error' in r ? fail(400, r.error!) : json(r);
  }
  if (Number(req.headers.get('content-length') || 0) > IMAGE_MAX + 64 * 1024) return fail(413, 'too_big');
  const form = await req.formData().catch(() => { throw new HttpError(fail(400, 'bad_form')); });
  const file = form.get('image');
  if (!(file instanceof File) || !file.size) return fail(400, 'no_image');
  if (!IMAGE_TYPES[file.type]) return fail(415, 'not_an_image');
  if (file.size > IMAGE_MAX) return fail(413, 'too_big');
  return json({ ok: true, ...(await saveImage(file)) });
});
