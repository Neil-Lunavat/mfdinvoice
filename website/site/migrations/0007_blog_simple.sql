-- The blog, simpler: a post lives at /blog/<slug> (typed by hand), with a search title (the tab and Google's link)
-- apart from its heading. No clusters, questions or authors.
ALTER TABLE posts ADD COLUMN seo_title TEXT NOT NULL DEFAULT '';
ALTER TABLE posts DROP COLUMN cluster;
ALTER TABLE posts DROP COLUMN faq;
ALTER TABLE posts DROP COLUMN author;

-- A post's earlier addresses: each still opens the post (a permanent redirect to where it is now).
CREATE TABLE post_aliases (
  slug    TEXT PRIMARY KEY,
  post_id INTEGER NOT NULL REFERENCES posts (id) ON DELETE CASCADE
);
CREATE INDEX post_aliases_post ON post_aliases (post_id);
