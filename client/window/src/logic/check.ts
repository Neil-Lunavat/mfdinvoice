/* Your check: which rows are ticked, and what Submit's count and total say. Both registrars take part of a month,
   so any row on either can be unticked. A blocked row (one this run cannot send) is never ticked. */

import type { CheckRow, Registrar } from '../bridge/types';
import { sum } from './format';

export const rowTotal = (r: CheckRow) => sum([r.taxable, r.gst]);

/** The keys ticked when Your check opens: everything, except what was left out last time and what is blocked. */
export const initialTicks = (rows: CheckRow[]) => new Set(rows.filter(r => r.included && !r.blocked).map(r => r.key));

export function toggle(ticked: Set<string>, row: CheckRow): Set<string> {
  const next = new Set(ticked);
  if (next.has(row.key)) next.delete(row.key); else if (!row.blocked) next.add(row.key);
  return next;
}

export interface CheckSums {
  count: number;
  byRegistrar: Record<Registrar, number>;
  taxable: number;
  gst: number;
  total: number;
}

export function sums(rows: CheckRow[], ticked: Set<string>): CheckSums {
  const kept = rows.filter(r => ticked.has(r.key));
  return {
    count: kept.length,
    byRegistrar: {
      CAMS: kept.filter(r => r.registrar === 'CAMS').length,
      KFINTECH: kept.filter(r => r.registrar === 'KFINTECH').length
    },
    taxable: sum(kept.map(r => r.taxable)),
    gst: sum(kept.map(r => r.gst)),
    total: sum(kept.map(rowTotal))
  };
}

/** What goes back to the app: the ticked keys, in the order they were offered. */
export const included = (rows: CheckRow[], ticked: Set<string>) => rows.filter(r => ticked.has(r.key)).map(r => r.key);

/** The own invoices' numbers as the ticks stand: an invoice that already holds its number keeps it; the other ticked
    ones, in the run's number order, take the run's numbers from the first, so the ticked ones have no gap; an unticked
    one has none. What the run gives them when Submit is pressed. Nothing on the registrar's path. */
export function numbersFor(rows: CheckRow[], ticked: Set<string>): Record<string, string> {
  const flowing = rows.filter(r => r.seq !== undefined && !r.kept).sort((a, b) => a.seq! - b.seq!);
  const pool = flowing.map(r => r.number);
  const out: Record<string, string> = {};
  for (const r of rows) if (r.kept && ticked.has(r.key)) out[r.key] = r.number;
  let i = 0;
  for (const r of flowing) if (ticked.has(r.key)) out[r.key] = pool[i++];
  return out;
}

/** Submit is on only with the consent tick and at least one invoice ticked. */
export const canSubmit = (s: CheckSums, agreed: boolean) => agreed && s.count > 0;

/** Rows grouped by registrar, CAMS first, as the table draws them. */
export function groups(rows: CheckRow[]): { registrar: Registrar; rows: CheckRow[] }[] {
  return (['CAMS', 'KFINTECH'] as const)
    .map(registrar => ({ registrar, rows: rows.filter(r => r.registrar === registrar) }))
    .filter(g => g.rows.length);
}
