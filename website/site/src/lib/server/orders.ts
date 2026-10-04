/* Payments: an order is created before the buyer pays; it completes once, from whichever arrives first (a card
   gateway's browser callback or its webhook; for UPI, the owner's approval). Completing applies the plan (or the
   extra slots), issues our tax invoice (or, without GST, a receipt) and emails it. */
import { env } from 'cloudflare:workers';
import { BUSINESS, INVOICE_PREFIX, RECEIPT_PREFIX, PRICE, SALES } from '../../consts';
import { quote, rupees, forWhat, monthsLeft, type Kind } from '../price';
import { invoiceLines, taxSplit, stateOf, longDate, type Line } from '../invoice';
import { receiptMail } from '../emails';
import { now, todayIST, istDay, plusYear, fy, token, siteOrigin } from './util';
import { send } from './mail';
import { record } from './errors';
import { getPlan, holdsPlan, yearFrom, getAccount } from './account';

export type Order = {
  id: string; provider: 'razorpay' | 'cashfree' | 'upi'; account_id: number | null; email: string; phone: string | null; kind: Kind; arns: number; months: number | null; subtotal: number; gst: number; total: number;
  bill_name: string; bill_gstin: string | null; bill_address: string; status: 'created' | 'review' | 'paid' | 'rejected'; payment_id: string | null;
  claim: string | null; utr: string | null; proof: string | null; created_at: string; paid_at: string | null;
  reviewed_at: string | null; review_note: string | null; terms: string | null; sent_at: string | null; unblocked_at: string | null; note_shared: number;
};
export type Invoice = {
  number: string; doc: 'tax' | 'receipt'; fy: string; seq: number; order_id: string; account_id: number | null; issued_at: string; email: string;
  buyer_name: string; buyer_gstin: string | null; buyer_address: string; buyer_state: string | null; seller: string; lines: string;
  subtotal: number; cgst: number; sgst: number; igst: number; total: number;
};

/* How many ARNs this account may buy now, and of which kind. A new plan unless a bought or gifted one is running
   (a free trial is bought like a first plan); then more ARNs, each for the months left on the plan (price.ts
   monthsLeft). While SALES.moreArns is false: one ARN per email, so nothing more to buy once a plan runs. */
export async function allowance(accountId: number) {
  const plan = await getPlan(accountId);
  const cap = SALES.moreArns ? PRICE.maxArns : 1;
  return holdsPlan(plan)
    ? { kind: 'add' as Kind, max: Math.max(0, cap - plan!.slots), plan, months: monthsLeft(todayIST(), plan!.ends_on) }
    : { kind: 'new' as Kind, max: cap, plan, months: 12 };
}

export const getOrder = (id: string) => env.DB.prepare('SELECT * FROM orders WHERE id = ?').bind(id).first<Order>();
export const invoiceFor = (orderId: string) => env.DB.prepare('SELECT * FROM invoices WHERE order_id = ?').bind(orderId).first<Invoice>();

export { quote };

/* Marks the order paid and applies it, exactly once. All of it happens in one D1 batch (one transaction):
   the first statement claims the order with a fresh value, and every later statement only acts on that claim,
   so a second caller (webhook after browser, or the other way round) changes nothing. */
/* actor: who approved it (a UPI payment, from the admin panel); the approval is logged in the same batch. */
export async function completeOrder(orderId: string, paymentId: string, actor: string | null = null) {
  const o = await getOrder(orderId);
  if (!o) return null;
  if (o.status === 'paid') return { order: o, invoice: await invoiceFor(o.id) };
  if (o.status === 'rejected') return null;

  const claim = token(), today = todayIST(), at = now();
  const plan = o.account_id ? await getPlan(o.account_id) : null;
  /* a new plan: a year from today, or from the free trial's last day while one is running */
  const endsOn = o.kind === 'new' ? plusYear(yearFrom(plan)) : plan?.ends_on ?? plusYear(today);
  const lines: Line[] = invoiceLines(o.kind, o.arns, endsOn, o.months ?? 12);
  const tax = taxSplit(o.bill_gstin, o.gst);   /* all zero without GST */
  const f = fy(today);
  /* no GST charged → a receipt, in its own series */
  const doc = o.gst > 0 ? 'tax' : 'receipt', prefix = doc === 'tax' ? INVOICE_PREFIX : RECEIPT_PREFIX;
  const seller = JSON.stringify({ legalName: BUSINESS.legalName, address: BUSINESS.address, gstin: BUSINESS.gstin, state: BUSINESS.state, stateCode: BUSINESS.stateCode, sac: BUSINESS.sac, email: BUSINESS.email });
  const mine = 'FROM orders WHERE id = ?1 AND claim = ?2';

  const planStmt = o.kind === 'new'
    ? env.DB.prepare(`INSERT INTO plans (account_id, slots, starts_on, ends_on, source, updated_at)
        SELECT account_id, arns, ?3, ?4, 'paid', ?5 ${mine} AND account_id IS NOT NULL
        ON CONFLICT (account_id) DO UPDATE SET slots = excluded.slots, starts_on = excluded.starts_on,
          ends_on = excluded.ends_on, source = 'paid', updated_at = excluded.updated_at`).bind(orderId, claim, today, endsOn, at)
    /* capped at the maximum rather than failing: the payment has already been taken */
    : env.DB.prepare(`UPDATE plans SET slots = MIN(${PRICE.maxArns}, slots + (SELECT arns ${mine})), updated_at = ?3
        WHERE account_id = (SELECT account_id ${mine})`).bind(orderId, claim, at);

  const batch = [
    env.DB.prepare(`UPDATE orders SET status = 'paid', payment_id = ?3, paid_at = ?4, claim = ?2${actor ? ', reviewed_at = ?4' : ''} WHERE id = ?1 AND status IN ('created', 'review')`)
      .bind(orderId, claim, paymentId, at),
    planStmt,
    env.DB.prepare(`INSERT INTO invoices (number, doc, fy, seq, order_id, account_id, issued_at, email, buyer_name, buyer_gstin, buyer_address,
        buyer_state, seller, lines, subtotal, cgst, sgst, igst, total)
      SELECT ?3 || '/' || ?4 || '/' || printf('%04d', n.seq), ?12, ?4, n.seq, id, account_id, ?5, email, bill_name, bill_gstin, bill_address,
        ?6, ?7, ?8, subtotal, ?9, ?10, ?11, total
      FROM orders, (SELECT COALESCE(MAX(seq), 0) + 1 AS seq FROM invoices WHERE doc = ?12 AND fy = ?4) n
      WHERE id = ?1 AND claim = ?2`)
      .bind(orderId, claim, prefix, f, at, stateOf(o.bill_gstin), seller, JSON.stringify(lines), tax.cgst, tax.sgst, tax.igst, doc),
  ];
  if (actor) batch.push(env.DB.prepare(`INSERT INTO events (at, actor, action, account_id, ref, note)
      SELECT ?3, ?4, 'payment.approved', account_id, id, (SELECT number FROM invoices WHERE order_id = ?1) FROM orders WHERE id = ?1 AND claim = ?2`).bind(orderId, claim, at, actor));
  try {
    await env.DB.batch(batch);
  } catch (e) {
    /* the money has been taken and the plan isn't applied: critical, the owner is emailed */
    await record('order', `completeOrder ${orderId}`, e);
    throw e;
  }

  const done = (await getOrder(orderId))!;
  const invoice = await invoiceFor(orderId);
  if (done.claim === claim && invoice) {
    /* the payment is safe whatever happens to the email */
    await sendInvoiceMail(invoice, done).catch(e => record('email', `receipt ${invoice.number}`, e));
  }
  return { order: done, invoice };
}

/* The receipt (or tax invoice) email. Also the admin panel's "Resend". */
export async function sendInvoiceMail(inv: Invoice, o: Order, download = true) {
  const plan = o.account_id ? await getPlan(o.account_id) : null;
  const tax = inv.igst ? [['IGST 18%', rupees(inv.igst)]] : inv.cgst ? [['CGST 9%', rupees(inv.cgst)], ['SGST 9%', rupees(inv.sgst)]] : [];
  const lines = JSON.parse(inv.lines) as Line[];
  await send(inv.email, receiptMail({
    doc: inv.doc, number: inv.number, date: longDate(istDay(inv.issued_at)),
    forWhat: forWhat(o.kind, o.arns, o.months, lines.length && o.kind === 'add' && plan ? plan.ends_on : null),
    billedTo: inv.buyer_name, gstin: SALES.gst ? inv.buyer_gstin : null,
    lines: (tax.length ? [['Amount', rupees(inv.subtotal)], ...tax] : []) as [string, string][],
    total: rupees(inv.total), planUntil: plan && o.provider === 'upi' ? longDate(plan.ends_on) : null, upi: o.provider === 'upi',
    link: `${siteOrigin()}/account/invoices/${inv.number}`,
    download: download ? `${siteOrigin()}/downloads` : null,
  }));
}

/* The admin panel's "Resend": the same email again, to the address on the receipt. Logged once it has gone. */
/* Resends a receipt to the account's email as it is now. A receipt (not a tax invoice, which stays as issued) first
   takes the account's billing details as they are now: the way to fix a wrong name or address on one. What changed
   is in the activity note. */
export async function resendReceipt(number: string, actor: string) {
  let inv = await env.DB.prepare('SELECT * FROM invoices WHERE number = ?').bind(number).first<Invoice>();
  const o = inv ? await getOrder(inv.order_id) : null;
  if (!inv || !o) return { error: 'no_receipt' };
  const a = inv.account_id ? await getAccount(inv.account_id) : null;
  const changed: string[] = [];
  if (a) {
    const next = { ...inv, email: a.email };
    if (inv.doc === 'receipt') { next.buyer_name = a.bill_name || inv.buyer_name; next.buyer_address = a.bill_address || inv.buyer_address; }
    if (next.buyer_name !== inv.buyer_name) changed.push(`name ${inv.buyer_name} → ${next.buyer_name}`);
    if (next.buyer_address !== inv.buyer_address) changed.push('address');
    if (next.email !== inv.email) changed.push(`email ${inv.email} → ${next.email}`);
    if (changed.length) await env.DB.prepare('UPDATE invoices SET buyer_name = ?, buyer_address = ?, email = ? WHERE number = ?')
      .bind(next.buyer_name, next.buyer_address, next.email, inv.number).run();
    inv = next;
  }
  await sendInvoiceMail(inv, o, false);
  await env.DB.prepare('INSERT INTO events (at, actor, action, account_id, ref, note) VALUES (?, ?, ?, ?, ?, ?)')
    .bind(now(), actor, 'receipt.resent', inv.account_id, inv.number, `to ${inv.email}${changed.length ? ` · updated: ${changed.join('; ')}` : ''}`).run();
  return { ok: true, to: inv.email };
}
