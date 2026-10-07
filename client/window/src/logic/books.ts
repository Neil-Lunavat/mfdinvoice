/* What the window says about the person's books (Tally), all in one place. */

import { dayMonYear } from './format';

/** The red line while a run waits for Tally. */
export const waitingLine = (company: string) => `TallyPrime needs to be open, with ${company}.`;
export const WAITING_SUB = 'The run goes on by itself when Tally answers. Or press Refresh.';

/** Setup's line under Your invoices when Tally is connected. */
export const continuesLine = (next: string) =>
  `Your invoices continue from ${next}. Anything typed into Tally meanwhile is picked up on its own.`;
export const continuesLineNoNext = (company: string) =>
  `Your invoices continue from the last one in ${company}. Anything typed into Tally meanwhile is picked up on its own.`;

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

/** Tally's questions in a run: the one option "yes" reads as a sentence. */
export const optionText = (o: string) => (o === 'yes' ? 'Yes, it is' : o);
