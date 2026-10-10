/* What the admin panel reads, and the gate on its API routes. Every change it makes goes through the lib/server
   function that owns it (upi.ts, account.ts, gifts.ts, support.ts, orders.ts), with the admin's email as the actor. */
import { env } from 'cloudflare:workers';
import { accessUser, type App, type Person } from './access';
import { route, checkOrigin, fail, HttpError } from './http';
import { todayIST, fy } from './util';
import type { Order, Invoice } from './orders';
import type { Plan } from './account';
import type { Request as SupportRequest } from './support';

/* An API route on the panel's (or the editor's) host: a valid Access JWT for that app, and a same-origin POST. */
export const gated = (app: App, fn: (req: Request, url: URL, me: Person) => Promise<Response>) =>
  route(async (req, url) => {
    const me = await accessUser(req, app);
    if (!me) throw new HttpError(fail(403, 'forbidden'));
    if (req.method !== 'GET') checkOrigin(req);
    return fn(req, url, me);
  });

const one = <T>(sql: string, ...b: unknown[]) => env.DB.prepare(sql).bind(...b).first<T>();
const all = <T>(sql: string, ...b: unknown[]) => env.DB.prepare(sql).bind(...b).all<T>().then(r => r.results);
/* an order's day and month in India */
const IST = `'+330 minutes'`;

export async function overview() {
  const today = todayIST(), month = today.slice(0, 7);
  const fyStart = `20${fy(today).slice(0, 2)}-04-01`;
  const plus = (n: number) => new Date(Date.parse(today) + n * 864e5).toISOString().slice(0, 10);
  const [pay, open, m, y, accounts, plans, gifts, del, signups, trialsEnding, plansEnding] = await Promise.all([
    one<{ n: number }>(`SELECT COUNT(*) AS n FROM orders WHERE provider = 'upi' AND status = 'review'`),
    one<{ n: number }>(`SELECT COUNT(*) AS n FROM requests WHERE status = 'open' AND topic != 'data'`),
    one<{ n: number; t: number }>(`SELECT COUNT(*) AS n, COALESCE(SUM(total), 0) AS t FROM orders WHERE status = 'paid' AND strftime('%Y-%m', paid_at, ${IST}) = ?`, month),
    one<{ n: number; t: number }>(`SELECT COUNT(*) AS n, COALESCE(SUM(total), 0) AS t FROM orders WHERE status = 'paid' AND date(paid_at, ${IST}) >= ?`, fyStart),
    one<{ n: number }>('SELECT COUNT(*) AS n FROM accounts'),
    one<{ paid: number; gift: number; trial: number }>(`SELECT COALESCE(SUM(source = 'paid'), 0) AS paid, COALESCE(SUM(source = 'grant'), 0) AS gift,
      COALESCE(SUM(source = 'trial'), 0) AS trial FROM plans WHERE ends_on >= ?`, today),
    one<{ n: number }>('SELECT COUNT(*) AS n FROM gifts WHERE used_at IS NULL AND revoked_at IS NULL'),
    one<{ n: number; next: string | null }>('SELECT COUNT(*) AS n, MIN(delete_after) AS next FROM accounts WHERE delete_after IS NOT NULL'),
    one<{ n: number }>(`SELECT COUNT(*) AS n FROM accounts WHERE date(created_at, ${IST}) >= ?`, plus(-6)),
    one<{ n: number }>(`SELECT COUNT(*) AS n FROM plans WHERE source = 'trial' AND ends_on BETWEEN ? AND ?`, today, plus(7)),
    one<{ n: number }>(`SELECT COUNT(*) AS n FROM plans WHERE source != 'trial' AND ends_on BETWEEN ? AND ?`, today, plus(30)),
  ]);
  return { payments: pay!.n, requests: open!.n, month: m!, year: y!, accounts: accounts!.n, plans: plans!, gifts: gifts!.n, deletions: del!.n, nextDeletion: del!.next,
    signups: signups!.n, trialsEnding: trialsEnding!.n, plansEnding: plansEnding!.n };
}

/* ARNs that came back on another free trial (a trial is once per email, not per ARN, on purpose): how many ARNs, the
   trials beyond each one's first, and the newest 50 with their emails. Read-only, from `trials`. */
export async function backOnTrial() {
  const [tot, list] = await Promise.all([
    one<{ arns: number; extra: number }>(`SELECT COUNT(*) AS arns, COALESCE(SUM(n - 1), 0) AS extra FROM (SELECT COUNT(*) AS n FROM trials GROUP BY arn HAVING COUNT(*) > 1)`),
    env.DB.prepare(`SELECT arn, COUNT(*) AS trials, group_concat(email, ', ') AS emails, MAX(started_at) AS last FROM trials GROUP BY arn HAVING COUNT(*) > 1 ORDER BY last DESC LIMIT 50`)
      .all<{ arn: string; trials: number; emails: string; last: string }>(),
  ]);
  return { arns: tot!.arns, extra: tot!.extra, rows: list.results };
}

/* The numbers on the tabs. */
export const tabCounts = async () => {
  const r = await one<{ p: number; s: number }>(`SELECT (SELECT COUNT(*) FROM orders WHERE provider = 'upi' AND status = 'review') AS p,
    (SELECT COUNT(*) FROM requests WHERE status = 'open' AND topic != 'data') AS s`);
  return { '/payments': r!.p, '/support': r!.s };
};

/* The colour of a plan's tag in the panel, by its source. */
export const PLAN_TAG: Record<Plan['source'], string> = { paid: 'green', grant: 'blue', trial: 'amber' };

export type AccountRow = { id: number; uid: string; email: string; bill_name: string | null; created_at: string; delete_after: string | null;
  ends_on: string | null; source: Plan['source'] | null; slots: number | null; arns: string | null };

/* Search by email, name, ARN or payment reference (or UTR); `f`: active (a paid or gifted plan running), gift, trial
   (one running), none, deleting. */
export async function searchAccounts(q: string, f: string) {
  const like = `%${q.toLowerCase()}%`, arn = q.replace(/^\s*arn[-\s]?/i, '').trim(), today = todayIST();
  const where: string[] = [], bind: unknown[] = [];
  if (q) {
    where.push(`(lower(a.email) LIKE ? OR lower(a.bill_name) LIKE ? OR a.id IN (SELECT account_id FROM arns WHERE arn = ?)
      OR a.id IN (SELECT account_id FROM orders WHERE upper(id) = upper(?) OR utr = upper(?)))`);
    bind.push(like, like, arn, q.trim(), q.trim());
  }
  if (f === 'active') { where.push(`p.ends_on >= ? AND p.source != 'trial'`); bind.push(today); }
  if (f === 'gift') { where.push(`p.ends_on >= ? AND p.source = 'grant'`); bind.push(today); }
  if (f === 'trial') { where.push(`p.ends_on >= ? AND p.source = 'trial'`); bind.push(today); }
  if (f === 'none') { where.push('(p.ends_on IS NULL OR p.ends_on < ?)'); bind.push(today); }
  if (f === 'deleting') where.push('a.delete_after IS NOT NULL');
  return all<AccountRow>(`SELECT a.id, a.uid, a.email, a.bill_name, a.created_at, a.delete_after, p.ends_on, p.source, p.slots,
      (SELECT group_concat(arn, ', ') FROM arns WHERE account_id = a.id) AS arns
    FROM accounts a LEFT JOIN plans p ON p.account_id = a.id ${where.length ? 'WHERE ' + where.join(' AND ') : ''}
    ORDER BY a.created_at DESC LIMIT 100`, ...bind);
}

/* One account, by its uid (the panel's links). */
export async function accountDetail(uid: string) {
  const a = await one<{ id: number; uid: string; email: string; created_at: string; bill_name: string | null; bill_gstin: string | null; bill_address: string | null; phone: string | null; delete_after: string | null }>(
    'SELECT * FROM accounts WHERE uid = ?', uid);
  if (!a) return null;
  const id = a.id;
  const [orders, invoices, requests] = await Promise.all([
    all<Order>('SELECT * FROM orders WHERE account_id = ? ORDER BY created_at DESC', id),
    all<Invoice>('SELECT * FROM invoices WHERE account_id = ? ORDER BY issued_at DESC', id),
    all<SupportRequest>('SELECT * FROM requests WHERE account_id = ? ORDER BY created_at DESC', id),
  ]);
  return { a, orders, invoices, requests };
}

/* Support requests, open first, newest first, with the account's plan and ARNs (for the request's popup).
   q: part of the number, email, message, ARN or new email. */
export type SupportRow = SupportRequest & { uid: string | null; ends_on: string | null; slots: number | null; source: Plan['source'] | null; arns: string | null;
  freed: number; freed_last: string | null };
export function supportList(q = '') {
  const like = `%${q.toLowerCase()}%`;
  return all<SupportRow>(`SELECT r.*, a.uid, p.ends_on, p.slots, p.source, (SELECT group_concat(arn, ', ') FROM arns WHERE account_id = r.account_id) AS arns,
      (SELECT COUNT(*) FROM events WHERE account_id = r.account_id AND action = 'arn.freed') AS freed,
      (SELECT MAX(at) FROM events WHERE account_id = r.account_id AND action = 'arn.freed') AS freed_last
    FROM requests r LEFT JOIN accounts a ON a.id = r.account_id LEFT JOIN plans p ON p.account_id = r.account_id
    ${q ? `WHERE (CAST(r.id AS TEXT) LIKE ?1 OR lower(r.email) LIKE ?1 OR lower(r.message) LIKE ?1 OR r.arn LIKE ?1 OR lower(r.new_email) LIKE ?1)` : ''}
    ORDER BY r.status = 'solved', r.created_at DESC LIMIT 500`, ...(q ? [like] : []));
}

/* Sales: paid orders only (gifts are never sales), newest first, with the receipt, and who approved it.
   Filters: q (reference, email, name, UTR or receipt number), from/to (India days it was paid), kind ('new' or 'add'). */
export type SaleRow = Order & { number: string | null; uid: string | null; approver: string | null };
export function salesList(f: { q?: string; from?: string; to?: string; kind?: string }) {
  const where = [`o.status = 'paid'`], bind: unknown[] = [];
  if (f.q) {
    const like = `%${f.q.toLowerCase()}%`;
    where.push('(lower(o.id) LIKE ? OR lower(o.email) LIKE ? OR lower(o.bill_name) LIKE ? OR lower(o.utr) LIKE ? OR lower(i.number) LIKE ?)');
    bind.push(like, like, like, like, like);
  }
  if (f.from) { where.push(`date(o.paid_at, ${IST}) >= ?`); bind.push(f.from); }
  if (f.to) { where.push(`date(o.paid_at, ${IST}) <= ?`); bind.push(f.to); }
  if (f.kind === 'new' || f.kind === 'add') { where.push('o.kind = ?'); bind.push(f.kind); }
  return all<SaleRow>(`SELECT o.*, i.number, (SELECT uid FROM accounts a WHERE a.id = o.account_id) AS uid,
      (SELECT actor FROM events e WHERE e.action = 'payment.approved' AND e.ref = o.id LIMIT 1) AS approver
    FROM orders o LEFT JOIN invoices i ON i.order_id = o.id WHERE ${where.join(' AND ')} ORDER BY o.paid_at DESC LIMIT 1000`, ...bind);
}

/* The CSV the partner files GST from: one row per receipt/invoice issued between two days (in India), inclusive. */
export async function salesCsv(from: string, to: string) {
  const rows = await all<Invoice & { utr: string | null }>(`SELECT i.*, o.utr FROM invoices i JOIN orders o ON o.id = i.order_id
    WHERE date(i.issued_at, ${IST}) BETWEEN ? AND ? ORDER BY i.issued_at`, from, to);
  const cell = (v: unknown) => { const s = v == null ? '' : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  const r2 = (p: number) => (p / 100).toFixed(2);
  const head = ['Number', 'Date', 'Type', 'Buyer', 'Buyer GSTIN', 'State', 'Amount', 'CGST', 'SGST', 'IGST', 'Total', 'Payment reference', 'UTR', 'Email'];
  const lines = rows.map(i => [
    i.number, new Date(Date.parse(i.issued_at) + 19_800_000).toISOString().slice(0, 10), i.doc === 'tax' ? 'Tax invoice' : 'Receipt',
    i.buyer_name, i.buyer_gstin ?? '', i.buyer_state ?? '', r2(i.subtotal), r2(i.cgst), r2(i.sgst), r2(i.igst), r2(i.total), i.order_id, i.utr ?? '', i.email,
  ].map(cell).join(','));
  return [head.join(','), ...lines].join('\r\n') + '\r\n';
}
