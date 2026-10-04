/* Which payment provider takes new orders: PAYMENTS in wrangler.jsonc ('upi', 'cashfree' or 'razorpay').
   'upi' until the company is registered: the buyer pays the owner's UPI ID and sends a screenshot; the owner
   approves it by hand. Then a card gateway (Cashfree or Razorpay; both are parked in the code, ready).
   An order always completes with the provider that created it. */
import { env } from 'cloudflare:workers';

export type Provider = 'razorpay' | 'cashfree' | 'upi';
export function activeProvider(): Provider {
  const p = env.PAYMENTS as string;
  return p === 'cashfree' || p === 'razorpay' ? p : 'upi';
}
export const providerName = (p: Provider) => ({ cashfree: 'Cashfree', razorpay: 'Razorpay', upi: 'UPI' })[p];

/* Indian mobile numbers, as Cashfree wants them: 10 digits, starting 6–9 (a leading +91 or 0 is dropped). */
export function normPhone(v: unknown) {
  const d = typeof v === 'string' ? v.replace(/[\s-]/g, '').replace(/^(\+91|0)/, '') : '';
  return /^[6-9]\d{9}$/.test(d) ? d : null;
}
