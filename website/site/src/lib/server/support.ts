/* Support requests. A signed-in account sends one from /support: it's saved (a random 6-digit number, Open) with up to three
   screenshots in R2, and emailed to support@ with reply-to set to the person, so the conversation happens by email.
   The topics the owner can fix from his phone also go to his own inbox. "A copy of my data" emails nobody: the
   hourly job sends the account its data 2 to 8 hours later and marks the request solved. */
import { env } from 'cloudflare:workers';
import { EMAIL, OWNER_EMAIL, SALES } from '../../consts';
import { TOPICS, SHOT_TYPES } from '../support';
import { QUESTIONS, answerLabel } from '../survey';
import { answersFor } from './survey';
import { supportMail, dataCopyMail, supportReceivedMail } from '../emails';
import { rupees, forWhat } from '../price';
import { longDate } from '../invoice';
import { send, ATTACH_MAX, type Attachment } from './mail';
import { record } from './errors';
import { event } from './events';
import { getAccount, getPlan, getArns, planLine, PLAN_NAME } from './account';
import { hit } from './auth';
import { now, later, HOUR, token, sixDigits, istWhen, istDay, controlOrigin } from './util';

export type Request = {
  id: number; account_id: number | null; email: string; topic: string; arn: string | null; new_email: string | null; message: string | null;
  files: string; status: 'open' | 'solved'; created_at: string; due_at: string | null; solved_at: string | null; solved_by: string | null;
};

const PER_HOUR = 5;

export async function submitRequest(s: { account_id: number; email: string }, f: { topic: string; arn: string | null; newEmail: string | null; message: string | null; shots: File[] }) {
  await hit(`support:${s.account_id}`, PER_HOUR);
  const t = TOPICS[f.topic];
  const keys: string[] = [], files: { key: string; bytes: ArrayBuffer; type: string }[] = [];
  for (const shot of f.shots) {
    const key = `support/${token().slice(0, 16)}.${SHOT_TYPES[shot.type]}`;
    const bytes = await shot.arrayBuffer();
    await env.FILES.put(key, bytes, { httpMetadata: { contentType: shot.type } });
    keys.push(key); files.push({ key, bytes, type: shot.type });
  }
  /* a data copy goes out at a random time 2 to 8 hours from now */
  const due = f.topic === 'data' ? later(2 * HOUR + Math.floor(Math.random() * 6 * HOUR)) : null;
  /* a random 6-digit number, tried again in the rare case it's taken */
  let r: { id: number } | null = null;
  while (!r) r = await env.DB.prepare(`INSERT INTO requests (id, account_id, email, topic, arn, new_email, message, files, created_at, due_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (id) DO NOTHING RETURNING id`)
    .bind(100000 + Number(sixDigits()) % 900000, s.account_id, s.email, f.topic, f.arn, f.newEmail, f.message, JSON.stringify(keys), now(), due).first<{ id: number }>();
  if (f.topic === 'data') return { id: r.id };

  const plan = await getPlan(s.account_id);
  const attachments: Attachment[] = [];
  let size = 0;
  for (const [i, x] of files.entries()) {
    if (size + x.bytes.byteLength > ATTACH_MAX) continue;
    size += x.bytes.byteLength;
    attachments.push({ content: x.bytes, filename: `${r.id}-${i + 1}.${SHOT_TYPES[x.type]}`, type: x.type, disposition: 'attachment' });
  }
  const mail = supportMail({
    number: String(r.id), topic: t.label, email: s.email, arn: f.arn ? `ARN-${f.arn}` : null, newEmail: f.newEmail,
    plan: planLine(plan),
    message: f.message,
    files: !files.length ? 'No screenshots.' : attachments.length === files.length ? `${files.length} screenshot${files.length > 1 ? 's' : ''} attached.`
      : `${attachments.length} of ${files.length} screenshots attached; the rest are too big for email and are in the panel.`,
    link: `${controlOrigin()}/support?q=${r.id}`,
  });
  await event('buyer', 'request.sent', s.account_id, `#${r.id}`, t.label).run();
  const to = [EMAIL.support, ...(t.owner ? [OWNER_EMAIL] : [])];
  for (const addr of to) await send(addr, mail, { replyTo: s.email, attachments }).catch(e => record('email', `support #${r.id} to ${addr}`, e));
  /* their own copy: it reached us */
  await send(s.email, supportReceivedMail({ number: String(r.id), topic: t.label })).catch(e => record('email', `support #${r.id} received`, e));
  return { id: r.id };
}

/* The panel's status dropdown. Solving and reopening are logged. */
export async function setRequestStatus(id: number, status: 'open' | 'solved', actor: string) {
  const req = await env.DB.prepare('SELECT account_id FROM requests WHERE id = ?').bind(id).first<{ account_id: number | null }>();
  if (!req) return { error: 'no_request' };
  const stmts = [
    status === 'solved'
      ? env.DB.prepare(`UPDATE requests SET status = 'solved', solved_at = ?, solved_by = ? WHERE id = ? AND status = 'open'`).bind(now(), actor, id)
      : env.DB.prepare(`UPDATE requests SET status = 'open', solved_at = NULL, solved_by = NULL WHERE id = ? AND status = 'solved'`).bind(id),
    env.DB.prepare(`INSERT INTO events (at, actor, action, account_id, ref) SELECT ?, ?, ?, ?, ? WHERE changes() > 0`)
      .bind(now(), actor, status === 'solved' ? 'request.solved' : 'request.reopened', req.account_id, `#${id}`),
  ];
  await env.DB.batch(stmts);
  return { ok: true };
}

/* ---- the data copy ---- */

/* Everything the website stores about an account. */
export async function accountData(accountId: number) {
  const a = (await getAccount(accountId))!;
  const all = <T>(sql: string, ...b: unknown[]) => env.DB.prepare(sql).bind(...b).all<T>().then(r => r.results);
  const [plan, arns, orders, receipts, gifts, requests, codes, sessions, answers] = await Promise.all([
    getPlan(accountId), getArns(accountId),
    all<any>(`SELECT id, provider, kind, arns, months, total, status, utr, proof, terms, created_at, paid_at,
      CASE WHEN note_shared = 1 THEN review_note END AS review_note FROM orders WHERE account_id = ? ORDER BY created_at`, accountId),
    all<any>('SELECT number, doc, issued_at, buyer_name, buyer_gstin, buyer_address, total FROM invoices WHERE account_id = ? ORDER BY issued_at', accountId),
    all<any>('SELECT id, email, arns, years, given_at, used_at, revoked_at FROM gifts WHERE account_id = ? OR email = ? ORDER BY given_at', accountId, a.email),
    all<any>('SELECT id, topic, arn, new_email, message, files, status, created_at, solved_at FROM requests WHERE account_id = ? ORDER BY created_at', accountId),
    all<any>('SELECT created_at, ip FROM codes WHERE email = ? ORDER BY created_at', a.email),
    all<any>('SELECT kind, created_at, last_seen, expires_at FROM sessions WHERE account_id = ? ORDER BY created_at', accountId),
    answersFor(accountId),
  ]);
  return {
    account: { id: a.uid, email: a.email, created_at: a.created_at },
    billing: { name: a.bill_name, ...(SALES.gst ? { gstin: a.bill_gstin } : {}), address: a.bill_address, phone: a.phone },
    plan, arns, orders, receipts, gifts,
    support_requests: requests.map((r: any) => ({ ...r, number: r.id, files: JSON.parse(r.files) })),
    sign_in: { codes_requested: codes, sessions },
    survey_answers: answers,
  };
}

const d = (iso: string | null) => (iso ? istWhen(iso) : '—');

/* The hourly job: every data copy that's due. Returns how many went out. */
export async function sendDueDataCopies() {
  const due = (await env.DB.prepare(`SELECT * FROM requests WHERE topic = 'data' AND status = 'open' AND due_at <= ? ORDER BY due_at LIMIT 20`)
    .bind(now()).all<Request>()).results;
  let sent = 0;
  for (const r of due) {
    try {
      if (!r.account_id) continue;
      const data = await accountData(r.account_id);
      const mail = dataCopyMail({
        asked: longDate(istDay(r.created_at)),
        sections: [
          { title: 'Account', rows: [['Email', data.account.email], ['Account ID', data.account.id], ['Created', d(data.account.created_at)]] },
          { title: 'Billing details', rows: [['Name', data.billing.name ?? '—'], ...(SALES.gst ? [['GSTIN', (data.billing as any).gstin ?? '—'] as [string, string]] : []), ['Address', data.billing.address ?? '—'], ...(data.billing.phone ? [['Mobile', data.billing.phone] as [string, string]] : [])] },
          { title: 'Plan', rows: data.plan ? [['Plan', PLAN_NAME[data.plan.source]], ['From', longDate(data.plan.starts_on)], ['Until', longDate(data.plan.ends_on)], ['ARN slots', String(data.plan.slots)]] : [], empty: 'No plan.' },
          { title: 'ARNs', rows: data.arns.map(x => [`ARN-${x.arn}`, x.holder] as [string, string]), empty: 'No ARNs.' },
          { title: 'Orders', rows: data.orders.map((o: any) => [o.id, `${forWhat(o.kind, o.arns)} · ${rupees(o.total)} · ${o.status}${o.utr ? ` · UTR ${o.utr}` : ''}${o.proof ? ` · screenshot ${o.proof}` : ''}${o.terms ? ` · Terms of ${longDate(o.terms)}` : ''} · ${d(o.created_at)}`] as [string, string]), empty: 'No orders.' },
          { title: SALES.gst ? 'Invoices and receipts' : 'Receipts', rows: data.receipts.map((x: any) => [x.number, `${rupees(x.total)} · ${d(x.issued_at)}`] as [string, string]), empty: 'None.' },
          { title: 'Gifts', rows: data.gifts.map((g: any) => [`Gift ${g.id}`, `Given ${d(g.given_at)}${g.used_at ? `, started ${d(g.used_at)}` : g.revoked_at ? ', revoked' : ', not used yet'}`] as [string, string]), empty: 'No gifts.' },
          { title: 'Support requests', rows: data.support_requests.map((x: any) => [`#${x.id}`, `${TOPICS[x.topic]?.label ?? x.topic} · ${x.status} · ${d(x.created_at)}`] as [string, string]), empty: 'None.' },
          { title: 'Sign-in codes requested (the last day)', rows: data.sign_in.codes_requested.map((c: any) => [d(c.created_at), `from IP ${c.ip ?? '—'}`] as [string, string]), empty: 'None in the last day.' },
          { title: 'Your answers to our questions', rows: data.survey_answers.map(x => [QUESTIONS.find(q => q.key === x.question)?.q ?? 'Other (your words)', answerLabel(x.question, x.answer)] as [string, string]), empty: 'None.' },
          { title: 'Signed-in sessions', rows: data.sign_in.sessions.map((x: any) => [x.kind === 'app' ? 'The app' : 'The website', `started ${d(x.created_at)}, last seen ${d(x.last_seen)}`] as [string, string]), empty: 'None.' },
        ],
      });
      await send(r.email, mail, { attachments: [{ content: JSON.stringify(data, null, 2), filename: `${data.account.email.split('@')[0]}-data.json`, type: 'application/json', disposition: 'attachment' }] });
      await env.DB.batch([
        env.DB.prepare(`UPDATE requests SET status = 'solved', solved_at = ?, solved_by = 'system' WHERE id = ?`).bind(now(), r.id),
        event('system', 'data.sent', r.account_id, `#${r.id}`, r.email),
      ]);
      sent++;
    } catch (e) { await record('email', `data copy #${r.id}`, e); }
  }
  return sent;
}
