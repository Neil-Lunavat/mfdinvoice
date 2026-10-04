/* Paying by UPI, checked by hand (until the company is registered and a card gateway can be used).
   1. Checkout: an order with a short reference (MFD-7K3Q9P) and a UPI QR that fills in the amount and the reference.
   2. The buyer pays, then sends the screenshot (and, if they like, the UTR): the order goes to 'review', the
      screenshot is kept in R2, and the owner gets an email with it attached.
   3. The owner approves (the plan starts that day, a receipt is emailed) or rejects (the buyer is emailed, with the
      reason only if the owner ticks it), in the admin panel's Payments.
   4. A rejected buyer can't pay by UPI again (the block follows the email too, so deleting the account doesn't lift
      it): Checkout sends them to support. The owner then either approves the rejected one after all (the money did
      arrive) or unblocks it: the same reference opens again at Checkout, and paying sends it back to be checked.
   So an account has at most one payment in the Payments list at a time.
   A payment started and left unfinished for a day gets one email (nudgeUnfinished, the hourly job). */
import { env } from 'cloudflare:workers';
import qrcode from 'qrcode-generator';
import { UPI, EMAIL } from '../../consts';
import { rupees, forWhat } from '../price';
import { paymentToCheckMail, paymentReceivedMail, rejectedMail, unblockedMail, unfinishedMail } from '../emails';
import { getOrder, completeOrder, type Order } from './orders';
import { getPlan, holdsPlan } from './account';
import { send, ATTACH_MAX } from './mail';
import { record } from './errors';
import { event } from './events';
import { now, ago, todayIST, istWhen, controlOrigin, siteOrigin, DAY } from './util';

/* MFD-7K3Q9P: easy to read out, no 0/O or 1/I */
const ALPHA = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ';
export function newRef() {
  const b = crypto.getRandomValues(new Uint8Array(6));
  return `${UPI.refPrefix}-${[...b].map(x => ALPHA[x % ALPHA.length]).join('')}`;
}

/* upi://pay with the amount and the reference in the note, as a QR (SVG). */
export function upiQr(ref: string, amount: number) {
  const uri = `upi://pay?pa=${UPI.id}&pn=${encodeURIComponent(UPI.name)}&am=${(amount / 100).toFixed(2)}&cu=INR&tn=${encodeURIComponent(ref)}`;
  const qr = qrcode(0, 'M');
  qr.addData(uri);
  qr.make();
  return { uri, svg: qr.createSvgTag({ cellSize: 4, margin: 0, scalable: true }) };
}

/* The buyer's latest UPI order that isn't finished: 'created' (QR shown) or 'review' (screenshot sent). */
export const openUpiOrder = (accountId: number) =>
  env.DB.prepare(`SELECT * FROM orders WHERE account_id = ? AND provider = 'upi' AND status IN ('created', 'review')
    ORDER BY created_at DESC LIMIT 1`).bind(accountId).first<Order>();

export const PROOF_TYPES: Record<string, string> = { 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp' };
export const PROOF_MAX = 8 * 1024 * 1024;

/* The screenshot arrives: keep it, mark the order for review, tell the owner. */
export async function submitProof(o: Order, file: File, utr: string | null) {
  const key = `proofs/${o.id}.${PROOF_TYPES[file.type]}`;
  const bytes = await file.arrayBuffer();
  await env.FILES.put(key, bytes, { httpMetadata: { contentType: file.type } });
  await env.DB.prepare(`UPDATE orders SET status = 'review', proof = ?, utr = ?, sent_at = ?, reviewed_at = NULL, review_note = NULL, note_shared = 0
    WHERE id = ? AND status IN ('created', 'review')`).bind(key, utr, now(), o.id).run();
  await event('buyer', 'payment.sent', o.account_id, o.id, utr ? `UTR ${utr}` : 'no UTR').run();

  const attached = bytes.byteLength <= ATTACH_MAX;
  /* to the owner's own inbox and to support@ */
  const mail = paymentToCheckMail({
    amount: rupees(o.total), forWhat: forWhat(o.kind, o.arns), ref: o.id, email: o.email, name: o.bill_name,
    utr: utr ?? 'not given', sent: istWhen(now()), link: `${controlOrigin()}/payments#${o.id}`, attached,
  });
  for (const to of [...new Set([UPI.notify, EMAIL.support])])
    await send(to, mail, { attachments: attached ? [{ content: bytes, filename: `${o.id}.${PROOF_TYPES[file.type]}`, type: file.type, disposition: 'attachment' }] : [] })
      .catch(e => record('email', `payment to check ${o.id} to ${to}`, e));
  /* the buyer's first email: received, being checked (the second comes with the approval) */
  await send(o.email, paymentReceivedMail({ amount: rupees(o.total), forWhat: forWhat(o.kind, o.arns), ref: o.id }))
    .catch(e => record('email', `payment received ${o.id}`, e));
}

/* The Payments page: those waiting for the owner (oldest first), then every rejected one (newest first).
   q: part of a reference, email, name or UTR. */
export function paymentsList(q = '') {
  const like = `%${q.toLowerCase()}%`;
  return env.DB.prepare(`SELECT o.*, (SELECT uid FROM accounts a WHERE a.id = o.account_id) AS uid FROM orders o
      WHERE provider = 'upi' AND status IN ('review', 'rejected')
      ${q ? 'AND (lower(id) LIKE ?1 OR lower(email) LIKE ?1 OR lower(bill_name) LIKE ?1 OR lower(utr) LIKE ?1)' : ''}
      ORDER BY status = 'rejected', CASE WHEN status = 'review' THEN sent_at END, reviewed_at DESC LIMIT 500`)
    .bind(...(q ? [like] : [])).all<Order & { uid: string | null }>().then(r => r.results);
}

/* A rejected payment for this account or this email: while there is one, they can't pay by UPI. */
export const rejectedBlock = (accountId: number, email: string) =>
  env.DB.prepare(`SELECT * FROM orders WHERE provider = 'upi' AND status = 'rejected' AND (account_id = ? OR email = ?)
    ORDER BY reviewed_at DESC LIMIT 1`).bind(accountId, email).first<Order>();

/* Approve: the plan starts today, the receipt is issued and emailed. The UTR (or the reference) is the payment id.
   A rejected payment can be approved too (the money did arrive after all). */
export async function approve(ref: string, actor: string) {
  const o = await getOrder(ref);
  if (!o || o.provider !== 'upi') return { error: 'no_order' };
  if (o.status === 'paid') return { error: 'already_paid' };
  if (o.status !== 'review' && o.status !== 'rejected') return { error: 'not_in_review', status: o.status };
  if (!o.account_id) return { error: 'no_account' };
  if (o.kind === 'new' && holdsPlan(await getPlan(o.account_id))) return { error: 'has_plan' };
  if (o.status === 'rejected') await env.DB.prepare(`UPDATE orders SET status = 'review' WHERE id = ? AND status = 'rejected'`).bind(o.id).run();
  const r = await completeOrder(o.id, o.utr || o.id, actor);
  return { ok: true, invoice: r?.invoice?.number ?? null };
}

/* Reject: nothing is applied and the account can't pay by UPI until unblocked. The buyer is emailed; the reason
   goes with it only if `tell`, otherwise it's the owner's own note. */
export async function reject(ref: string, note: string, tell: boolean, actor: string) {
  const o = await getOrder(ref);
  if (!o || o.provider !== 'upi') return { error: 'no_order' };
  if (o.status !== 'review') return { error: 'not_in_review', status: o.status };
  const [r] = await env.DB.batch([
    env.DB.prepare(`UPDATE orders SET status = 'rejected', reviewed_at = ?, review_note = ?, note_shared = ? WHERE id = ? AND status = 'review'`)
      .bind(now(), note || null, tell && note ? 1 : 0, o.id),
    event(actor, 'payment.rejected', o.account_id, o.id, note || null),
  ]);
  if (!r.meta.changes) return { error: 'not_in_review' };
  await send(o.email, rejectedMail({ amount: rupees(o.total), ref: o.id, note: tell && note ? note : null, link: `${siteOrigin()}/support?about=payment` })).catch(e => record('email', `rejected ${o.id}`, e));
  return { ok: true, replies_to: EMAIL.support };
}

/* Unblock: the same payment opens again at Checkout (no new reference); sending a screenshot puts it back in the list.
   What happened stays in the account's activity. */
export async function unblock(ref: string, actor: string, tell = false) {
  const o = await getOrder(ref);
  if (!o || o.provider !== 'upi') return { error: 'no_order' };
  const [r] = await env.DB.batch([
    env.DB.prepare(`UPDATE orders SET status = 'created', unblocked_at = ? WHERE id = ? AND status = 'rejected'`).bind(now(), o.id),
    env.DB.prepare(`INSERT INTO events (at, actor, action, account_id, ref) SELECT ?, ?, 'payment.unblocked', ?, ? WHERE changes() > 0`).bind(now(), actor, o.account_id, o.id),
  ]);
  if (!r.meta.changes) return { error: 'not_blocked' };
  if (tell) await send(o.email, unblockedMail({ link: `${siteOrigin()}/checkout` })).catch(e => record('email', `unblocked ${o.id}`, e));
  return { ok: true };
}

/* The hourly job: a payment started at Checkout (the QR shown) and not finished a day later gets one email, once per
   account: the activity log is what remembers that it went. Not while another payment of theirs is being checked or
   is blocked, and not once a bought or gifted plan is running. With several unfinished, the newest is the one logged
   (SQLite takes the other columns from the MAX row). */
export async function nudgeUnfinished() {
  const due = (await env.DB.prepare(`SELECT o.id, o.account_id, a.email, MAX(o.created_at) FROM orders o JOIN accounts a ON a.id = o.account_id
      WHERE o.provider = 'upi' AND o.status = 'created' AND COALESCE(o.unblocked_at, o.created_at) <= ?1 AND a.delete_after IS NULL
        AND NOT EXISTS (SELECT 1 FROM orders x WHERE x.account_id = o.account_id AND x.status IN ('review', 'rejected'))
        AND NOT EXISTS (SELECT 1 FROM plans p WHERE p.account_id = o.account_id AND p.source != 'trial' AND p.ends_on >= ?2)
        AND NOT EXISTS (SELECT 1 FROM events e WHERE e.account_id = o.account_id AND e.action = 'payment.nudged')
      GROUP BY o.account_id LIMIT 50`).bind(ago(DAY), todayIST()).all<{ id: string; account_id: number; email: string }>()).results;
  let sent = 0;
  for (const o of due) {
    try {
      await send(o.email, unfinishedMail({ link: `${siteOrigin()}/checkout` }));
      await event('system', 'payment.nudged', o.account_id, o.id).run();
      sent++;
    } catch (e) { await record('email', `unfinished ${o.id}`, e); }
  }
  return sent;
}
