/* When Run, Check now and Check status are off. One place, so Overview and a month's invoices grey out together. */

import type { Profile, Snapshot } from '../bridge/types';
import { consentCurrent } from './consent';
import { nextInvoice } from './details';
import { opening } from './opening';
import { planBlocksRun } from './plan';

export interface Missing { text: string; fix: string; which: 'sig' | 'mb' | 'inv' }

/** What this ARN still lacks before it can run. With books connected the books give the invoice numbers, so there is
    no last number to be missing. */
export function missingOf(p: Profile): Missing[] {
  return [
    !p.signature.present && { text: 'Signature missing', fix: 'Add signature', which: 'sig' as const },
    p.camsUsed && !p.mailbox.connected && { text: 'Mailbox not connected', fix: 'Connect mailbox', which: 'mb' as const },
    p.invoices.source === 'own' && !p.books && !nextInvoice(p.invoices) && { text: 'Your last invoice number is missing', fix: 'Add it', which: 'inv' as const }
  ].filter((x): x is Missing => !!x);
}

export function runOffOf(s: Snapshot): boolean {
  const p = s.profile;
  if (!p) return true;
  const banner = opening({ updateRequired: !!s.update, condition: s.condition, signedIn: !!s.account, hasArn: s.arns.length > 0 }).banner;
  return !!banner || missingOf(p).length > 0 || planBlocksRun(s.plan, s.arn) || !consentCurrent(p.consent);
}
