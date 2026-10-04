/* A blog post's Markdown → HTML: the public post and the editor's preview use the same.
   HTML inside the Markdown is kept (the team writes the posts; the site's CSP stops any script in it).
   Each ## heading gets an id from its words, so "On this page" can link to it. An image on its own line is a figure:
   centred, with its alt text (![caption](…)) as the caption underneath. */
import { Marked } from 'marked';

export const slugify = (s: string) =>
  s.toLowerCase().normalize('NFKD').replace(/<[^>]+>/g, '').replace(/[’']/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 80);

const attr = (s: string) => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!);

const md = new Marked({ gfm: true });
md.use({
  renderer: {
    paragraph({ tokens }) {
      const only = tokens.filter(t => !(t.type === 'text' && !t.raw.trim()));
      if (only.length === 1 && only[0].type === 'image') {
        const { href, text } = only[0] as { href: string; text: string };
        return `<figure><img src="${attr(href)}" alt="${attr(text)}" loading="lazy">${text ? `<figcaption>${attr(text)}</figcaption>` : ''}</figure>
`;
      }
      return `<p>${this.parser.parseInline(tokens)}</p>
`;
    },
    heading({ tokens, depth, text }) {
      const inner = this.parser.parseInline(tokens);
      return depth === 2 ? `<h2 id="${slugify(text)}">${inner}</h2>\n` : `<h${depth}>${inner}</h${depth}>\n`;
    },
  },
});

export const renderMarkdown = (src: string) => md.parse(src, { async: false }) as string;

/* The ## headings of rendered HTML, for "On this page". */
export const headingsOf = (html: string) =>
  [...html.matchAll(/<h2 id="([^"]+)">(.*?)<\/h2>/g)].map(([, id, t]) => ({ id, text: t.replace(/<[^>]+>/g, '') }));

/* Minutes to read, at about 220 words a minute. */
export const readMinutes = (src: string) => Math.max(1, Math.round(src.replace(/<[^>]+>/g, ' ').split(/\s+/).filter(Boolean).length / 220));

