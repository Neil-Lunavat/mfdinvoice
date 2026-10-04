/* POST, after the provider's checkout reports success → { ok, total, kind, arns, email, invoice }
   Razorpay: { order_id, payment_id, signature } (its success callback; the signature is checked).
   Cashfree: { order_id } (Cashfree is asked whether the order is paid, for our amount).
   Then the order completes, once, however many times this or a webhook is called. */
import { route, checkOrigin, body, json, fail, str } from '../../../lib/server/http';
import { webSession } from '../../../lib/server/auth';
import { getOrder, completeOrder } from '../../../lib/server/orders';
import { paymentSignatureOk } from '../../../lib/server/razorpay';
import { paidPayment } from '../../../lib/server/cashfree';
export const prerender = false;

export const POST = route(async req => {
  checkOrigin(req);
  const s = await webSession(req);
  if (!s) return fail(401, 'signed_out');
  const b = await body(req);
  const o = await getOrder(str(b.order_id, 64));
  if (!o || o.account_id !== s.account_id) return fail(404, 'no_order');
  /* a UPI payment completes only when the owner approves it */
  if (o.provider === 'upi') return fail(400, 'upi_is_reviewed');
  let paymentId: string | null;
  if (o.provider === 'razorpay') {
    paymentId = str(b.payment_id, 64);
    if (!(await paymentSignatureOk(o.id, paymentId, str(b.signature, 128)))) return fail(400, 'bad_signature');
  } else {
    paymentId = o.status === 'paid' ? o.payment_id : await paidPayment(o.id, o.total);
    if (!paymentId) return fail(402, 'not_paid');
  }
  const r = (await completeOrder(o.id, paymentId!))!;
  return json({ ok: true, total: r.order.total, kind: r.order.kind, arns: r.order.arns, email: r.order.email, invoice: r.invoice?.number ?? null });
});
