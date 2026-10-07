/* Sending, through Cloudflare Email Service (the EMAIL binding). The emails themselves are built in lib/emails.ts.
   With EMAIL_CONSOLE=1 (local .dev.vars, and `bun run check`) an email is printed to the log instead. */
import { env } from 'cloudflare:workers';
import { EMAIL, NAME } from '../../consts';
import type { Mail } from '../emails';
export { esc } from '../emails';

export type Attachment = { content: ArrayBuffer | string; filename: string; type: string; disposition: 'attachment' | 'inline' };
/* An email may be 5 MiB in all; attachments stop well short of that. */
export const ATTACH_MAX = 4 * 1024 * 1024;

export async function send(to: string, m: Mail, opts: { replyTo?: string; attachments?: Attachment[]; from?: { name: string; email: string } } = {}) {
  const attachments = opts.attachments ?? [];
  const replyTo = opts.replyTo ?? EMAIL.support;
  /* test accounts have no mailbox: printing instead of sending keeps bounces off our sending reputation */
  if (env.EMAIL_CONSOLE === '1' || (env.TEST_LOGIN_DOMAIN && to.endsWith('@' + env.TEST_LOGIN_DOMAIN))) {
    console.log(`\n--- email to ${to} ---\nFrom: ${opts.from?.email ?? EMAIL.from}\nReply-To: ${replyTo}\nSubject: ${m.subject}\n\n${m.text}\n${attachments.map(a => `[attached: ${a.filename}]\n`).join('')}--- end ---\n`);
    return;
  }
  /* the inbox shows the name, not "no-reply" */
  await env.EMAIL.send({ to, from: opts.from ?? { name: NAME, email: EMAIL.from }, replyTo, subject: m.subject, text: m.text, html: m.html, ...(attachments.length ? { attachments } : {}) });
}
