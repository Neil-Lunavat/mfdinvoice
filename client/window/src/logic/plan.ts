/* The account's plan, in the window's words. The website says what the plan is (`Snapshot.plan`); this only decides
   what to draw. Nothing here sells or prices anything, and a plan given as a gift is just a plan: the window may say
   "trial", never "gift" or "beta". */

import type { Plan } from '../bridge/types';
import { dayMon, dayMonYear } from './format';

/** What Overview shows instead of the month: the free trial to activate, the plain screen of a plan that ended, an
    ARN that is set up here but not on the plan (`unbound`), or nothing (the month as usual). An ARN set up without
    KFintech is bound by its first run (`bindOnRun`): with a plan running it just runs; with none, once Activate free
    trial has been pressed (`bindAsked`). */
export function planScreen(p: Plan | null, arn = '', prof?: { bindOnRun?: boolean; bindAsked?: boolean } | null): 'activate' | 'ended' | 'unbound' | null {
  if (!p) return null;
  if (p.state === 'ended') return 'ended';
  if (p.state === 'none') return prof?.bindOnRun && prof.bindAsked ? null : 'activate';
  if (p.state === 'active' && arn && !p.arns.includes(arn)) return prof?.bindOnRun ? null : 'unbound';
  return null;
}

/** Every slot on the plan is taken, and every ARN on it is set up on this PC: another ARN needs another slot. */
export const noFreeSlot = (p: Plan | null, here: string[]) =>
  !!p && p.state === 'active' && p.arns.length >= p.slots && p.arns.every(a => here.includes(a));

/** The plan in one line, for the sidebar's foot and Settings › Account & plan. */
export function planLine(p: Plan | null): string {
  if (!p) return '';
  switch (p.state) {
    case 'active': return p.source === 'trial' ? `Free trial · last day ${dayMon(p.until)}` : p.until ? `Plan · until ${dayMonYear(p.until)}` : 'Plan';
    case 'ended': return `${p.source === 'trial' ? 'Free trial' : 'Plan'} ended ${dayMonYear(p.until)}`;
    case 'none': return 'No plan yet';
    case 'unknown': return "Couldn't check your plan just now";
  }
}

/** Run turns off while the plan can't be read, or there is none to run on. */
export const planBlocksRun = (p: Plan | null, arn = '') => !!p && (p.state === 'unknown' || planScreen(p, arn) !== null);
