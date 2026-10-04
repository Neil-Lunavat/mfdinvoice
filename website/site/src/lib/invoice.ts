/* Our tax invoices to buyers: the lines, the tax split, and how they read. */
import { BUSINESS, PRICE, SALES } from '../consts';
import { STATES } from './gstin';
import { extraFor, monthsLine, type Kind } from './price';
import { longDate } from './date';
/* the backend imports the date helpers from here; point it at date.ts in the backend pass */
export { longDate, shortDate, monthYear } from './date';

export type Line = { text: string; amount: number };   /* amount in paise, before tax */

/* months: for 'add', the months left on the plan that each extra ARN costs (price.ts monthsLeft). */
export function invoiceLines(kind: Kind, arns: number, endsOn: string, months = 12): Line[] {
  if (kind === 'add') return [{ text: `${arns} more ARN${arns > 1 ? 's' : ''} ${monthsLine(months, endsOn)}`, amount: extraFor(months) * arns * 100 }];
  const lines = [{ text: `Yearly plan, ${arns === 1 && !SALES.moreArns ? 'one' : 'first'} ARN, until ${longDate(endsOn)}`, amount: PRICE.first * 100 }];
  if (arns > 1) lines.push({ text: `${arns - 1} more ARN${arns > 2 ? 's' : ''}`, amount: PRICE.extra * (arns - 1) * 100 });
  return lines;
}

/* CGST 9% + SGST 9% inside the seller's state (the buyer's GSTIN starts with it), IGST 18% outside it. */
export function taxSplit(buyerGstin: string | null, gst: number) {
  if (!gst) return { cgst: 0, sgst: 0, igst: 0 };
  const local = (buyerGstin ?? '').slice(0, 2) === BUSINESS.stateCode;
  const half = Math.floor(gst / 2);
  return local ? { cgst: half, sgst: gst - half, igst: 0 } : { cgst: 0, sgst: 0, igst: gst };
}

export const stateOf = (gstin: string | null) => (gstin ? `${STATES[gstin.slice(0, 2)] ?? 'Unknown'} (${gstin.slice(0, 2)})` : null);

/* 5310.00 → "Five thousand three hundred and ten rupees only", Indian grouping. */
const ONES = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen'];
const TENS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety'];
function upTo99(n: number) { return n < 20 ? ONES[n] : TENS[Math.floor(n / 10)] + (n % 10 ? '-' + ONES[n % 10] : ''); }
function upTo999(n: number) {
  const h = Math.floor(n / 100), r = n % 100;
  return [h ? ONES[h] + ' hundred' : '', r ? (h ? 'and ' : '') + upTo99(r) : ''].filter(Boolean).join(' ');
}
function words(n: number): string {
  if (!n) return 'zero';
  const parts: string[] = [];
  const crore = Math.floor(n / 1e7), lakh = Math.floor(n / 1e5) % 100, thou = Math.floor(n / 1e3) % 100, rest = n % 1000;
  if (crore) parts.push(words(crore) + ' crore');
  if (lakh) parts.push(upTo99(lakh) + ' lakh');
  if (thou) parts.push(upTo99(thou) + ' thousand');
  if (rest) parts.push(upTo999(rest));
  return parts.join(' ');
}
export function amountInWords(paise: number) {
  const r = Math.floor(paise / 100), p = paise % 100;
  const s = words(r) + ' rupees' + (p ? ' and ' + upTo99(p) + ' paise' : '') + ' only';
  return s[0].toUpperCase() + s.slice(1);
}
