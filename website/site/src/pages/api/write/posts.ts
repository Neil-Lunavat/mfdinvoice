/* POST { action: "save", id?, ...post } → { ok, id, path } · a new post (no id) or changes to one; live at once.
   POST { action: "delete", id } → { ok } · the blog editor (lib/server/blog.ts). */
import { json, fail, body } from '../../../lib/server/http';
import { gated } from '../../../lib/server/admin';
import { savePost, deletePost } from '../../../lib/server/blog';
export const prerender = false;

export const POST = gated('write', async (req, _url, me) => {
  const b = await body(req);
  const id = Number(b.id) || null;
  const r = b.action === 'save' ? await savePost(id, b, me.email)
    : b.action === 'delete' && id ? await deletePost(id, me.email)
    : { error: 'bad_action' };
  return 'error' in r ? fail(400, r.error!) : json(r);
});
