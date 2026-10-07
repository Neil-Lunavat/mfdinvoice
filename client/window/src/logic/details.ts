import { NAME } from '../brand';
/* The details a run uses, and when each setup step is complete (Continue unlocks only when the step is valid). */

import type { ProfileDraft } from '../bridge/types';
import { arnOk, emailOk, gstinOk } from './validate';
import { bump, counterOf, rule46 } from './numbering';

/** The details alone, as a Change in Settings checks them. */
export const detailsValid = (d: ProfileDraft) => arnOk(d.arn) && gstinOk(d.gstin) && d.name.trim().length >= 3;
/** Setup's first step: the ARN, with the authority sentence ticked. Setup cannot go on without it. */
export const whoValid = (d: ProfileDraft) => arnOk(d.arn) && !!d.consent;
/** Setup's Name and GSTIN step. */
export const nameValid = (d: ProfileDraft) => gstinOk(d.gstin) && d.name.trim().length >= 3;
/** The ARN a portal showed is the ARN typed. */
export const sameArn = (shown: string, typed: string) => !!shown && shown.replace(/\D/g, '') === typed.replace(/\D/g, '');
/** The CAMS email with a sign-in that showed this ARN, or "I don't use CAMS": the same rule as KFintech. */
export const camsValid = (d: ProfileDraft) => !d.camsUsed || (emailOk(d.camsEmail) && sameArn(d.camsArn, d.arn));
/** A passed Verify connection is required; without CAMS there is no mail to read. */
export const mailboxValid = (d: ProfileDraft) => !d.camsUsed || d.mailbox.connected;
/** A passed login that showed this ARN, or "I don't use KFintech". One of the two registrars must be used. */
export const kfintechValid = (d: ProfileDraft) =>
  d.kfintech.used ? !!d.kfintech.loggedInAs && sameArn(d.kfintech.arn, d.arn) : d.camsUsed;
/** A portal's own sign-in showed this ARN: KFintech's (a password login), or CAMS's when KFintech is not used. Setup
    finishes only then, because finishing is what binds the ARN to the account. */
export const arnProven = (d: ProfileDraft) =>
  (d.kfintech.used && sameArn(d.kfintech.arn, d.arn)) || (d.camsUsed && sameArn(d.camsArn, d.arn));
/** Which portals showed this ARN, for the line under Check everything. */
export const provenBy = (d: ProfileDraft) =>
  [d.kfintech.used && sameArn(d.kfintech.arn, d.arn) && 'KFintech', d.camsUsed && sameArn(d.camsArn, d.arn) && 'CAMS'].filter(Boolean).join(' and ');
/** The registrars this ARN uses, CAMS first. */
export const registrarsOf = (d: { camsUsed: boolean; kfintech: { used: boolean } }) =>
  [d.camsUsed && 'CAMS', d.kfintech.used && 'KFINTECH'].filter(Boolean) as ('CAMS' | 'KFINTECH')[];
/** The chosen way is set up: a photo given, or a token's certificate picked and a test signed with it. */
export const signatureValid = (d: ProfileDraft) =>
  d.signature.way === 'dsc' ? !!d.signature.cert?.tested : !!d.signature.image;

export const signatureLine = (s: ProfileDraft['signature']) =>
  s.way === 'dsc' ? `USB token · ${s.cert?.name ?? 'not picked'}` : 'Your signature';

/** The next number the person's own series will use, from the last one they issued: '' when it cannot count. */
export const nextInvoice = (i: ProfileDraft['invoices']) => (i.last.trim() && !rule46(i.last) ? bump(i.last.trim(), counterOf(i.last.trim(), i.at)) : '');

/** Books are connected (Tally or Zoho Books): they give the person's own invoice numbers, so no last number is asked. */
export const booked = (d: Pick<ProfileDraft, 'tally' | 'zoho'>) => !!(d.tally?.company || d.zoho?.org);
export const bookKind = (d: Pick<ProfileDraft, 'tally' | 'zoho'>): '' | 'tally' | 'zoho' => (d.zoho?.org ? 'zoho' : d.tally?.company ? 'tally' : '');

/** Which invoice is uploaded is chosen; their own needs the last number (with a part that counts, unless Tally gives
    the numbers) and an address. */
export const invoicesValid = (d: ProfileDraft) =>
  d.invoices.source === 'registrar'
  || (d.invoices.source === 'own' && (booked(d) || !!nextInvoice(d.invoices)) && d.invoices.settings.address.some(a => a.trim().length > 2));

/** Your invoices: which invoice is uploaded, and the signature that goes on it, seen on that invoice. */
export const invoicesStepValid = (d: ProfileDraft) => invoicesValid(d) && signatureValid(d);

/** Books are optional: nothing chosen, or a company or organisation whose GSTIN is this ARN's, or one the person said is right. */
export const booksValid = (d: ProfileDraft) =>
  (!d.tally?.company || d.tally.same || d.tally.sure) && (!d.zoho?.org || d.zoho.same || d.zoho.sure);
export const booksLine = (d: Pick<ProfileDraft, 'tally' | 'zoho'>) =>
  d.zoho?.org ? `Zoho Books · ${d.zoho.org}` : d.tally?.company ? `Tally · ${d.tally.company}` : 'Not connected';

// The portals come before Name and GSTIN, which they fill in. The books come before Your invoices: with books
// connected, the books give the invoice numbers. The mailbox is last.
export const STEP_TITLES = ['Your ARN', 'CAMS', 'KFintech', 'Name and GSTIN', 'Signature', 'Your books', 'Your invoices', 'Mailbox', 'Check everything'] as const;
export const STEP = { arn: 0, cams: 1, kfintech: 2, name: 3, signature: 4, books: 5, invoices: 6, mailbox: 7 } as const;
const STEPS_VALID = [whoValid, camsValid, kfintechValid, nameValid, signatureValid, booksValid, invoicesValid, mailboxValid] as const;
/** Check everything finishes only when every step still holds (an ARN changed late unsettles the others) and a
    portal has shown the ARN. */
export const allValid = (d: ProfileDraft) => STEPS_VALID.every(v => v(d)) && arnProven(d);
export const stepValid = [...STEPS_VALID, allValid] as const;

export function mailboxLine(m: ProfileDraft['mailbox']): string {
  if (m.provider === 'folder') return "You choose CAMS's files yourself";
  if (m.provider === 'forward') return `Forwarded to ${NAME} · ${m.address}${m.connected ? '' : ' · not set up'}`;
  return `Gmail · ${m.address}${m.connected ? '' : ' · not connected'}`;
}

export const kfintechLine = (k: ProfileDraft['kfintech']) => (!k.used ? 'Not used' : k.loggedInAs ? `Logged in as ${k.loggedInAs}` : k.username);

export const invoicesLine = (i: ProfileDraft['invoices'], books: boolean | '' | 'tally' | 'zoho' = false) =>
  i.source === 'own' ? (books ? `Your own · numbered by ${books === 'zoho' ? 'Zoho Books' : 'Tally'}` : `Your own · next ${nextInvoice(i) || '—'}`) : "The registrar's, signed by you";
