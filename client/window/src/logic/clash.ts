/* The mailbox clash: CAMS sends its invoice mails to the CAMS email. If that email changes
   while the mailbox was the same address, the run would wait in the wrong inbox. So the run won't start until the
   person picks "Change mailbox" or "Keep <old address>". */

const same = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase();

import type { Clash } from '../bridge/types';

export type { Clash };

/** Did this change to the CAMS email leave the mailbox behind? `before` is the details as they were. */
export function clashAfter(
  before: { camsEmail: string; mailbox: { address: string } },
  newCamsEmail: string
): Clash | null {
  if (same(before.camsEmail, newCamsEmail)) return null;
  if (!same(before.mailbox.address, before.camsEmail)) return null;
  return { mailbox: before.mailbox.address, camsEmail: newCamsEmail };
}

/** A one-registrar KFintech run has no CAMS mail to read, so it never waits on the clash. */
export const blocksRun = (clash: Clash | null, registrars: string[]) => !!clash && registrars.includes('CAMS');
