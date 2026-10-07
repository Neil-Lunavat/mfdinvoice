/* An account as the Account page, the app, the app's server and the admin panel see it, and every change to one. */
import { env } from 'cloudflare:workers';
import { SALES } from '../../consts';
import { deletionMail, emailChangedOldMail, emailChangedNewMail, arnFreedMail } from '../emails';
import { longDate } from '../date';
import { now, later, todayIST, DAY, istWhen, siteOrigin } from './util';
import { str } from './http';
import { gstinOk } from '../gstin';
import { send } from './mail';
import { event } from './events';
import { record } from './errors';

/* source: how the plan came to be. 'paid' (a purchase), 'grant' (a gift) or 'trial' (the free trial, trial.ts). */
export type Plan = { slots: number; starts_on: string; ends_on: string; source: 'paid' | 'grant' | 'trial' };
export const PLAN_NAME: Record<Plan['source'], string> = { paid: 'Paid', grant: 'Gift', trial: 'Trial' };
export type Arn = { arn: string; holder: string };
export type Account = { id: number; uid: string; email: string; created_at: string; bill_name: string | null; bill_gstin: string | null; bill_address: string | null; phone: string | null; delete_after: string | null };

export const getAccount = (id: number) =>
  env.DB.prepare('SELECT id, uid, email, created_at, bill_name, bill_gstin, bill_address, phone, delete_after FROM accounts WHERE id = ?').bind(id).first<Account>();
export const getPlan = (id: number) =>
  env.DB.prepare('SELECT slots, starts_on, ends_on, source FROM plans WHERE account_id = ?').bind(id).first<Plan>();
export const getArns = (id: number) =>
  env.DB.prepare('SELECT arn, holder FROM arns WHERE account_id = ? ORDER BY rowid').bind(id).all<Arn>().then(r => r.results);

/* A plan runs through its last day, in India. */
export const isActive = (p: Pick<Plan, 'ends_on'> | null) => !!p && todayIST() <= p.ends_on;
/* A trial that is still running. It is bought like a first plan, and the year then starts when the trial ends. */
export const onTrial = (p: Plan | null) => isActive(p) && p!.source === 'trial';
/* A bought or gifted plan that is still running: nothing new to buy (but more ARNs) until it ends. */
export const holdsPlan = (p: Plan | null) => isActive(p) && p!.source !== 'trial';
/* The day a plan bought (or gifted) today starts from: the trial's last day while one is running, otherwise today. */
export const yearFrom = (p: Plan | null) => (onTrial(p) ? p!.ends_on : todayIST());

/* "Paid, until 1 October 2027, 1 ARN slot": a plan in one line, for the owner (support emails, the panel). */
export const planLine = (p: Pick<Plan, 'source' | 'ends_on' | 'slots'> | null) => !p ? 'No plan'
  : `${PLAN_NAME[p.source]}, ${isActive(p) ? 'until' : 'ended'} ${longDate(p.ends_on)}, ${p.slots} ARN slot${p.slots === 1 ? '' : 's'}`;

/* This account's email has had its free trial, here or on an account deleted before (`trials` is kept for good):
   one free trial per email. */
export const trialUsed = (id: number) =>
  env.DB.prepare('SELECT EXISTS (SELECT 1 FROM trials t JOIN accounts a ON a.email = t.email WHERE a.id = ?) AS u')
    .bind(id).first<{ u: number }>().then(r => !!r?.u);
/* Has had a plan, a free trial included (the site's main button then says Buy now): a plan on this account, or a
   trial this email had before. */
export const hadPlan = async (id: number, plan: Plan | null) => !!plan || (await trialUsed(id));

/* The licence: what the app and the app's server need. trial_used: this email has had its free trial, so binding a
   first ARN won't start one (the app says to buy a plan). */
export async function licence(id: number) {
  const [plan, arns, used] = await Promise.all([getPlan(id), getArns(id), trialUsed(id)]);
  return {
    active: isActive(plan),
    paid_until: plan?.ends_on ?? null,
    source: plan?.source ?? null,
    slots: plan?.slots ?? 0,
    arns: arns.map(a => ({ arn: a.arn, holder: a.holder })),
    trial_used: used,
  };
}

/* ---- deleting: "Delete my account" waits a day ---- */

/* Sets delete_after to a day from now and ends every session (web and app). Nothing is removed yet; signing in
   before then offers to keep the account. The daily job deletes it (jobs.ts). */
export async function scheduleDeletion(id: number, email: string) {
  const when = later(DAY);
  const [r] = await env.DB.batch([
    env.DB.prepare('UPDATE accounts SET delete_after = ? WHERE id = ? AND delete_after IS NULL').bind(when, id),
    env.DB.prepare('DELETE FROM sessions WHERE account_id = ?').bind(id),
    event('buyer', 'deletion.scheduled', id, null, `Deletes after ${istWhen(when)}`),
  ]);
  if (!r.meta.changes) return;
  try { await send(email, deletionMail({ when: istWhen(when), link: `${siteOrigin()}/signin?next=/account` })); }
  catch (e) { await record('email', 'scheduleDeletion', e); }
}

/* "Keep my account" (the buyer, signing in during the day) or the admin panel. */
export async function cancelDeletion(id: number, actor: string) {
  const [r] = await env.DB.batch([
    env.DB.prepare('UPDATE accounts SET delete_after = NULL WHERE id = ? AND delete_after IS NOT NULL').bind(id),
    env.DB.prepare(`INSERT INTO events (at, actor, action, account_id) SELECT ?, ?, 'deletion.cancelled', ? WHERE changes() > 0`).bind(now(), actor, id),
  ]);
  return !!r.meta.changes;
}

/* The real deletion (the daily job, once delete_after has passed, or the admin panel at once): the account, its
   sessions, plan, slots, billing details, support requests (and their screenshots) and activity go, and its ARNs are
   freed. Orders, receipts and gifts stay, without the account link. `deletions` keeps the email (so signing in again
   says the account was deleted) and who did it.
   by: 'buyer' (their own request) or the admin's email. */
export async function deleteAccount(id: number, email: string, at: string, by = 'buyer') {
  const files = (await env.DB.prepare('SELECT files FROM requests WHERE account_id = ?').bind(id).all<{ files: string }>()).results
    .flatMap(r => JSON.parse(r.files) as string[]);
  await env.DB.batch([
    env.DB.prepare('INSERT INTO deletions (account_id, deleted_at, email, deleted_by) VALUES (?, ?, ?, ?)').bind(id, at, email, by),
    env.DB.prepare('UPDATE orders SET account_id = NULL WHERE account_id = ?').bind(id),
    env.DB.prepare('UPDATE invoices SET account_id = NULL WHERE account_id = ?').bind(id),
    env.DB.prepare('UPDATE gifts SET account_id = NULL WHERE account_id = ?').bind(id),
    env.DB.prepare('DELETE FROM sessions WHERE account_id = ?').bind(id),
    env.DB.prepare('DELETE FROM arns WHERE account_id = ?').bind(id),
    env.DB.prepare('DELETE FROM plans WHERE account_id = ?').bind(id),
    env.DB.prepare('DELETE FROM requests WHERE account_id = ?').bind(id),
    env.DB.prepare('DELETE FROM codes WHERE email = ?').bind(email),
    env.DB.prepare('DELETE FROM events WHERE account_id = ?').bind(id),
    env.DB.prepare('DELETE FROM answers WHERE account_id = ?').bind(id),
    env.DB.prepare('DELETE FROM survey_replies WHERE account_id = ?').bind(id),
    env.DB.prepare('DELETE FROM accounts WHERE id = ?').bind(id),
    event(by === 'buyer' ? 'system' : by, 'deletion.done', id),
  ]);
  if (files.length) await env.FILES.delete(files).catch(e => record('r2', 'deleteAccount', e));
}

/* ---- the admin panel's fixes ---- */

/* Frees an ARN's slot. The only change the panel makes to ARNs: a new one comes in through the app's own setup
   (checked against its CAMS mailbox), never typed here. Each freeing is in the account's activity, so a plan that
   keeps moving between ARNs shows. */
export async function freeArn(accountId: number, arn: string, actor: string, tell = false) {
  const [r] = await env.DB.batch([
    env.DB.prepare('DELETE FROM arns WHERE arn = ? AND account_id = ?').bind(arn, accountId),
    env.DB.prepare(`INSERT INTO events (at, actor, action, account_id, ref) SELECT ?, ?, 'arn.freed', ?, ? WHERE changes() > 0`).bind(now(), actor, accountId, arn),
  ]);
  if (!r.meta.changes) return { error: 'no_arn' };
  const a = tell ? await getAccount(accountId) : null;
  if (a) await send(a.email, arnFreedMail({ arn: `ARN-${arn}` })).catch(e => record('email', `arn freed ${arn}`, e));
  return { ok: true };
}

/* Moves the account to a new email. Refused if another account has it. Every session ends; both addresses are told. */
export async function changeEmail(accountId: number, to: string, actor: string) {
  const a = await getAccount(accountId);
  if (!a) return { error: 'no_account' };
  if (a.email === to) return { error: 'same_email' };
  if (await env.DB.prepare('SELECT 1 FROM accounts WHERE email = ?').bind(to).first()) return { error: 'email_taken' };
  try {
    await env.DB.batch([
      env.DB.prepare('UPDATE accounts SET email = ? WHERE id = ?').bind(to, accountId),
      env.DB.prepare('DELETE FROM sessions WHERE account_id = ?').bind(accountId),
      env.DB.prepare('DELETE FROM codes WHERE email = ?').bind(a.email),
      event(actor, 'email.changed', accountId, null, `${a.email} → ${to}`),
    ]);
  } catch (e) {
    /* the UNIQUE email: someone signed up with it a moment ago */
    if (/UNIQUE/i.test(String(e))) return { error: 'email_taken' };
    throw e;
  }
  const sign = `${siteOrigin()}/signin?next=/account`;
  await Promise.all([
    send(a.email, emailChangedOldMail({ newEmail: to })).catch(e => record('email', 'changeEmail (old)', e)),
    send(to, emailChangedNewMail({ oldEmail: a.email, link: sign })).catch(e => record('email', 'changeEmail (new)', e)),
  ]);
  return { ok: true };
}

/* ---- billing details ---- */

/* From a form: a name and an address; and, while SALES.gst is on, a GSTIN that passes its checksum (off: no GSTIN
   is asked for or kept). Returns { error } or the cleaned details. */
export function billing(b: Record<string, unknown>): { error: string } | { name: string; gstin: string | null; address: string } {
  const name = str(b.name, 200), address = str(b.address, 500);
  const gstin = SALES.gst ? str(b.gstin, 15).toUpperCase() : null;
  if (SALES.gst && !gstinOk(gstin!)) return { error: 'bad_gstin' };
  if (!name) return { error: 'no_name' };
  if (!address) return { error: 'no_address' };
  return { name, gstin, address };
}

/* Saves the billing details (Account, or Checkout). A change is in the account's activity ("Billing details changed"),
   so the owner knows a receipt resent now carries the new ones. */
export async function saveBilling(accountId: number, bill: { name: string; gstin: string | null; address: string }) {
  const was = await getAccount(accountId);
  await env.DB.prepare(`UPDATE accounts SET bill_name = ?, bill_address = ?${SALES.gst ? ', bill_gstin = ?' : ''} WHERE id = ?`)
    .bind(...(SALES.gst ? [bill.name, bill.address, bill.gstin, accountId] : [bill.name, bill.address, accountId])).run();
  const changed = [
    ...(was?.bill_name !== bill.name ? [`Name: ${bill.name}`] : []),
    ...(was?.bill_address !== bill.address ? [`Address: ${bill.address.replace(/\s*\n\s*/g, ', ')}`] : []),
    ...(SALES.gst && (was?.bill_gstin ?? null) !== bill.gstin ? [`GSTIN: ${bill.gstin ?? '—'}`] : []),
  ];
  if (changed.length) await event('buyer', 'billing.changed', accountId, null, changed.join(' · ')).run();
}
