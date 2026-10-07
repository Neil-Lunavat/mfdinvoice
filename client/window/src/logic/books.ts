/* What the window says about the person's books (Tally or Zoho Books), all in one place. */

import { dayMonYear } from './format';

export const booksName = (kind: string) => (kind === 'zoho' ? 'Zoho Books' : 'Tally');

/** The red line while a run waits for the books. Zoho Books says its own words (`said`). */
export const waitingLine = (kind: string, company: string, said: string) =>
  kind === 'zoho' ? said || "Zoho Books isn't answering." : `TallyPrime needs to be open, with ${company}.`;
export const waitingSub = (kind: string, said: string) =>
  kind === 'zoho' ? 'The run goes on by itself when Zoho Books answers. Or press Refresh.' : said || 'The run goes on by itself when Tally answers. Or press Refresh.';

/** Setup's line under Your invoices when books are connected. */
export const continuesLine = (next: string, kind = 'tally') =>
  `Your invoices continue from ${next}. Anything typed into ${booksName(kind)} meanwhile is picked up on its own.`;
export const continuesLineNoNext = (company: string, kind = 'tally') =>
  `Your invoices continue from the last one in ${company}. Anything typed into ${booksName(kind)} meanwhile is picked up on its own.`;

/** Letting Zoho Books in, from Settings, the Books tab or setup: one organisation is used at once. */
export const connectWords = (state: string, said: string) =>
  said || (state === 'cancelled' ? '' : 'Zoho Books could not be connected. Try again.');

/** Your check: the older-month line, and the new financial year's first invoice. */
export const afterLine = (month: string) => `These take the invoice numbers after ${month}'s.`;
export const firstLabel = (fy: string) => `First invoice of ${fy}`;

/** Your check: an invoice Tally would renumber others for. */
export const CANT_GO = "Can't go into Tally as it's set up.";
export const ASIDE = 'Put it aside';
export const TODAY = 'Date it today';
export const whyRenumber = (iso: string) =>
  `Your Tally gives invoices new invoice numbers when an older one is added before them. This invoice is dated ${dayMonYear(iso)}, `
  + 'and Tally already has invoices after that date, so adding it with its own date would change their invoice numbers, '
  + 'including ones already sent to CAMS and KFintech. Dated today, it goes in after them and nothing changes. '
  + 'Or put it aside for now.';

/** The end of a run. */
export const ENTER_HEAD = 'Enter these in your books with these invoice numbers';
export const LEFT_HEAD = 'Not sent this run';

/** The books' questions in a run: the one option "yes" reads as a sentence. */
export const optionText = (o: string) => (o === 'yes' ? 'Yes, it is' : o);
