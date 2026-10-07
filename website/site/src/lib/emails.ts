/* Every email the site sends, built from one layout in the site's look. Each email is a list of blocks, turned into
   HTML (tables and inline CSS, system fonts, no images, so Gmail, Outlook and phone mail apps show it the same) and
   into its plain-text twin. Pure functions: the Worker sends them (lib/server/mail.ts), and `bun run emails -- preview`
   sends each one as a template with every variable shown as a highlighted {placeholder}. */
import { NAME, WORDMARK } from '../consts';

export type Mail = { subject: string; text: string; html: string };
type Row = [label: string, value: string, href?: string];
type Block =
  | { t: 'h'; s: string }            /* the heading */
  | { t: 'h2'; s: string }           /* a section heading (the data copy) */
  | { t: 'p'; s: string }
  | { t: 'say'; s: string }          /* words as typed: line breaks kept (the panel's reply) */
  | { t: 'code'; s: string }         /* the sign-in code, first and large */
  | { t: 'rows'; r: Row[] }          /* label / value pairs */
  | { t: 'box'; s: string }          /* a message, quoted as written */
  | { t: 'btn'; s: string; href: string }
  | { t: 'note'; s: string };        /* small print */

export const esc = (s: string) =>
  s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);

const C = { ink: '#0f172a', ink2: '#334155', muted: '#5b6475', faint: '#94a3b8', line: '#e4e7ec', line2: '#eef0f3', canvas: '#f6f7f9', subtle: '#fafbfc', blue: '#1d4ed8' };
const SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif";
const MONO = "ui-monospace,SFMono-Regular,Consolas,'Liberation Mono',Menlo,monospace";

function blockHtml(b: Block): string {
  switch (b.t) {
    case 'h': return `<h1 style="margin:0 0 14px;font:600 21px/1.3 ${SANS};letter-spacing:-.02em;color:${C.ink}">${esc(b.s)}</h1>`;
    case 'h2': return `<h2 style="margin:26px 0 8px;font:600 15px/1.4 ${SANS};color:${C.ink}">${esc(b.s)}</h2>`;
    case 'p': return `<p style="margin:0 0 14px;font:15px/1.6 ${SANS};color:${C.ink2}">${esc(b.s)}</p>`;
    case 'code': return `<p style="margin:0 0 18px;font:600 36px/1.2 ${MONO};letter-spacing:8px;color:${C.ink}">${esc(b.s)}</p>`;
    case 'say': return `<p style="margin:0 0 14px;font:15px/1.6 ${SANS};color:${C.ink2}">${esc(b.s).replace(/\n/g, '<br>')}</p>`;
    case 'note': return `<p style="margin:14px 0 0;font:13px/1.55 ${SANS};color:${C.muted}">${esc(b.s)}</p>`;
    case 'box': return `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 16px"><tr><td style="padding:14px 16px;background:${C.subtle};border:1px solid ${C.line};border-radius:10px;font:14.5px/1.6 ${SANS};color:${C.ink};white-space:pre-wrap">${esc(b.s)}</td></tr></table>`;
    case 'btn': return `<table role="presentation" cellpadding="0" cellspacing="0" style="margin:6px 0 14px"><tr><td style="background:${C.blue};border-radius:8px"><a href="${esc(b.href)}" style="display:inline-block;padding:11px 20px;font:500 14.5px/1.2 ${SANS};color:#ffffff;text-decoration:none">${esc(b.s)}</a></td></tr></table>`;
    case 'rows': return `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 16px;border-top:1px solid ${C.line2}">${b.r.map(([k, v, href]) =>
      `<tr><td valign="top" style="padding:9px 12px 9px 0;border-bottom:1px solid ${C.line2};font:13.5px/1.5 ${SANS};color:${C.muted};width:38%">${esc(k)}</td><td valign="top" style="padding:9px 0;border-bottom:1px solid ${C.line2};font:14px/1.5 ${SANS};color:${C.ink};word-break:break-word">${href ? `<a href="${esc(href)}" style="color:${C.blue};text-decoration:none">${esc(v)}</a>` : esc(v).replace(/\n/g, '<br>')}</td></tr>`).join('')}</table>`;
  }
}

function blockText(b: Block): string {
  switch (b.t) {
    case 'h': return b.s.toUpperCase() === b.s ? b.s : b.s + '\n';
    case 'h2': return '\n' + b.s + '\n' + '-'.repeat(Math.min(b.s.length, 40));
    case 'code': return b.s + '\n';
    case 'rows': return b.r.map(([k, v, href]) => `${k}: ${v.replace(/\n/g, ', ')}${href && href !== v ? ` (${href})` : ''}`).join('\n') + '\n';
    case 'box': return b.s.split('\n').map(l => '  ' + l).join('\n') + '\n';
    case 'btn': return `${b.s}: ${b.href}\n`;
    default: return b.s + '\n';
  }
}

/* The layout: the mark and the wordmark (text only), a white card, and why this email came. */
function layout(subject: string, blocks: Block[], why: string, preheader?: string): Mail {
  /* the inbox's preview line: without it, mail apps show the wordmark ("✓ MFDInvoice …"). After it, only zero-width
     characters (no spaces: those showed as a gap), enough to use up the preview so nothing from the body follows. */
  const pre = preheader ?? (blocks.find(b => b.t === 'p') as { s: string } | undefined)?.s ?? '';
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>${esc(subject)}</title></head>
<body style="margin:0;padding:0;background:${C.canvas}">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;mso-hide:all">${esc(pre)}${'&zwnj;&#847;'.repeat(220)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:${C.canvas}"><tr><td align="center" style="padding:28px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px">
<tr><td style="padding:0 4px 16px"><table role="presentation" cellpadding="0" cellspacing="0"><tr>
<td width="24" height="24" align="center" valign="middle" style="width:24px;height:24px;background:${C.blue};border-radius:7px;font:700 14px/24px ${SANS};color:#ffffff">&#10003;</td>
<td style="padding-left:10px;font:15px/24px ${SANS};color:${C.muted};letter-spacing:-.01em"><b style="font-weight:700;color:${C.ink}">${esc(WORDMARK[0])}</b>${esc(WORDMARK[1])}</td>
</tr></table></td></tr>
<tr><td style="background:#ffffff;border:1px solid ${C.line};border-radius:14px;padding:30px 28px">
${blocks.map(blockHtml).join('\n')}
</td></tr>
<tr><td style="padding:16px 6px 0;font:12.5px/1.55 ${SANS};color:${C.faint}">${esc(why)}</td></tr>
</table></td></tr></table></body></html>`;
  const text = blocks.map(blockText).join('\n').replace(/\n{3,}/g, '\n\n').trim() + `\n\n--\n${NAME}. ${why}\n`;
  return { subject, text, html };
}

const FOR_YOU = 'You’re getting this because of your account on our website.';
const FOR_OWNER = 'Sent to the owner by the website.';

/* ---- to buyers ---- */

export const codeMail = (v: { code: string }) => layout(`${v.code} is your ${NAME} code`, [
  { t: 'code', s: v.code },
  { t: 'p', s: 'Enter this code to sign in. It works for 10 minutes.' },
  { t: 'note', s: 'If you didn’t ask for it, ignore this email. Nobody can sign in without the code.' },
], 'You’re getting this because someone asked to sign in with this address.', `${v.code} is your code. It works for 10 minutes.`);

/* A UPI payment's screenshot has arrived: the first of the two emails around a purchase. */
export const paymentReceivedMail = (v: { amount: string; forWhat: string; ref: string }) => layout(`We’ve received your ${NAME} payment`, [
  { t: 'h', s: 'We’ve received your payment' },
  { t: 'p', s: 'We’re checking it now. We’ll notify you when your payment is confirmed, usually within a few hours, and your plan starts then.' },
  { t: 'rows', r: [['Amount', v.amount], ['For', v.forWhat], ['Reference', v.ref]] },
], FOR_YOU);

/* The payment is confirmed: the second email (for UPI, when the owner approves), with the download and the receipt.
   `download`: the Downloads page, on every approval. The panel's "Resend" sends it without. */
export const receiptMail = (v: {
  doc: 'receipt' | 'tax'; number: string; date: string; forWhat: string; billedTo: string; gstin?: string | null;
  lines: Row[]; total: string; planUntil?: string | null; upi: boolean; link: string; download?: string | null;
}) => {
  const receipt = v.doc === 'receipt', label = receipt ? 'Receipt' : 'Tax invoice';
  return layout(v.upi ? `Your ${NAME} payment is confirmed` : `Your ${NAME} ${receipt ? 'receipt' : 'invoice'} ${v.number}`, [
    { t: 'h', s: v.upi ? 'Your payment is confirmed' : 'Thank you. Your payment is received' },
    ...(v.planUntil ? [{ t: 'p' as const, s: `Your plan runs until ${v.planUntil}.${v.download ? ` Download ${NAME} to get started.` : ''}` }] : []),
    ...(v.download ? [{ t: 'btn' as const, s: `Download ${NAME}`, href: v.download }] : []),
    { t: 'rows', r: [
      (v.download ? [label, v.number, v.link] : [label, v.number]) as Row, ['Date', v.date], ['For', v.forWhat],
      ['Billed to', v.billedTo], ...(v.gstin ? [['GSTIN', v.gstin] as Row] : []),
      ...v.lines, ['Total', v.total],
    ] },
    ...(v.download ? [] : [{ t: 'btn' as const, s: receipt ? 'View the receipt' : 'View the invoice', href: v.link }]),
    { t: 'note', s: `The ${receipt ? 'receipt' : 'invoice'} is also on your account page, ready to print.` },
  ], FOR_YOU);
};

/* A payment the owner couldn't verify. The account can't pay again until support has helped (upi.ts). */
export const rejectedMail = (v: { amount: string; ref: string; note?: string | null; link: string }) => layout(`We couldn’t verify your ${NAME} payment`, [
  { t: 'h', s: 'We couldn’t verify your payment' },
  { t: 'p', s: `We’re sorry. We couldn’t verify your UPI payment of ${v.amount} (reference ${v.ref}).` },
  ...(v.note ? [{ t: 'box' as const, s: v.note }] : []),
  { t: 'p', s: 'If the money left your account, please write to support with the payment’s details and we’ll help you. Until then, a new payment can’t be made from your account.' },
  { t: 'btn', s: 'Write to support', href: v.link },
  { t: 'note', s: 'We’re sorry for the inconvenience.' },
], FOR_YOU);

/* The owner unblocked a payment he couldn't verify (if he chose to tell them): they can pay again. */
export const unblockedMail = (v: { link: string }) => layout(`You can pay for ${NAME} again`, [
  { t: 'h', s: 'You can pay again' },
  { t: 'p', s: 'Your account can make a payment again. Pick up at Checkout whenever you’re ready.' },
  { t: 'btn', s: 'Go to Checkout', href: v.link },
], FOR_YOU);

/* A payment started at Checkout and not finished a day later: one email, once (upi.ts nudgeUnfinished). A nudge,
   not a bill: what they get back, and the way back in. */
export const unfinishedMail = (v: { link: string }) => layout('You were one step away', [
  { t: 'h', s: 'Get your evenings and your GST payout back every month' },
  { t: 'p', s: 'No more logging in to CAMS and KFintech, signing seventeen PDFs or typing the same numbers into Tally.' },
  { t: 'btn', s: 'Pick up where you left off', href: v.link },
], FOR_YOU);

/* The free trial (lib/server/trial.ts): a few days before its last day, and once it is over. The subject, the heading
   and the text each say something different. */
export const trialEndingMail = (v: { until: string; link: string }) => layout(`Your ${NAME} trial ends on ${v.until}`, [
  { t: 'h', s: 'Keep your months running' },
  { t: 'p', s: `Buy a plan now and keep using ${NAME} for a year* after the trial.` },
  { t: 'btn', s: 'Open Checkout', href: v.link },
  { t: 'note', s: '* Your year starts when the trial ends, so you can pay any time before then.' },
], FOR_YOU);

export const trialEndedMail = (v: { link: string }) => layout(`Your ${NAME} free trial has ended`, [
  { t: 'h', s: 'Ready when you are' },
  { t: 'p', s: 'The software has stopped running for now. Buy a plan and it picks up right where it stopped. Everything on your PC is still kept safely.' },
  { t: 'btn', s: 'Continue with a plan', href: v.link },
], FOR_YOU);

/* The owner freed one of the plan's ARN slots (if he chose to tell them). */
export const arnFreedMail = (v: { arn: string }) => layout(`Your ${NAME} ARN slot is free`, [
  { t: 'h', s: 'Your ARN slot is free' },
  { t: 'p', s: `We’ve taken ${v.arn} off your plan. Add the new ARN in the software, and it takes the free slot.` },
], FOR_YOU);

/* Another account added an ARN this account had, after this account's plan ended (bind.ts). Sent once, as it moves. */
export const arnTakenMail = (v: { arn: string; link: string }) => layout(`${v.arn} is now on another ${NAME} account`, [
  { t: 'h', s: `${v.arn} has moved` },
  { t: 'p', s: `Another ${NAME} account has added ${v.arn}. Your plan had ended, so it was free to add. The files on your PC are untouched.` },
  { t: 'p', s: 'Something wrong? Write to support and we’ll look into it.' },
  { t: 'btn', s: 'Write to support', href: v.link },
], FOR_YOU);

/* The panel's one reply to a support request (Support › Reply), from support@: his words, a paragraph per blank line,
   in the usual layout. Replying to it reaches support@, and the conversation goes on from the mailbox. */
export const supportReplyMail = (v: { subject: string; message: string; number: string }) => layout(v.subject,
  v.message.split(/\n\s*\n/).map(s => s.trim()).filter(Boolean).map(s => ({ t: 'say' as const, s })),
  `About your support request #${v.number}. Reply to this email to write back.`);

/* A support request has reached us: the person's own copy (not for "A copy of my data", which has its own email). */
export const supportReceivedMail = (v: { number: string; topic: string }) => layout(`We’ve received your support request #${v.number}`, [
  { t: 'h', s: 'We’ve received your request' },
  { t: 'p', s: `Your request #${v.number} (${v.topic}) has reached us. We’ll reply to this address.` },
  { t: 'note', s: 'To add anything, reply to this email.' },
], FOR_YOU);

export const giftGivenMail = (v: { link: string }) => layout(`You’ve been gifted a year of ${NAME}`, [
  { t: 'h', s: 'You’ve been gifted a plan' },
  { t: 'p', s: `You’ve been gifted a one-year ${NAME} plan for one ARN. Sign in with this email to start it.` },
  { t: 'btn', s: 'Sign in', href: v.link },
  { t: 'note', s: 'The year starts on the day you sign in. It’s tied to this email address.' },
], 'You’re getting this because a plan was gifted to this address.');

export const giftStartedMail = (v: { until: string; link: string }) => layout(`Your ${NAME} plan has started`, [
  { t: 'h', s: 'Your gifted plan has started' },
  { t: 'p', s: `You’ve been gifted a one-year ${NAME} plan for one ARN. It started today and runs until ${v.until}.` },
  { t: 'btn', s: 'Go to your account', href: v.link },
], FOR_YOU);

export const deletionMail = (v: { when: string; link: string }) => layout(`Your ${NAME} account will be deleted`, [
  { t: 'h', s: 'Your account will be deleted' },
  { t: 'p', s: `Your account will be deleted on ${v.when} (India time). Signing in before then keeps it.` },
  { t: 'btn', s: 'Sign in to keep it', href: v.link },
  { t: 'note', s: 'If you didn’t ask for this, sign in now and keep your account.' },
], FOR_YOU);

export const emailChangedOldMail = (v: { newEmail: string }) => layout(`Your ${NAME} account’s email has changed`, [
  { t: 'h', s: 'Your account’s email has changed' },
  { t: 'p', s: `Your account now signs in with ${v.newEmail}. This address no longer does.` },
  { t: 'note', s: 'If you didn’t ask for this, reply to this email.' },
], 'You’re getting this because this address was your account’s email.');

export const emailChangedNewMail = (v: { oldEmail: string; link: string }) => layout(`This is now your ${NAME} account’s email`, [
  { t: 'h', s: 'This is now your account’s email' },
  { t: 'p', s: `Your account (until now ${v.oldEmail}) signs in with this address from now on.` },
  { t: 'btn', s: 'Sign in', href: v.link },
], FOR_YOU);

/* The data copy: every section as label/value rows; the same data is attached as JSON. */
export const dataCopyMail = (v: { asked: string; sections: { title: string; rows: Row[]; empty?: string }[] }) => layout(`Your ${NAME} data`, [
  { t: 'h', s: 'A copy of your data' },
  { t: 'p', s: `Everything our website stores about your account, as you asked on ${v.asked}. The same data is attached as a JSON file.` },
  ...v.sections.flatMap(s => [{ t: 'h2' as const, s: s.title }, s.rows.length ? { t: 'rows' as const, r: s.rows } : { t: 'p' as const, s: s.empty ?? 'None.' }]),
  { t: 'note', s: 'The software keeps your passwords, signature and invoices on your PC, so they aren’t here. A forwarded CAMS email is deleted soon after your PC takes it.' },
], FOR_YOU);

/* ---- to support@ and the owner ---- */

export const paymentToCheckMail = (v: { amount: string; forWhat: string; ref: string; email: string; name: string; utr: string; sent: string; link: string; attached: boolean }) =>
  layout(`Payment to check: ${v.amount} from ${v.email} (${v.ref})`, [
    { t: 'h', s: 'A UPI payment to check' },
    { t: 'rows', r: [['Amount', v.amount], ['For', v.forWhat], ['Reference', v.ref], ['From', v.email], ['Name', v.name], ['UTR', v.utr], ['Sent', v.sent]] },
    { t: 'p', s: v.attached ? 'The screenshot is attached. Check that the money arrived, then approve or reject it in the panel.' : 'The screenshot is too big to attach. It’s in the panel, next to Approve and Reject.' },
    { t: 'btn', s: 'Open in the panel', href: v.link },
  ], FOR_OWNER);

export const supportMail = (v: { number: string; topic: string; email: string; arn?: string | null; newEmail?: string | null; plan: string; message?: string | null; files: string; link: string }) =>
  layout(`#${v.number} · ${v.topic} · ${v.email}`, [
    { t: 'h', s: `#${v.number} · ${v.topic}` },
    { t: 'rows', r: [['From', v.email], ...(v.arn ? [['ARN', v.arn] as Row] : []), ...(v.newEmail ? [['New email', v.newEmail] as Row] : []), ['Plan', v.plan]] },
    ...(v.message ? [{ t: 'box' as const, s: v.message }] : []),
    { t: 'p', s: v.files },
    { t: 'btn', s: 'Open the request in the panel', href: v.link },
    { t: 'note', s: 'Reply to this email to answer them. Set it to Solved in the panel.' },
  ], FOR_OWNER);

/* Previews: every {placeholder} in the text (not inside tags) is highlighted. */
export function highlight(m: Mail): Mail {
  const mark = (s: string) => s.replace(/\{[a-z_]+\}/g, x => `<span style="background:#fff1b8;color:#8a5300;border-radius:3px;padding:0 3px">${x}</span>`);
  const [head, body] = m.html.split('<body');
  return { ...m, html: head + '<body' + body.split(/(<[^>]+>)/).map(p => (p.startsWith('<') ? p : mark(p))).join('') };
}
