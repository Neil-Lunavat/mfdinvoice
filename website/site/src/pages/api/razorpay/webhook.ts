/* POST from Razorpay (payment.captured, order.paid). Checks X-Razorpay-Signature against the raw body with
   RAZORPAY_WEBHOOK_SECRET, then completes the order if the browser didn't. Anything else is acknowledged and ignored. */
import { route, json, fail } from '../../../lib/server/http';
import { completeOrder } from '../../../lib/server/orders';
import { webhookSignatureOk } from '../../../lib/server/razorpay';
export const prerender = false;

export const POST = route(async req => {
  const raw = await req.text();
  if (!(await webhookSignatureOk(raw, req.headers.get('x-razorpay-signature') || ''))) return fail(400, 'bad_signature');
  let ev: any;
  try { ev = JSON.parse(raw); } catch { return fail(400, 'bad_json'); }
  if (ev.event === 'payment.captured' || ev.event === 'order.paid') {
    const p = ev.payload?.payment?.entity;
    const orderId = ev.payload?.order?.entity?.id || p?.order_id;
    if (orderId && p?.id) {
      const r = await completeOrder(orderId, p.id);
      return json({ ok: true, known: !!r });
    }
  }
  return json({ ok: true, ignored: ev.event ?? null });
});
