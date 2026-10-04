/* The blog's addresses and lengths. Posts live in the database (lib/server/blog.ts). */

/* A post is at /blog/<slug>; the slug is typed by hand. */
export const postPath = (slug: string) => `/blog/${slug}`;

/* The search title and the description: about this long for search results. */
export const TITLE_LEN = 60, DESCRIPTION_LEN = 155;
