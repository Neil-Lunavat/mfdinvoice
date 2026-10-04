/* The blog, from the `posts` table. The editor (WRITE_HOST) writes a post, sees it exactly as it will be on the site,
   then publishes it: it's live at once. A post is /blog/<slug>; when its slug changes, the old one is kept in
   `post_aliases` and still opens it (a permanent redirect), however many times it changes. Each publish and delete is
   logged and clears the blog from Cloudflare's edge cache. Images live in R2 under blog/. */
import { env, cache } from 'cloudflare:workers';
import { postPath } from '../blog';
import { slugify } from '../markdown';
import { str } from './http';
import { record } from './errors';
import { event } from './events';
import { now, token } from './util';

export type Post = {
  id: number; slug: string; seo_title: string; title: string; description: string; body: string; cover: string | null;
  created_at: string; updated_at: string;
};
const withPath = <T extends { slug: string }>(p: T) => ({ ...p, path: postPath(p.slug) });

export const IMAGE_TYPES: Record<string, string> = { 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp', 'image/gif': 'gif', 'image/svg+xml': 'svg' };
export const IMAGE_MAX = 5 * 1024 * 1024;
/* R2 key blog/<name> ↔ the public address /blog/images/<name> */
export const imageUrl = (key: string | null) => (key ? `/blog/images/${key.replace(/^blog\//, '')}` : null);

/* ---- reading ---- */

export const getPost = (id: number) => env.DB.prepare('SELECT * FROM posts WHERE id = ?').bind(id).first<Post>().then(p => (p ? withPath(p) : null));

/* Every post, newest first, with its address. */
export const listPosts = () =>
  env.DB.prepare('SELECT * FROM posts ORDER BY created_at DESC').all<Post>().then(r => r.results.map(withPath));

/* The post at /blog/<slug>; or, for one of its earlier slugs, where it is now. */
export async function findPost(slug: string): Promise<{ post: Post & { path: string } } | { moved: string } | null> {
  const p = await env.DB.prepare('SELECT * FROM posts WHERE slug = ?').bind(slug).first<Post>();
  if (p) return { post: withPath(p) };
  const a = await env.DB.prepare('SELECT p.slug FROM post_aliases a JOIN posts p ON p.id = a.post_id WHERE a.slug = ?').bind(slug).first<{ slug: string }>();
  return a ? { moved: postPath(a.slug) } : null;
}

/* ---- writing ---- */

/* The editor's fields, cleaned: what the preview shows and what Publish saves. */
export function draftOf(b: Record<string, unknown>) {
  const cover = typeof b.cover === 'string' && /^blog\/[A-Za-z0-9._-]+$/.test(b.cover) ? b.cover : null;
  return {
    title: str(b.title, 200), seo_title: str(b.seo_title, 200), slug: slugify(str(b.slug, 120)),
    description: str(b.description, 400), body: typeof b.body === 'string' ? b.body.slice(0, 200_000) : '', cover,
  };
}

/* What's still missing before it can be published, or null. */
export function missing(p: ReturnType<typeof draftOf>) {
  return !p.title ? 'no_title' : !p.seo_title ? 'no_search_title' : !p.slug ? 'no_slug' : !p.description ? 'no_description' : !p.body.trim() ? 'no_text' : null;
}

/* Clears the blog from Cloudflare's edge cache (the pages carry the tag 'blog'). Locally there's nothing to clear. */
async function purge() {
  try { await cache.purge({ tags: ['blog'] }); } catch (e) { if (env.EMAIL_CONSOLE !== '1') await record('server', 'blog cache purge', e); }
}

/* Publish: a new post (no id) or changes to one. It's live at once. A slug that another post uses, now or before, is
   refused. by: the writer's email. */
export async function savePost(id: number | null, b: Record<string, unknown>, by: string) {
  const p = draftOf(b);
  const gap = missing(p);
  if (gap) return { error: gap };
  const other = await env.DB.prepare(`SELECT id FROM posts WHERE slug = ?1 UNION ALL SELECT post_id FROM post_aliases WHERE slug = ?1`)
    .bind(p.slug).all<{ id: number }>();
  if (other.results.some(o => o.id !== id)) return { error: 'slug_taken' };
  const at = now();
  if (id) {
    const was = await env.DB.prepare('SELECT slug FROM posts WHERE id = ?').bind(id).first<{ slug: string }>();
    if (!was) return { error: 'no_post' };
    await env.DB.batch([
      env.DB.prepare(`UPDATE posts SET slug = ?, seo_title = ?, title = ?, description = ?, body = ?, cover = ?, updated_at = ? WHERE id = ?`)
        .bind(p.slug, p.seo_title, p.title, p.description, p.body, p.cover, at, id),
      /* the old slug keeps opening it; the new one isn't an alias any more */
      ...(was.slug !== p.slug ? [
        env.DB.prepare('INSERT INTO post_aliases (slug, post_id) VALUES (?, ?) ON CONFLICT (slug) DO UPDATE SET post_id = excluded.post_id').bind(was.slug, id),
        env.DB.prepare('DELETE FROM post_aliases WHERE slug = ?').bind(p.slug),
      ] : []),
    ]);
  } else {
    id = (await env.DB.prepare(`INSERT INTO posts (slug, seo_title, title, description, body, cover, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id`).bind(p.slug, p.seo_title, p.title, p.description, p.body, p.cover, at, at).first<{ id: number }>())!.id;
  }
  const path = postPath(p.slug);
  await event(`writer:${by}`, 'post.saved', null, `post ${id}`, path).run();
  await purge();
  return { ok: true, id, path };
}

/* Delete: off the blog; its address, and every earlier one, shows "not found". */
export async function deletePost(id: number, by: string) {
  const [r] = await env.DB.batch([
    env.DB.prepare('DELETE FROM posts WHERE id = ?').bind(id),
    env.DB.prepare('DELETE FROM post_aliases WHERE post_id = ?').bind(id),
  ]);
  if (!r.meta.changes) return { error: 'no_post' };
  await event(`writer:${by}`, 'post.deleted', null, `post ${id}`).run();
  await purge();
  return { ok: true };
}

/* Every image in the library (R2, blog/…), newest first, with the posts that use it (in the text or as the cover). */
export async function listImages() {
  const objects: R2Object[] = [];
  let cursor: string | undefined;
  do {
    const page = await env.FILES.list({ prefix: 'blog/', cursor });
    objects.push(...page.objects);
    cursor = page.truncated ? page.cursor : undefined;
  } while (cursor);
  const posts = await listPosts();
  return objects.sort((a, b) => +b.uploaded - +a.uploaded).map(o => {
    const url = imageUrl(o.key)!;
    return { key: o.key, url, size: o.size, uploaded: o.uploaded.toISOString(),
      usedIn: posts.filter(p => p.cover === o.key || p.body.includes(url)).map(p => ({ id: p.id, title: p.title })) };
  });
}

/* Deletes an image from the library. A post still using it shows a broken image, so the page warns first. */
export async function deleteImage(key: string, by: string) {
  if (!/^blog\/[A-Za-z0-9._-]+$/.test(key)) return { error: 'no_image' };
  await env.FILES.delete(key);
  await event(`writer:${by}`, 'image.deleted', null, key).run();
  return { ok: true };
}

/* An image for a post: kept in R2, served at /blog/images/<name>. */
export async function saveImage(file: File) {
  const key = `blog/${token().slice(0, 12)}.${IMAGE_TYPES[file.type]}`;
  await env.FILES.put(key, await file.arrayBuffer(), { httpMetadata: { contentType: file.type, cacheControl: 'public, max-age=31536000, immutable' } });
  return { key, url: imageUrl(key)! };
}
