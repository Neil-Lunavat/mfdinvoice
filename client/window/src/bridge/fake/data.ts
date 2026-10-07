/* The fake app's sample data, from docs/prototype/data.js. Today is 9 October 2026. Totals are always computed. */

import type { ActivityEntry, Invoice, Month, MonthRow, Note, Profile, Registrar, Status } from '../types';
import { NAME } from '../../brand';

export const TODAY = '2026-10-09';
export const CHECKED = '2026-10-09T09:12:00';

// [fund house, registrar, taxable, igst?]
const ROWS: [string, Registrar, number, boolean?][] = [
  ['Aditya Birla Sun Life', 'CAMS', 21480.35], ['Axis', 'KFINTECH', 16840.0], ['Bandhan', 'CAMS', 8264.7],
  ['Bank of India', 'KFINTECH', 4312.18], ['DSP', 'CAMS', 12604.45], ['Franklin Templeton', 'CAMS', 10998.62, true],
  ['HDFC', 'CAMS', 40856.0], ['ICICI Prudential', 'CAMS', 33592.27], ['Invesco', 'KFINTECH', 7998.31],
  ['JM Financial', 'KFINTECH', 5406.9], ['Kotak Mahindra', 'CAMS', 14660.44], ['Mahindra Manulife', 'CAMS', 6120.08],
  ['Nippon India', 'KFINTECH', 22440.0], ['Quant', 'KFINTECH', 9118.56], ['SBI', 'CAMS', 28915.0],
  ['Tata', 'CAMS', 8400.42], ['WhiteOak Capital', 'CAMS', 4104.73]
];

const r2 = (n: number) => Math.round(n * 100) / 100;

function invoice(amc: string, registrar: Registrar, taxable: number, igst: boolean, i: number, date: string): Invoice {
  const half = r2(taxable * 0.09);
  const key = registrar === 'CAMS' ? `BM/26-27/E/${5 + i}` : String(128260801030896 + i);
  return {
    key, registrar, amc, number: key, date, taxable,
    cgst: igst ? 0 : half, sgst: igst ? 0 : half, igst: igst ? r2(taxable * 0.18) : 0,
    status: 'Not submitted', said: '', rejection: '', timeline: [], gstin: '27AAATB0102C1ZR', tally: ''
  };
}

/** October's invoices for R. K. Mehta (17) or S. R. Mehta (12, smaller). */
export function octoberInvoices(second = false): Invoice[] {
  const all = ROWS.map((r, i) => invoice(r[0], r[1], r[2], !!r[3], i, '2026-09-30'));
  if (!second) return all;
  return [0, 2, 4, 6, 7, 10, 14, 15, 1, 8, 12, 13]
    .map(k => all[k])
    .map(x => { const t = r2(x.taxable * 0.55); return { ...invoice(x.amc, x.registrar, t, x.igst > 0, ROWS.findIndex(r => r[0] === x.amc), x.date) }; })
    .sort((a, b) => a.amc.localeCompare(b.amc));
}

export const REJECTION = 'Invoice date is before the brokerage month.';

const said: Partial<Record<Status, string>> = {
  'Waiting approval': 'PENDING', Approved: 'APPROVED', Rejected: 'REJECTED', Submitted: 'PENDING'
};
const kfSaid: Partial<Record<Status, string>> = {
  'Waiting approval': 'Pending for Approval', Approved: 'Accepted & Payment pending', Rejected: 'Rejected'
};

/** Set an invoice's status the way the app's local store would have it, with its timeline. */
export function withStatus(x: Invoice, status: Status, submitted = '2026-10-03', who = 'you, on this PC'): Invoice {
  if (status === 'Not submitted') return { ...x, status, said: '', rejection: '', timeline: [] };
  const tl: Invoice['timeline'] = [
    { what: 'Fetched', when: submitted }, { what: 'Signed', when: submitted }, { what: 'Checked', when: submitted },
    { what: 'Submitted', when: submitted, who }
  ];
  if (status === 'Approved') tl.push({ what: 'Approved', when: '2026-10-07' });
  if (status === 'Rejected') tl.push({ what: 'Rejected', when: '2026-10-08' });
  if (status === 'Waiting approval') tl.push({ what: 'Waiting approval', when: '' });
  return {
    ...x, status, timeline: tl,
    said: (x.registrar === 'CAMS' ? said : kfSaid)[status] ?? status,
    rejection: status === 'Rejected' ? REJECTION : ''
  };
}

export type MonthState = 'first_run' | 'stopped' | 'not_listed' | 'not_fetched' | 'to_do' | 'partly' | 'submitted' | 'rejected' | 'approved';

export function october(state: MonthState, second = false): Month {
  const base = octoberInvoices(second);
  const m: Month = {
    period: 'OCT-2026', label: 'October 2026', kfLabel: 'September 2026', deadline: '2026-10-15',
    checkedAt: CHECKED, listed: true, notListed: [], everRun: true, submittedOn: '', lastRun: null, invoices: base
  };
  const stopped = (said: string, code: string, portal = ''): Month['lastRun'] => ({ how: 'stopped', at: '2026-10-08T10:04:00', said, portal, code });
  switch (state) {
    case 'first_run': return { ...m, everRun: false, listed: false, checkedAt: '', invoices: [] };
    case 'stopped': return { ...m, listed: false, invoices: [], lastRun: stopped('Something on our side needs fixing', 'internal') };
    case 'not_listed': return { ...m, listed: false, invoices: [], lastRun: stopped('The portal is not responding', 'portal_empty', 'No Invoice Number Found.') };
    case 'not_fetched': return { ...m, listed: false, invoices: [] };
    case 'to_do': return m;
    case 'partly': return { ...m, submittedOn: '2026-10-03', invoices: base.map(x => x.registrar === 'CAMS' ? withStatus(x, 'Waiting approval') : x) };
    case 'submitted': return { ...m, submittedOn: '2026-10-03', invoices: base.map(x => withStatus(x, 'Waiting approval')) };
    case 'rejected': return {
      ...m, submittedOn: '2026-10-03',
      invoices: base.map(x => withStatus(x, x.amc === 'Axis' ? 'Rejected' : x.amc === 'Invesco' || x.amc === 'Quant' ? 'Waiting approval' : 'Approved'))
    };
    case 'approved': return { ...m, submittedOn: '2026-10-03', invoices: base.map(x => withStatus(x, 'Approved')) };
  }
}

const EARLIER: [string, string, number][] = [
  ['SEP-2026', 'September 2026', 248110.0], ['AUG-2026', 'August 2026', 239660.08], ['JUL-2026', 'July 2026', 252377.91],
  ['JUN-2026', 'June 2026', 229105.33], ['MAY-2026', 'May 2026', 244812.7], ['APR-2026', 'April 2026', 231940.12]
];

/** An earlier month: every invoice approved, the amounts scaled to that month's total. */
export function earlier(period: string, second = false): Month {
  const idx = EARLIER.findIndex(x => x[0] === period) + 1, [, label, target] = EARLIER[idx - 1];
  const full = octoberInvoices(false).reduce((s, x) => s + x.taxable + x.cgst + x.sgst + x.igst, 0);
  const mm = String(10 - idx).padStart(2, '0'), prev = String(9 - idx).padStart(2, '0');
  const invoices = octoberInvoices(second).map((x, i) => {
    const t = r2(x.taxable * target / full), igst = x.igst > 0, half = r2(t * 0.09);
    const key = x.registrar === 'CAMS' ? `BM/26-27/${String.fromCharCode(65 + idx)}/${5 + i}` : String(128260801030896 - idx * 100 + i);
    return withStatus({ ...x, key, number: key, date: `2026-${prev}-28`, taxable: t, cgst: igst ? 0 : half, sgst: igst ? 0 : half, igst: igst ? r2(t * 0.18) : 0 },
      'Approved', `2026-${mm}-04`, 'OFFICE-PC');
  });
  return {
    period, label, kfLabel: EARLIER[idx]?.[1] ?? 'March 2026', deadline: `2026-${mm}-15`,
    checkedAt: CHECKED, listed: true, notListed: [], everRun: true, submittedOn: `2026-${mm}-04`,
    lastRun: { how: 'done', at: `2026-${mm}-04T10:20:00`, said: '', portal: '', code: '' }, invoices
  };
}

export function yearRows(oct: Month, second = false): MonthRow[] {
  const tot = (m: Month) => r2(m.invoices.reduce((s, x) => s + x.taxable + x.cgst + x.sgst + x.igst, 0));
  const rej = oct.invoices.filter(x => x.status === 'Rejected').length;
  const status: MonthRow['status'] = rej ? 'Rejected'
    : oct.invoices.length && oct.invoices.every(x => x.status === 'Approved') ? 'Approved'
    : oct.invoices.some(x => x.status === 'Waiting approval') ? 'Submitted' : 'Not submitted';
  const rows: MonthRow[] = [{ period: oct.period, label: oct.label, count: oct.invoices.length, total: tot(oct), status, rejected: rej }];
  for (const [period, label] of EARLIER) {
    const m = earlier(period, second);
    rows.push({ period, label, count: m.invoices.length, total: tot(m), status: 'Approved', rejected: 0 });
  }
  return rows;
}

export const RK: Omit<Profile, 'signature'> = {
  arn: 'ARN-104512', name: 'R. K. Mehta', gstin: '27ABCPM1234F1Z3', arnConfirmed: true, camsUsed: true,
  camsEmail: 'rkmehta@gmail.com', camsArn: 'ARN-104512',
  mailbox: { provider: 'gmail', address: 'rkmehta@gmail.com', connected: true },
  kfintech: { used: true, username: 'rkmehta_dss', loggedInAs: 'R K MEHTA', arn: 'ARN-104512' },
  invoices: { source: 'own', last: 'RKM/26-27/073', at: 10, settings: {
    template: 'tally', address: ['12, Shanti Kunj, College Road', 'Nashik 422005'], phone: '98220 12345',
    email: 'rkmehta@gmail.com', website: '', particulars: 'Commission', particularsAmc: true, remarks: '' } },
  lastLogin: { CAMS: '2026-10-03', KFINTECH: '2026-10-03' }, tally: { company: 'Lunavat & Co', ledgers: 17 },
  consent: { version: 1, text: `I authorise ${NAME} to sign in and act for me on CAMS and KFintech for ARN-104512.`, at: '2026-06-02T10:14:00', device: 'THIS-PC' }
};

export const SR: Omit<Profile, 'signature'> = {
  arn: 'ARN-118830', name: 'S. R. Mehta', gstin: '27AAKPM5678K1ZY', arnConfirmed: true, camsUsed: true,
  camsEmail: 'srmehta.mfd@gmail.com', camsArn: 'ARN-118830',
  mailbox: { provider: 'gmail', address: 'srmehta.mfd@gmail.com', connected: true },
  kfintech: { used: true, username: 'srmehta_mfd', loggedInAs: 'S R MEHTA', arn: 'ARN-118830' },
  invoices: { source: 'registrar', last: '', at: -1, settings: {
    template: 'tally', address: [], phone: '', email: '', website: '', particulars: 'Commission', particularsAmc: true, remarks: '' } },
  lastLogin: { CAMS: '2026-09-04', KFINTECH: '2026-09-04' }, tally: { company: '', ledgers: 0 },
  consent: { version: 1, text: `I authorise ${NAME} to sign in and act for me on CAMS and KFintech for ARN-118830.`, at: '2026-08-11T16:40:00', device: 'THIS-PC' }
};

export function notes(state: MonthState): Note[] {
  const n: Note[] = [];
  if (state === 'rejected') n.push({ id: 'n4', kind: 'rejected', text: 'Axis rejected an invoice.', detail: `KFintech says: “${REJECTION}”`, opens: 'invoices', when: '2026-10-08T09:15:00', read: false });
  if (state === 'rejected' || state === 'approved') n.push({ id: 'n3', kind: 'approved', text: '14 invoices approved.', detail: 'CAMS 11 · KFintech 3', opens: 'invoices', when: '2026-10-07T09:12:00', read: true });
  if (state !== 'first_run' && state !== 'not_listed' && state !== 'to_do') n.push({ id: 'n2', kind: 'run_done', text: '17 invoices submitted for October.', detail: 'Approval usually takes 3–7 days.', opens: 'overview', when: '2026-10-03T10:10:00', read: true });
  if (state !== 'first_run' && state !== 'not_listed') n.push({ id: 'n1', kind: 'listed', text: "October's invoices are listed.", detail: "CAMS 11 · KFintech 6. Run October when you're ready.", opens: 'overview', when: '2026-10-02T09:00:00', read: true });
  return n;
}

const a = (at: string, text: string, registrar: Registrar | null = null, who = '', tone: ActivityEntry['tone'] = 'plain'): ActivityEntry =>
  ({ at, text, registrar, who, tone });

export function activity(state: MonthState): ActivityEntry[] {
  const sep = [
    a('2026-09-02T12:05:00', 'Mailbox connected: rkmehta@gmail.com', null, 'OFFICE-PC', 'setting'),
    a('2026-09-04T10:11:00', 'Started the run for September', null, 'OFFICE-PC'),
    a('2026-09-04T10:13:00', 'Signed 17 invoices'),
    a('2026-09-04T10:19:00', 'Approved 17 invoices for ₹2,48,110.00', null, 'OFFICE-PC'),
    a('2026-09-04T10:20:00', 'Submitted 11', 'CAMS'), a('2026-09-04T10:20:00', 'Submitted 6', 'KFINTECH'),
    a('2026-09-10T09:30:00', 'All 17 approved for September')
  ];
  const oct = state === 'first_run' || state === 'not_listed' || state === 'to_do' ? [] : [
    a('2026-10-03T10:02:00', 'Started the run for October', null, 'you, on this PC'),
    a('2026-10-03T10:03:00', 'Signed in to CAMS', 'CAMS'), a('2026-10-03T10:03:00', 'Signed in to KFintech', 'KFINTECH'),
    a('2026-10-03T10:05:00', 'Got 6 invoices', 'KFINTECH'), a('2026-10-03T10:06:00', 'Got 11 invoices by email (ref 224851745)', 'CAMS'),
    a('2026-10-03T10:07:00', 'Signed 17 invoices'),
    a('2026-10-03T10:08:00', '17 of 17 matched what CAMS and KFintech show'),
    a('2026-10-03T10:09:00', 'Approved 17 invoices for ₹4,23,583.43', null, 'you, on this PC'),
    a('2026-10-03T10:09:00', 'Submitted 11', 'CAMS'), a('2026-10-03T10:10:00', 'Submitted 6', 'KFINTECH'),
    a('2026-10-06T17:40:00', 'Mailbox changed to rkmehta@gmail.com', null, 'you, on this PC', 'setting'),
    ...(state === 'rejected' || state === 'approved' ? [a('2026-10-07T09:12:00', 'CAMS approved 11 invoices', 'CAMS'), a('2026-10-07T09:12:00', 'KFintech approved 3 invoices', 'KFINTECH')] : []),
    ...(state === 'rejected' ? [a('2026-10-08T09:15:00', `Axis rejected 128260801030897: “${REJECTION}”`, 'KFINTECH', '', 'bad')] : [])
  ];
  return [...sep, ...oct].reverse();
}

/** A survey from the panel, as /api/app/me brings it. */
export const SURVEY = {
  id: 1, title: 'Your first month',
  questions: [
    { key: 'q1', q: 'How did your first month with MFDInvoice go?', type: 'one' as const, options: ['Smoothly', 'A few bumps', 'It was hard'], other: false },
    { key: 'q2', q: 'Which of these would you use?', type: 'many' as const, options: ['Download several months at once', 'Zoho Books', 'A reminder when invoices are listed'], other: true },
    { key: 'q3', q: 'What one thing should we change?', type: 'text' as const, options: [], other: false }
  ]
};
