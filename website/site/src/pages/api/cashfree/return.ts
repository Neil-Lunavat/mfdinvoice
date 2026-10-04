/* GET ?order_id=… · where Cashfree sends the browser if its checkout leaves the page (some banks and UPI apps do).
   Completes the order if Cashfree says it's paid, then goes on as Checkout's Continue would: a new plan to Downloads,
   more ARNs to Account. Not paid: back to Checkout. */
import { route } from '../../../lib/server/http';
import { getOrder, completeOrder } from '../../../lib/server/orders';
import { paidPayment } from '../../../lib/server/cashfree';
export const prerender = false;

const go = (to: string) => new Response(null, { status: 302, headers: { location: to, 'cache-control': 'no-store' } });

export const GET = route(async (req, url) => {
  const o = await getOrder((url.searchParams.get('order_id') || '').slice(0, 64));
  if (!o || o.provider !== 'cashfree') return go('/account');
  const paymentId = o.status === 'paid' ? o.payment_id : await paidPayment(o.id, o.total);
  if (!paymentId) return go(o.kind === 'add' ? '/checkout?add=1' : `/checkout?arns=${o.arns}`);
  await completeOrder(o.id, paymentId);
  return go(o.kind === 'add' ? '/account' : '/downloads');
});
