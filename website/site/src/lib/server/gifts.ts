/* Gifts: a free plan (a year on one ARN) given to an email from the admin panel, only to someone who has never had a
   bought or gifted plan. It is emailed to that address and starts the day that email signs in (web or app, auth.ts
   verifyCode), exactly once. No secret link: the email is what makes it theirs. If the email already has an account,
   it starts when given. A free trial doesn't count as a plan here: the gift takes over from it, the year running
   from the trial's last day. Gifts are separate from orders: no receipt, never a sale. */
import { env } from 'cloudflare:workers';
import { giftGivenMail, giftStartedMail } from '../emails';
import { longDate } from '../invoice';
import { send } from './mail';

import { record } from './errors';
import { getPlan, yearFrom } from './account';
import { now, todayIST, plusYear, token, siteOrigin } from './util';

export type Gift = {
  id: number; email: string; arns: number; years: number; given_at: string; given_by: string;
  used_at: string | null; account_id: number | null; revoked_at: string | null; revoked_by: string | null;
};
export type GiftStatus = 'waiting' | 'used' | 'revoked';

/* Starts the oldest usable gift for this email on this account, if the account has never had a bought or gifted plan.
   One D1 batch: the first statement claims the gift (only while unused, unrevoked, and no such plan), the rest act
   only on that claim, so two sign-ins at once can't both apply it. Returns the plan's last day, or null. */
export async function applyGift(accountId: number, email: string): Promise<string | null> {
  const g = await env.DB.prepare('SELECT id, years FROM gifts WHERE email = ? AND used_at IS NULL AND revoked_at IS NULL ORDER BY id LIMIT 1')
    .bind(email).first<{ id: number; years: number }>();
  if (!g) return null;
  const today = todayIST(), at = now(), claim = token();
  let endsOn = yearFrom(await getPlan(accountId));
  for (let i = 0; i < g.years; i++) endsOn = plusYear(endsOn);
  const mine = 'FROM gifts WHERE id = ?1 AND claim = ?2';
  await env.DB.batch([
    env.DB.prepare(`UPDATE gifts SET used_at = ?3, account_id = ?4, claim = ?2 WHERE id = ?1 AND used_at IS NULL AND revoked_at IS NULL
        AND NOT EXISTS (SELECT 1 FROM plans WHERE account_id = ?4 AND source != 'trial')`).bind(g.id, claim, at, accountId),
    env.DB.prepare(`INSERT INTO plans (account_id, slots, starts_on, ends_on, source, updated_at)
        SELECT account_id, arns, ?3, ?4, 'grant', ?5 ${mine}
        ON CONFLICT (account_id) DO UPDATE SET slots = excluded.slots, starts_on = excluded.starts_on,
          ends_on = excluded.ends_on, source = 'grant', updated_at = excluded.updated_at`).bind(g.id, claim, today, endsOn, at),
    env.DB.prepare(`INSERT INTO events (at, actor, action, account_id, ref, note)
        SELECT ?3, 'system', 'gift.used', account_id, 'gift ' || id, 'Plan until ' || ?4 ${mine}`).bind(g.id, claim, at, endsOn),
  ]);
  const won = await env.DB.prepare(`SELECT 1 ${mine}`).bind(g.id, claim).first();
  return won ? endsOn : null;
}

/* Gives a gift: refused if the email's account has ever had a bought or gifted plan; otherwise saved, then applied at once if the email
   has an account (and no deletion pending), and emailed either way. actor: the admin's email. */
export async function giveGift(email: string, actor: string) {
  const acct = await env.DB.prepare(`SELECT id, delete_after, EXISTS (SELECT 1 FROM plans p WHERE p.account_id = accounts.id AND p.source != 'trial') AS had_plan FROM accounts WHERE email = ?`)
    .bind(email).first<{ id: number; delete_after: string | null; had_plan: number }>();
  if (acct?.had_plan) return { error: 'had_plan' };
  const [ins] = await env.DB.batch<{ id: number }>([
    env.DB.prepare('INSERT INTO gifts (email, arns, years, given_at, given_by) VALUES (?, 1, 1, ?, ?) RETURNING id').bind(email, now(), actor),
    env.DB.prepare(`INSERT INTO events (at, actor, action, account_id, ref, note) VALUES (?, ?, 'gift.given', ?, 'gift ' || last_insert_rowid(), ?)`)
      .bind(now(), actor, acct?.id ?? null, email),
  ]);
  const row = ins.results[0];
  const until = acct && !acct.delete_after ? await applyGift(acct.id, email) : null;
  try {
    await send(email, until
      ? giftStartedMail({ until: longDate(until), link: `${siteOrigin()}/account` })
      : giftGivenMail({ link: `${siteOrigin()}/signin?next=/account` }));
  } catch (e) { await record('email', 'giveGift', e); }
  return { id: row!.id, started: !!until, until };
}

/* Revokes a gift that hasn't been used. */
export async function revokeGift(id: number, actor: string) {
  const g = await env.DB.prepare('SELECT g.email, a.id AS account FROM gifts g LEFT JOIN accounts a ON a.email = g.email WHERE g.id = ?').bind(id).first<{ email: string; account: number | null }>();
  if (!g) return { error: 'no_gift' };
  const [r] = await env.DB.batch([
    env.DB.prepare('UPDATE gifts SET revoked_at = ?, revoked_by = ? WHERE id = ? AND used_at IS NULL AND revoked_at IS NULL').bind(now(), actor, id),
    env.DB.prepare(`INSERT INTO events (at, actor, action, account_id, ref, note)
        SELECT ?, ?, 'gift.revoked', ?, 'gift ' || id, email FROM gifts WHERE id = ? AND revoked_by = ? AND changes() > 0`).bind(now(), actor, g.account, id, actor),
  ]);
  return r.meta.changes ? { ok: true } : { error: 'not_waiting' };
}

/* Every gift with its status: waiting, used or revoked. */
export async function listGifts(filter: { email?: string } = {}) {
  const rows = (await env.DB.prepare(`SELECT g.*, (SELECT a.uid FROM accounts a WHERE a.email = g.email) AS holder
      FROM gifts g ${filter.email ? 'WHERE g.email = ?' : ''} ORDER BY g.given_at DESC LIMIT 500`)
    .bind(...(filter.email ? [filter.email] : [])).all<Gift & { holder: string | null }>()).results;
  return rows.map(g => ({ ...g, status: (g.revoked_at ? 'revoked' : g.used_at ? 'used' : 'waiting') as GiftStatus }));
}
