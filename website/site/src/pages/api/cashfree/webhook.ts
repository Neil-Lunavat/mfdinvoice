/* POST from Cashfree (the order's notify_url). Checks x-webhook-signature (timestamp + raw body, the secret key),
   and on PAYMENT_SUCCESS_WEBHOOK asks Cashfree for the order's state before completing it, so the amount is ours.
   Anything else is acknowledged and ignored. */
import { route, json, fail } from '../../../lib/server/http';
import { getOrder, completeOrder } from '../../../lib/server/orders';
import { webhookSignatureOk, paidPayment } from '../../../lib/server/cashfree';
export const prerender = false;

export const POST = route(async req => {
  const raw = await req.text();
  if (!(await webhookSignatureOk(raw, req.headers.get('x-webhook-timestamp') || '', req.headers.get('x-webhook-signature') || '')))
    return fail(400, 'bad_signature');
  let ev: any;
  try { ev = JSON.parse(raw); } catch { return fail(400, 'bad_json'); }
  const orderId = ev?.data?.order?.order_id;
  if (ev?.type === 'PAYMENT_SUCCESS_WEBHOOK' && typeof orderId === 'string') {
    const o = await getOrder(orderId);
    if (!o || o.provider !== 'cashfree') return json({ ok: true, known: false });
    const paymentId = o.status === 'paid' ? o.payment_id : await paidPayment(o.id, o.total);
    if (paymentId) await completeOrder(o.id, paymentId);
    return json({ ok: true, known: true, paid: !!paymentId });
  }
  return json({ ok: true, ignored: ev?.type ?? null });
});
