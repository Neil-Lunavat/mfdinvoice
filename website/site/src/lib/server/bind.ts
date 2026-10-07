/* Binding an ARN to an account: the app does it when setup finishes, once the person's own portal sign-ins have shown
   the ARN (/api/app/bind). On an account that has never had a plan it starts the free trial with that ARN (trial.ts;
   trial_until is its last day), unless this email has had one: then it answers (403) no_active_plan with
   trial_used: true, as for a plan that has ended. Refuses (409) arn_taken (another account has it, on a plan that
   is running), no_free_slot, or (403) no_active_plan. Binding an ARN the account already has is fine (already: true).
   An ARN on an account whose plan has ended is free to take: it leaves that account, which is emailed, and comes to
   this one. */
import { env } from 'cloudflare:workers';
import { json, fail, str } from './http';
import { normArn } from './arn';
import { getAccount, getPlan, isActive, trialUsed } from './account';
import { startTrial } from './trial';
import { event } from './events';
import { now, todayIST, siteOrigin } from './util';
import { send } from './mail';
import { record } from './errors';
import { arnTakenMail } from '../emails';

const ownerOf = (arn: string) => env.DB.prepare('SELECT account_id FROM arns WHERE arn = ?').bind(arn).first<{ account_id: number }>();
const usedBy = async (account: number) =>
  (await env.DB.prepare('SELECT COUNT(*) AS n FROM arns WHERE account_id = ?').bind(account).first<{ n: number }>())!.n;

/* Takes an ARN off an account whose plan has ended (or that has none), for the account binding it now. One
   statement decides, so a plan renewed this second keeps its ARN. It is in that account's activity. */
async function release(arn: string, from: number, to: number) {
  const [r] = await env.DB.batch([
    env.DB.prepare(`DELETE FROM arns WHERE arn = ?1 AND account_id = ?2
        AND NOT EXISTS (SELECT 1 FROM plans WHERE account_id = ?2 AND ends_on >= ?3)`).bind(arn, from, todayIST()),
    env.DB.prepare(`INSERT INTO events (at, actor, action, account_id, ref, note)
        SELECT ?1, 'system', 'arn.freed', ?2, ?3, ?4 WHERE changes() > 0`)
      .bind(now(), from, arn, `Its plan had ended; taken by account ${to}`),
  ]);
  if (!r.meta.changes) return false;
  /* the old account is told once; a failed email doesn't stop the bind */
  const old = await getAccount(from);
  if (old) await send(old.email, arnTakenMail({ arn: `ARN-${arn}`, link: `${siteOrigin()}/support` }))
    .catch(e => record('email', `arn taken ${arn}`, e));
  return true;
}

export async function bindArn(account: number, rawArn: unknown, rawHolder: unknown): Promise<Response> {
  const arn = normArn(rawArn), holder = str(rawHolder, 200);
  if (!arn) return fail(400, 'bad_arn');
  if (!holder) return fail(400, 'no_holder');
  let owner = await ownerOf(arn);
  /* another account's: theirs while their plan runs, free to take once it has ended */
  const theirs = owner && owner.account_id !== account ? owner.account_id : null;
  if (theirs !== null && isActive(await getPlan(theirs))) return fail(409, 'arn_taken');

  let plan = await getPlan(account);
  /* never had a plan: this ARN starts the account's free trial */
  if (!plan) {
    if (!(await getAccount(account))) return fail(404, 'no_account');
    /* one free trial per email: an account deleted and made again doesn't get a second */
    if (await trialUsed(account)) return fail(403, 'no_active_plan', { paid_until: null, trial_used: true });
    if (theirs !== null && !(await release(arn, theirs, account))) return fail(409, 'arn_taken');
    const until = await startTrial(account, arn, holder);
    if (until) return json({ ok: true, arn, already: false, slots: 1, used: 1, trial_until: until });
    /* it didn't start: a plan arrived meanwhile (carry on below), or another account took the ARN a moment ago */
    plan = await getPlan(account);
    if (!plan) return fail(409, 'arn_taken');
  }
  if (!isActive(plan)) return fail(403, 'no_active_plan', { paid_until: plan.ends_on });
  if (theirs !== null) {
    /* it leaves the other account only when this one has a slot for it */
    const used = await usedBy(account);
    if (used >= plan.slots) return fail(409, 'no_free_slot', { slots: plan.slots, used });
    if (!(await release(arn, theirs, account))) return fail(409, 'arn_taken');
    owner = null;
  }
  if (owner) return json({ ok: true, arn, already: true, slots: plan.slots, used: await usedBy(account) });

  /* one statement: it only inserts while a slot is free, so two setups at once can't overfill the plan */
  const r = await env.DB.prepare(`INSERT INTO arns (arn, account_id, holder)
      SELECT ?1, ?2, ?3 WHERE (SELECT COUNT(*) FROM arns WHERE account_id = ?2) < (SELECT slots FROM plans WHERE account_id = ?2)
      ON CONFLICT (arn) DO NOTHING`).bind(arn, account, holder).run();
  if (r.meta.changes) await event('app', 'arn.added', account, arn, holder).run();
  if (!r.meta.changes) {
    const again = await ownerOf(arn);
    if (!again) return fail(409, 'no_free_slot', { slots: plan.slots, used: await usedBy(account) });
    if (again.account_id !== account) return fail(409, 'arn_taken');
  }
  return json({ ok: true, arn, already: false, slots: plan.slots, used: await usedBy(account) });
}
