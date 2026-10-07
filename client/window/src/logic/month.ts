/* The month as Overview and Invoices show it, worked out from the invoices the local store holds.
   "Nothing counted before it's fetched": no count or amount appears until an invoice is in the store. */

import type { Invoice, Month, Registrar, Status } from '../bridge/types';
import { sum } from './format';

export const total = (x: Invoice) => sum([x.taxable, x.cgst, x.sgst, x.igst]);
export const gst = (x: Invoice) => sum([x.cgst, x.sgst, x.igst]);
export const totalOf = (xs: Invoice[]) => sum(xs.map(total));

const APPROVED: Status[] = ['Approved'];
const WAITING: Status[] = ['Submitted', 'Waiting approval'];

export const isApproved = (x: Invoice) => APPROVED.includes(x.status);
export const isWaiting = (x: Invoice) => WAITING.includes(x.status);
export const isRejected = (x: Invoice) => x.status === 'Rejected';
/** With the registrar: submitted, waiting or approved. A rejection is not: it comes back to be fixed. */
export const isWithRegistrar = (x: Invoice) => isApproved(x) || isWaiting(x);
/** Still to be sent by a run. */
export const isOpen = (x: Invoice) => !isWithRegistrar(x) && !isRejected(x);

/* The month card's states. Every state with nothing fetched yet offers Run: only a run reads what the registrars have
   (Check status reads CAMS's status page, which lists an invoice only once it has been uploaded), so a month card that
   offered only "Check now" could never be got going again. That was the 25 Sep demo: a first run crashed before it
   fetched anything, and Overview had no Run button left.

     first_run    never run, nothing fetched
     stopped      nothing fetched, and this month's last run stopped: say what happened, run again
     not_listed   nothing fetched, and the last look (a run or a check) found the registrars list nothing yet
     not_fetched  nothing fetched, and nobody has run this month yet (a new month, after earlier ones)
     to_do · partly · submitted · approved    from the invoices themselves */
export type CardState = 'first_run' | 'stopped' | 'not_listed' | 'not_fetched' | 'to_do' | 'partly' | 'submitted' | 'approved';

export interface Card {
  state: CardState;
  count: number;
  total: number;
  open: number;
  openTotal: number;
  sent: number;           // with the registrar
  approved: number;
  waiting: number;
  rejected: number;
  byRegistrar: Record<Registrar, number>;
  canRun: boolean;        // the month card offers Run (Run can still be off for a hard day)
  lastStopped: string;    // this month's last run stopped: its heading, else ''
  /** Rejections, when they are all that is left to send: the button says "Run the 3 rejected again". A run takes
      every invoice the registrars do not have, so it takes these. Empty otherwise. */
  rerun: { keys: string[]; registrars: Registrar[] };
}

const RUNNABLE: CardState[] = ['first_run', 'stopped', 'not_listed', 'not_fetched', 'to_do', 'partly'];

export function card(m: Month): Card {
  const xs = m.invoices, open = xs.filter(isOpen);
  const approved = xs.filter(isApproved).length, waiting = xs.filter(isWaiting).length, rejected = xs.filter(isRejected).length;
  const sent = approved + waiting;
  const last = m.lastRun ?? null;
  const stopped = last?.how === 'stopped';
  const unlisted = stopped ? last!.code === 'not_listed' : !m.listed && m.notListed.length > 0;
  const state: CardState =
    !xs.length ? (
      unlisted ? 'not_listed'
        : !m.everRun ? 'first_run'
        : stopped ? 'stopped'
        : 'not_fetched')
      : sent === 0 && rejected === 0 ? 'to_do'
      : open.length ? 'partly'
      : approved === xs.length ? 'approved'
      : 'submitted';
  return {
    state, count: xs.length, total: totalOf(xs), open: open.length, openTotal: totalOf(open),
    sent, approved, waiting, rejected,
    byRegistrar: { CAMS: xs.filter(x => x.registrar === 'CAMS').length, KFINTECH: xs.filter(x => x.registrar === 'KFINTECH').length },
    canRun: RUNNABLE.includes(state),
    // "not listed yet" is over once the month's invoices are here
    lastStopped: stopped && !(last!.code === 'not_listed' && xs.length) ? last!.said || 'The run stopped' : '',
    rerun: rejected && !RUNNABLE.includes(state)
      ? { keys: xs.filter(isRejected).map(x => x.key),
          registrars: (['CAMS', 'KFINTECH'] as Registrar[]).filter(r => xs.some(x => isRejected(x) && x.registrar === r)) }
      : { keys: [], registrars: [] }
  };
}

/** How far an invoice has come, on the five dots: Fetched · Signed · Checked · Submitted · Approved. */
const PROGRESS: Record<Status, number> = {
  'Not submitted': 0, Mismatch: 0, 'Needs your attention': 0, Fetched: 1, Signed: 2, Checked: 3,
  Submitted: 4, 'Waiting approval': 4, Rejected: 4, Approved: 5
};

export interface RegistrarCard {
  registrar: Registrar;
  count: number;
  total: number;
  on: number;                                    // dots lit
  bad: boolean;                                  // the last dot is a rejection
  chip: { text: string; tone: 'neutral' | 'wait' | 'good' | 'bad' };
}

export function registrarCard(m: Month, registrar: Registrar): RegistrarCard {
  const xs = m.invoices.filter(x => x.registrar === registrar);
  const rejected = xs.filter(isRejected).length;
  const on = xs.length ? Math.min(...xs.map(x => PROGRESS[x.status])) : 0;
  const chip: RegistrarCard['chip'] =
    rejected ? { text: `${rejected} rejected`, tone: 'bad' }
      : xs.length && xs.every(isApproved) ? { text: 'Approved', tone: 'good' }
      : xs.length && xs.every(isWithRegistrar) ? { text: 'Waiting approval', tone: 'wait' }
      : xs.some(isWithRegistrar) ? { text: `${xs.filter(isWithRegistrar).length} of ${xs.length} submitted`, tone: 'wait' }
      : { text: 'Not submitted', tone: 'neutral' };
  return { registrar, count: xs.length, total: totalOf(xs), on: rejected ? 4 : on, bad: rejected > 0, chip };
}

export const rejections = (m: Month) => m.invoices.filter(isRejected);

export const chipTone = (s: Status): 'neutral' | 'wait' | 'good' | 'bad' =>
  isApproved({ status: s } as Invoice) ? 'good'
    : s === 'Rejected' || s === 'Mismatch' || s === 'Needs your attention' ? 'bad'
    : WAITING.includes(s) ? 'wait'
    : 'neutral';

// --- the month's table on Invoices --------------------------------------------------------------------------------

export type SortKey = 'amc' | 'number' | 'taxable' | 'gst' | 'total' | 'status';
export interface TableQuery { registrar: 'All' | Registrar; status: 'All' | Status; q: string; sort: SortKey; dir: 1 | -1 }

export const blankQuery = (): TableQuery => ({ registrar: 'All', status: 'All', q: '', sort: 'number', dir: 1 });

export function table(xs: Invoice[], t: TableQuery): Invoice[] {
  const q = t.q.trim().toLowerCase();
  const key: Record<SortKey, (x: Invoice) => string | number> = {
    amc: x => x.amc.toLowerCase(), number: x => xs.indexOf(x), taxable: x => x.taxable, gst, total, status: x => x.status
  };
  return xs
    .filter(x => (t.registrar === 'All' || x.registrar === t.registrar) && (t.status === 'All' || x.status === t.status)
      && (!q || `${x.amc} ${x.number} ${x.key}`.toLowerCase().includes(q)))
    .sort((a, b) => {
      const ka = key[t.sort](a), kb = key[t.sort](b);
      return (ka > kb ? 1 : ka < kb ? -1 : 0) * t.dir;
    });
}

/** The statuses present, in the order the filter shows them. The status filter appears only when there are two or more. */
export function statusesIn(xs: Invoice[]): Status[] {
  const order: Status[] = ['Approved', 'Waiting approval', 'Submitted', 'Rejected', 'Mismatch', 'Needs your attention', 'Checked', 'Signed', 'Fetched', 'Not submitted'];
  return order.filter(s => xs.some(x => x.status === s));
}
