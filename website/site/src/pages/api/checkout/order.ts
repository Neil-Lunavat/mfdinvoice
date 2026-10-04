/* POST { kind, arns, name, address, gstin? (only while SALES.gst), phone? } → { provider, order_id, amount, currency, email, name, kind, arns, ... }
   Creates an order with the active payment provider (lib/server/pay.ts) for a new plan or, when a plan is running,
   for more ARNs (each for the months left on the plan). The amount is worked out here. UPI adds { qr (SVG), upi_id, upi_name } and reuses the buyer's
   unfinished UPI order; Razorpay adds { key }; Cashfree adds { session, mode } and needs `phone`. */
import { env } from 'cloudflare:workers';
import { NAME, TERMS_VERSION } from '../../../consts';
import { route, checkOrigin, body, json, fail } from '../../../lib/server/http';
import { webSession } from '../../../lib/server/auth';
import { billing, saveBilling } from '../../../lib/server/account';
import { allowance, quote } from '../../../lib/server/orders';
import { activeProvider, normPhone } from '../../../lib/server/pay';
import * as razorpay from '../../../lib/server/razorpay';
import * as cashfree from '../../../lib/server/cashfree';
import { newRef, upiQr, openUpiOrder, rejectedBlock } from '../../../lib/server/upi';
import { UPI } from '../../../consts';
import { now, token } from '../../../lib/server/util';
export const prerender = false;

export const POST = route(async req => {
  checkOrigin(req);
  const s = await webSession(req);
  if (!s) return fail(401, 'signed_out');
  const b = await body(req);
  const bill = billing(b);
  if ('error' in bill) return fail(400, bill.error);
  const { kind, max, months } = await allowance(s.account_id);
  /* the page says which it is showing; if the plan changed meanwhile, the page must reload */
  if (b.kind !== kind) return fail(409, 'plan_changed', { kind });
  const arns = Number(b.arns);
  if (!Number.isInteger(arns) || arns < 1 || arns > max) return fail(400, 'bad_arns', { max });

  const provider = activeProvider();
  const phone = normPhone(b.phone);
  if (provider === 'cashfree' && !phone) return fail(400, 'bad_phone');

  const q = quote(kind, arns, months);
  let id: string, extra: Record<string, unknown>;
  if (provider === 'upi') {
    const open = await openUpiOrder(s.account_id);
    /* one at a time: a screenshot already sent waits for the owner; after a rejection, only support */
    if (open?.status === 'review') return fail(409, 'in_review', { ref: open.id });
    const blocked = await rejectedBlock(s.account_id, s.email);
    if (blocked) return fail(409, 'rejected', { ref: blocked.id });
    const reuse = open && open.status === 'created' && open.kind === kind && open.arns === arns && open.total === q.total;
    id = reuse ? open!.id : newRef();
    extra = { qr: upiQr(id, q.total).svg, upi_id: UPI.id, upi_name: UPI.name };
    if (reuse) {
      await saveBilling(s.account_id, bill);
      await env.DB.prepare('UPDATE orders SET bill_name = ?, bill_gstin = ?, bill_address = ?, terms = ? WHERE id = ?').bind(bill.name, bill.gstin, bill.address, TERMS_VERSION, id).run();
      return json({ provider, order_id: id, amount: q.total, currency: 'INR', email: s.email, name: NAME, kind, arns, ...extra });
    }
  } else if (provider === 'razorpay') {
    const rz = await razorpay.createOrder(q.total, `a${s.account_id}-${Date.now()}`, { account: String(s.account_id), kind, arns: String(arns) });
    if (!rz) return fail(502, 'payment_unavailable');
    id = rz.id; extra = { key: razorpay.keyId() };
  } else {
    id = `cf_${s.account_id}_${Date.now()}_${token().replace(/[^A-Za-z0-9]/g, '').slice(0, 8)}`;
    const cf = await cashfree.createOrder({ id, amount: q.total, account: s.account_id, email: s.email, phone: phone!, origin: new URL(req.url).origin });
    if (!cf) return fail(502, 'payment_unavailable');
    extra = { session: cf.sessionId, mode: cashfree.mode() };
  }

  await env.DB.batch([
    env.DB.prepare(`INSERT INTO orders (id, provider, account_id, email, phone, kind, arns, months, subtotal, gst, total, bill_name, bill_gstin, bill_address, terms, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`)
      .bind(id, provider, s.account_id, s.email, phone, kind, arns, kind === 'add' ? months : null, q.subtotal, q.gst, q.total, bill.name, bill.gstin, bill.address, TERMS_VERSION, now()),
    /* the details the buyer entered become their saved billing details */
    env.DB.prepare('UPDATE accounts SET phone = COALESCE(?, phone) WHERE id = ?').bind(phone, s.account_id),
  ]);
  await saveBilling(s.account_id, bill);
  return json({ provider, order_id: id, amount: q.total, currency: 'INR', email: s.email, name: NAME, kind, arns, ...extra });
});
