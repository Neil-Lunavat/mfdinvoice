/* DEV ONLY (a checkout's window, `uv run app`): the dev panel's calls to the Python side (hands/devtools.py).
   Kept apart from bridge/types.ts: the `App` interface the build uses knows none of this. */

import type { InvoiceSettings, Invoices, ProfileDraft } from '../bridge/types';

export interface DevState { submit: boolean; showBrowser: boolean; states: string[]; configured: string[] }
export type DevResult = { ok: boolean; said?: string };

/** Setup's draft as filled from [dev]; the signature's photo comes as `signatureImage`, settings partly (merged with the blanks). */
export type DevDraft = Omit<ProfileDraft, 'signature' | 'invoices'> & {
  signatureImage: string;
  invoices: Omit<Invoices, 'settings'> & { settings: Partial<InvoiceSettings> };
};
export type DevDraftResult = { ok: true; draft: DevDraft } | { ok: false; said: string };

interface PyApi { call(method: string, args?: unknown[]): Promise<unknown> }

async function call<T>(method: string, ...args: unknown[]): Promise<T> {
  const api = (window as unknown as { pywebview?: { api: PyApi } }).pywebview?.api;
  if (!api) throw new Error('no app behind the window');
  return (await api.call(method, args)) as T;
}

export const dev = {
  state: () => call<DevState>('devState'),
  set: (v: { submit?: boolean; showBrowser?: boolean }) => call<DevState>('devSet', v),
  backToSetup: () => call<DevResult>('devBackToSetup'),
  fill: () => call<DevResult>('devFill'),
  draft: () => call<DevDraftResult>('devDraft'),
  save: (name: string) => call<DevResult>('devSaveState', name),
  load: (name: string) => call<DevResult>('devLoadState', name),
  remove: (name: string) => call<DevResult>('devDeleteState', name),
};
