/* What a purchase costs, from PRICE in consts.ts. Amounts in paise, so the tax is exact.
   The server uses this to charge; Checkout uses it only to show the same numbers. */
import { PRICE, SALES } from '../consts';
import { shortDate } from './date';

export type Kind = 'new' | 'add';

/* Every ARN on an account ends on the plan's last day, so an ARN added later costs its share of a year, in whole
   months rounded up (owner, 29 Sep 2026): the months from the purchase day to the plan's last day, any part month
   counting as a whole one, 1 to 12. 15 Mar 2027 → 30 Sep 2027 is 6.5 months, so 7. Days are 'YYYY-MM-DD'. */
export function monthsLeft(today: string, lastDay: string) {
  const [y, m, d] = today.split('-').map(Number);
  for (let n = 1; n <= 12; n++) {
    /* the same day n months on (clamped to the month's end): once that's past the last day, n months cover it */
    const t = new Date(Date.UTC(y, m - 1 + n, 1));
    const end = new Date(Date.UTC(t.getUTCFullYear(), t.getUTCMonth() + 1, 0)).getUTCDate();
    const day = `${t.getUTCFullYear()}-${String(t.getUTCMonth() + 1).padStart(2, '0')}-${String(Math.min(d, end)).padStart(2, '0')}`;
    if (day > lastDay) return n;
  }
  return 12;
}

/* One extra ARN for `months` months, in whole rupees: ceil(₹500 × months / 12). */
export const extraFor = (months = 12) => Math.ceil((PRICE.extra * months) / 12);

/* months: for 'add', the months left on the plan (monthsLeft); a new plan is always a full year. */
export function quote(kind: Kind, arns: number, months = 12) {
  const rupees = kind === 'new' ? PRICE.first + PRICE.extra * (arns - 1) : extraFor(months) * arns;
  const subtotal = rupees * 100;
  const gst = SALES.gst ? Math.round(subtotal * PRICE.gst) : 0;   /* no GST while we aren't registered */
  return { subtotal, gst, total: subtotal + gst };
}

/* ₹5,310.00 */
export const rupees = (paise: number) =>
  '₹' + (paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/* "for the 7 months left on your plan (to 30 Sep 2027)" */
export const monthsLine = (months: number, lastDay: string) =>
  `for the ${months === 1 ? 'month' : months + ' months'} left on your plan (to ${shortDate(lastDay)})`;

/* "Yearly plan, 2 ARNs" / "2 more ARNs for the 7 months left on your plan (to 30 Sep 2027)": what a payment was
   for, on Account and in emails. */
export const forWhat = (kind: Kind, arns: number, months?: number | null, lastDay?: string | null) =>
  kind === 'new'
    ? `Yearly plan, ${arns} ARN${arns > 1 ? 's' : ''}`
    : `${arns} more ARN${arns > 1 ? 's' : ''}${months && lastDay ? ' ' + monthsLine(months, lastDay) : ''}`;
