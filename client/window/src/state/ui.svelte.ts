/* Where the person is in the window, and what is open on top. Nothing here comes from the app. */

import type { Invoice, InvoiceSettings, Invoices, ProfileDraft, Registrar, RunKind } from '../bridge';
import type { Clash } from '../logic/clash';

export type Page = 'splash' | 'signin' | 'setup' | 'overview' | 'invoices' | 'downloads' | 'books' | 'settings';
export type Detail = 'who' | 'cams' | 'mb' | 'kf' | 'sig' | 'inv';

export const SECTIONS = ['Connections', 'Your details', 'Your invoices', 'History', 'Account & plan', 'This PC', 'Support', 'Send an idea'] as const;
export type Section = (typeof SECTIONS)[number];

export type Popup =
  | { type: 'support'; where: string }
  | { type: 'edit'; which: Detail }
  | { type: 'invoice'; invoice: Invoice; period: string }
  | { type: 'cams_files'; done: (periods: string[]) => void }
  | { type: 'close_ask' }
  | { type: 'leave_settings'; go: () => void }
  | { type: 'sign_out' }
  | { type: 'consent' }
  | { type: 'trial_started' };

export const blankDraft = (): ProfileDraft => ({
  arn: '', name: '', gstin: '', camsUsed: true, camsEmail: '', camsArn: '',
  mailbox: { provider: 'gmail', address: '', connected: false },
  kfintech: { used: true, username: '', loggedInAs: '', arn: '' },
  signature: { way: 'image', present: false, image: '', size: 100, cert: null },
  invoices: blankInvoices(),
  consent: null,
  ticks: { cams: null, kfintech: null }
});

export const blankSettings = (): InvoiceSettings => ({
  template: 'tally', address: [], phone: '', email: '', website: '', particulars: 'Commission', particularsAmc: true, remarks: ''
});

export const blankInvoices = (): Invoices => ({ source: '', last: '', at: -1, settings: blankSettings() });

class Ui {
  page = $state<Page>('splash');
  invoicesMonth = $state<string | null>(null);          // null: the year's months
  section = $state<Section>('Connections');
  popups = $state<Popup[]>([]);
  menu = $state<'' | 'bell' | 'arn' | 'run' | 'month'>('');        // a small popover, closed by Esc or a click elsewhere
  // the run window is open: for these registrars and this month, as a run, a status check or a download
  runWith = $state<{ registrars: Registrar[]; period: string; what: RunKind; periods?: string[] } | null>(null);   // periods: a download of several months
  month = $state<string | null>(null);                   // the month Overview shows; null: this month
  booksMonth = $state<string | null>(null);              // the month the Books tab opens on; null: the newest
  settingsDirty = $state(false);                         // Your invoices has unsaved changes
  saveSettings: (() => Promise<void>) | null = null;     // how to save them, when leaving asks
  discardSettings: (() => void) | null = null;           // and how to drop them
  clash = $state<Clash | null>(null);                    // the CAMS email moved away from the mailbox; the run waits on it

  // setup
  step = $state(0);
  reached = $state(0);
  returnTo = $state<number | null>(null);                // opened from Check everything's Change
  adding = $state(false);                                // Add ARN, not a first setup
  draft = $state<ProfileDraft>(blankDraft());
  /* What the portals showed at Verify, for the ARN, name and GSTIN step to offer. `version` counts the readings; the step
     takes them once per reading, so what the person has typed over is not put back. */
  read = $state({ cams: '', kf: '', gstin: '', version: 0, taken: 0 });

  go(p: Page) {
    if (this.page === 'settings' && p !== 'settings' && this.settingsDirty) {
      this.open({ type: 'leave_settings', go: () => { this.settingsDirty = false; this.go(p); } });
      return;
    }
    this.menu = '';
    if (p === 'invoices' && this.page !== 'invoices') this.invoicesMonth = null;
    this.page = p;
  }

  goSection(s: Section) {
    if (this.settingsDirty && s !== this.section) {
      this.open({ type: 'leave_settings', go: () => { this.settingsDirty = false; this.section = s; } });
      return;
    }
    this.section = s;
  }

  open(p: Popup) { this.menu = ''; this.popups = [...this.popups, p]; }
  close() { this.popups = this.popups.slice(0, -1); }
  get top(): Popup | null { return this.popups.at(-1) ?? null; }

  startSetup(adding: boolean) {
    this.adding = adding;
    this.step = 0;
    this.reached = 0;
    this.returnTo = null;
    this.draft = blankDraft();
    this.read = { cams: '', kf: '', gstin: '', version: 0, taken: 0 };
    this.page = 'setup';
  }
}

export const ui = new Ui();
