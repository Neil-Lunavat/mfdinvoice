/* The activity log (the `events` table): each change writes one row in the same D1 batch as the change itself.
   actor: an admin's email, 'buyer', 'app' (the app), 'writer:<email>' or 'system' (the scheduled jobs). */
import { env } from 'cloudflare:workers';
import { now } from './util';

export type Action =
  | 'account.created' | 'signin.web' | 'signin.app' | 'signout.everywhere' | 'app.downloaded'
  | 'payment.sent' | 'payment.approved' | 'payment.rejected' | 'payment.unblocked' | 'payment.nudged'
  | 'trial.started' | 'trial.ending' | 'trial.ended'
  | 'gift.given' | 'gift.used' | 'gift.revoked'
  | 'deletion.scheduled' | 'deletion.cancelled' | 'deletion.done'
  | 'arn.added' | 'arn.freed' | 'email.changed' | 'receipt.resent' | 'billing.changed'
  | 'request.sent' | 'request.solved' | 'request.reopened' | 'report.sent' | 'data.sent' | 'post.saved' | 'post.deleted' | 'image.deleted';

export const event = (actor: string, action: Action, accountId: number | null, ref: string | null = null, note: string | null = null) =>
  env.DB.prepare('INSERT INTO events (at, actor, action, account_id, ref, note) VALUES (?, ?, ?, ?, ?, ?)')
    .bind(now(), actor, action, accountId, ref, note);

export const eventsFor = (accountId: number) =>
  env.DB.prepare('SELECT at, actor, action, ref, note FROM events WHERE account_id = ? ORDER BY at DESC, id DESC LIMIT 200')
    .bind(accountId).all<{ at: string; actor: string; action: Action; ref: string | null; note: string | null }>().then(r => r.results);

/* How each action reads on an account's page. */
export const ACTION_TEXT: Record<Action, string> = {
  'account.created': 'Account created', 'signin.web': 'Signed in on the website', 'signin.app': 'Signed in to the app',
  'signout.everywhere': 'Signed out of all devices', 'app.downloaded': 'App downloaded', 'payment.sent': 'Payment sent for checking',
  'arn.added': 'ARN added by the app', 'request.sent': 'Support request sent', 'request.reopened': 'Support request reopened',
  'payment.approved': 'Payment approved', 'payment.rejected': 'Payment rejected', 'payment.unblocked': 'Unblocked: can pay again',
  'payment.nudged': 'Emailed: a payment left unfinished',
  'trial.started': 'Free trial started', 'trial.ending': 'Emailed: the trial is ending', 'trial.ended': 'Emailed: the trial has ended',
  'gift.given': 'Gift given', 'gift.used': 'Gift started', 'gift.revoked': 'Gift revoked',
  'deletion.scheduled': 'Deletion scheduled', 'deletion.cancelled': 'Deletion cancelled', 'deletion.done': 'Account deleted',
  'arn.freed': 'ARN freed', 'billing.changed': 'Billing details changed', 'email.changed': 'Email changed', 'receipt.resent': 'Receipt resent',
  'request.solved': 'Support request solved', 'report.sent': 'Sent to support from the app', 'data.sent': 'Data copy sent',
  'post.saved': 'Post saved', 'post.deleted': 'Post deleted', 'image.deleted': 'Image deleted',
};
