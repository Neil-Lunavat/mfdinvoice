/* Letting Zoho Books in: Zoho's Accept page opens in the person's own browser, and the software waits (up to five
   minutes). Then the organisations are read, each with its GSTIN beside this ARN's. Used by setup, Settings and the
   Books tab. */

import { app, type ZohoOrg } from '../bridge';

export type Connected = { ok: true; orgs: ZohoOrg[] } | { ok: false; said: string; cancelled: boolean };

export async function connectZoho(arn: string, gstin: string): Promise<Connected> {
  const r = await app.zohoConnect(arn);
  if (!r.ok) return { ok: false, said: r.said, cancelled: r.state === 'cancelled' };
  const look = await app.booksSetup({ kind: 'zoho', gstin, arn });
  if (look.state !== 'ready') return { ok: false, said: look.said || "Zoho Books isn't answering.", cancelled: false };
  if (!look.orgs.length) return { ok: false, said: 'There is no organisation in this Zoho Books login.', cancelled: false };
  return { ok: true, orgs: look.orgs };
}
