/* bun run emails -- preview [--to someone@example.com] [--only words]
   Sends every email the site sends to the owner as a template: each variable is a highlighted {placeholder}, so the
   fixed words stand apart from what changes. Built with the same functions the Worker uses (src/lib/emails.ts) and
   sent through Cloudflare Email Service with wrangler (you must be logged in to the account: bunx wrangler login).
   Re-run it after changing an email. --only: just the ones whose name has those words (--only trial). */
import { spawnSync } from 'bun';
import { writeFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { EMAIL, OWNER_EMAIL, NAME } from '../src/consts';
import * as E from '../src/lib/emails';

const args = process.argv.slice(2);
if (args[0] !== 'preview') {
  console.log('Usage: bun run emails -- preview [--to address] [--only words]');
  process.exit(1);
}
const to = args.includes('--to') ? args[args.indexOf('--to') + 1] : OWNER_EMAIL;
const only = args.includes('--only') ? args[args.indexOf('--only') + 1].toLowerCase() : '';
const link = '{link}';

const previews: [string, E.Mail][] = [
  ['Sign-in code', E.codeMail({ code: '{code}' })],
  ['Payment received', E.paymentReceivedMail({ amount: '{amount}', forWhat: '{for_what}', ref: '{reference}' })],
  ['Payment confirmed (with the receipt)', E.receiptMail({ doc: 'receipt', number: '{number}', date: '{date}', forWhat: '{for_what}', billedTo: '{name}', lines: [], total: '{amount}', planUntil: '{plan_until}', upi: true, link, download: '{download_link}' })],
  ['Payment to check (to the owner)', E.paymentToCheckMail({ amount: '{amount}', forWhat: '{for_what}', ref: '{reference}', email: '{email}', name: '{name}', utr: '{utr}', sent: '{time}', link, attached: true })],
  ['Payment not verified', E.rejectedMail({ amount: '{amount}', ref: '{reference}', note: '{reason}', link })],
  ['You can pay again (after Unblock)', E.unblockedMail({ link })],
  ['Checkout left unfinished (a day after, once)', E.unfinishedMail({ link })],
  ['Trial ending (3 days before)', E.trialEndingMail({ until: '{trial_until}', link })],
  ['Trial ended', E.trialEndedMail({ link })],
  ['ARN slot freed', E.arnFreedMail({ arn: '{arn}' })],
  ['ARN taken by another account', E.arnTakenMail({ arn: '{arn}', link })],
  ['Support reply (from the panel)', E.supportReplyMail({ subject: 'Your support request #{number}: {topic}', number: '{number}',
    message: 'Hello,\n\nWe’ve freed the slot for ARN-111111 on your plan. Add the new ARN in the software, and it takes the free slot.\n\nBest regards,\nMFDInvoice Support' })],
  ['Support request received (to the person)', E.supportReceivedMail({ number: '{number}', topic: '{topic}' })],
  ['Gift given', E.giftGivenMail({ link })],
  ['Gift started', E.giftStartedMail({ until: '{plan_until}', link })],
  ['Deletion scheduled', E.deletionMail({ when: '{delete_time}', link })],
  ['Email changed (to the old address)', E.emailChangedOldMail({ newEmail: '{new_email}' })],
  ['Email changed (to the new address)', E.emailChangedNewMail({ oldEmail: '{old_email}', link })],
  ['Support request (to support@, and the owner’s copy)', E.supportMail({ number: '{number}', topic: '{topic}', email: '{email}', arn: '{arn}', newEmail: '{new_email}', plan: '{plan}', message: '{message}', files: '{screenshots}', link })],
  ['Data copy', E.dataCopyMail({ asked: '{date}', sections: [
    { title: 'Account', rows: [['Email', '{email}'], ['Account ID', '{account}'], ['Created', '{time}']] },
    { title: 'Billing details', rows: [['Name', '{name}'], ['Address', '{address}']] },
    { title: 'Plan', rows: [['Plan', '{paid_gift_or_trial}'], ['From', '{date}'], ['Until', '{date}'], ['ARN slots', '{slots}']] },
    { title: 'ARNs', rows: [['{arn}', '{holder}']] },
    { title: 'Orders', rows: [['{reference}', '{for_what} · {amount} · {status} · UTR {utr} · screenshot {file} · {time}']] },
    { title: 'Receipts', rows: [['{number}', '{amount} · {time}']] },
    { title: 'Gifts', rows: [], empty: 'No gifts.' },
    { title: 'Support requests', rows: [['#{number}', '{topic} · {status} · {time}']] },
    { title: 'Sign-in codes requested (the last day)', rows: [['{time}', 'from IP {ip}']] },
    { title: 'Signed-in sessions', rows: [['{where}', 'started {time}, last seen {time}']] },
  ] })],
];

const b64 = (s: string) => Buffer.from(s, 'utf8').toString('base64').replace(/.{76}/g, '$&\r\n');
const word = (s: string) => `=?UTF-8?B?${Buffer.from(s, 'utf8').toString('base64')}?=`;
function mime(subject: string, m: E.Mail) {
  const b = 'b' + crypto.randomUUID().replace(/-/g, '');
  return [
    `From: ${NAME} <${EMAIL.from}>`, `To: ${to}`, `Subject: ${word(subject)}`, 'MIME-Version: 1.0',
    `Content-Type: multipart/alternative; boundary="${b}"`, '',
    `--${b}`, 'Content-Type: text/plain; charset=utf-8', 'Content-Transfer-Encoding: base64', '', b64(m.text), '',
    `--${b}`, 'Content-Type: text/html; charset=utf-8', 'Content-Transfer-Encoding: base64', '', b64(m.html), '',
    `--${b}--`, '',
  ].join('\r\n');
}

const dir = mkdtempSync(join(tmpdir(), 'emails-'));
let n = 0;
for (const [name, m0] of previews) {
  if (only && !name.toLowerCase().includes(only)) { n++; continue; }
  const m = E.highlight(m0);
  const file = join(dir, `${++n}.eml`);
  writeFileSync(file, mime(`Template ${n}/${previews.length} · ${name} · ${m.subject}`, { ...m, text: `TEMPLATE: ${name}\n\n${m.text}` }));
  const r = spawnSync(['bunx', 'wrangler', 'email', 'sending', 'send-raw', '--from', EMAIL.from, '--to', to, '--mime-file', file], { stdout: 'pipe', stderr: 'pipe' });
  console.log(`${r.exitCode === 0 ? 'sent' : 'FAILED'}  ${n}. ${name}${r.exitCode === 0 ? '' : '\n' + r.stderr.toString() + r.stdout.toString()}`);
}
rmSync(dir, { recursive: true, force: true });
