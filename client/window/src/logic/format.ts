/* Numbers and dates as the person already writes them: Indian grouping, day month year, 24-hour clock. */

import type { Registrar } from '../bridge/types';

const r2 = (n: number) => Math.round(n * 100) / 100;

export const n2 = (n: number) => r2(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const inr = (n: number) => '₹' + n2(n);
export const sum = (xs: number[]) => r2(xs.reduce((a, b) => a + b, 0));

export const regName = (r: Registrar) => (r === 'CAMS' ? 'CAMS' : 'KFintech');
export const regTag = (r: Registrar) => (r === 'CAMS' ? 'CAMS' : 'KFIN');

export function ordinal(n: number): string {
  const t = n % 100;
  if (t >= 11 && t <= 13) return n + 'th';
  return n + ({ 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] ?? 'th');
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

const parse = (iso: string) => new Date(iso.length === 10 ? iso + 'T00:00:00' : iso);

/** "3 Oct" */
export const dayMon = (iso: string) => { const d = parse(iso); return `${d.getDate()} ${MONTHS[d.getMonth()].slice(0, 3)}`; };
/** "30 Sep 2026" */
export const dayMonYear = (iso: string) => { const d = parse(iso); return `${dayMon(iso)} ${d.getFullYear()}`; };
/** "3 October" */
export const dayMonth = (iso: string) => { const d = parse(iso); return `${d.getDate()} ${MONTHS[d.getMonth()]}`; };
/** "09:12" */
export const hhmm = (iso: string) => { const d = parse(iso); return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; };
export const monthName = (iso: string) => MONTHS[parse(iso).getMonth()];

export function sameDay(a: string, b: string) {
  const x = parse(a), y = parse(b);
  return x.getFullYear() === y.getFullYear() && x.getMonth() === y.getMonth() && x.getDate() === y.getDate();
}

/** "Checked today 09:12" / "Checked 7 Oct, 09:12" */
export function checkedLine(checkedAt: string, today: string) {
  if (!checkedAt) return 'Not checked yet';
  return sameDay(checkedAt, today) ? `Checked today ${hhmm(checkedAt)}` : `Checked ${dayMon(checkedAt)}, ${hhmm(checkedAt)}`;
}

export function daysBetween(fromIso: string, toIso: string) {
  const a = parse(fromIso.slice(0, 10)), b = parse(toIso.slice(0, 10));
  return Math.round((b.getTime() - a.getTime()) / 86_400_000);
}

/** "6 days to the 15th". Never red, never a banner. */

/** "0:42", "12:05" */
export const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

/** r•••@gmail.com */
export function maskEmail(a: string) {
  const [u, d] = a.split('@');
  return (u?.[0] ?? '') + '•••@' + (d ?? '');
}
