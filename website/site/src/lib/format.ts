/* Small helpers shared by pages and their scripts. */
import { BUSINESS } from '../consts';

/* ₹4,000 — whole rupees, Indian grouping. */
export const inr = (n: number) => '₹' + n.toLocaleString('en-IN');

/* "six" for 6, for numbers written out in copy. */
const WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve'];
export const word = (n: number) => WORDS[n] ?? String(n);

/* A business detail still in [brackets] is a placeholder and is shown greyed. */
export const isPlaceholder = (v: string) => v.startsWith('[');
/* ... as HTML, for a value set into a sentence (the legal pages): greyed while it is a placeholder (kit.css .ph) */
export const shown = (v: string) => (isPlaceholder(v) ? `<span class="ph">${v}</span>` : v);

/* The company as an address block, as HTML, for the legal pages' Contact. The phone appears here and nowhere else. */
export const companyLine = () => {
  const B = BUSINESS, cap = (s: string) => s[0].toUpperCase() + s.slice(1);
  return [`<b>${B.legalName}</b>`, shown(cap(B.entity)), `${shown(B.address)}, ${B.state}, India`,
    `Phone: <a href="tel:${B.phone.replace(/\s/g, '')}">${shown(B.phone)}</a>`, `Email: <a href="mailto:${B.email}">${B.email}</a>`].join('<br>');
};
