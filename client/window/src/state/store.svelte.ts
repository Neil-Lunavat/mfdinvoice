/* The window's state: what the app has told it, kept as it arrives. Screens read from here and redraw by themselves.
   The window renders from this straight away and never waits on the network: the app answers `load` from disk, and
   pushes whatever changes afterwards. */

import { app, type Ask, type Entered, type Left, type Push, type Registrar, type RunKind, type Snapshot, type StepView, type Stop, type UpdateFailure } from '../bridge';
import { SECTIONS, ui, type Page, type Section } from './ui.svelte';

type CaptchaAsk = Extract<Ask, { type: 'captcha' }>;
type PinAsk = Extract<Ask, { type: 'pin' }>;

export interface RunLive {
  id: string;
  what: RunKind;
  period: string;
  registrars: Registrar[];
  steps: StepView[];
  startedAt: number;                            // when the run window began it, for the clock
  ask: Ask | null;                              // the question on screen, if any
  waitingEmail: { since: string; ref: string; skip: boolean; months?: string[] } | null;
  waitingBooks: { company: string; said: string; kind: string } | null;    // the run waits for the books to answer
  month?: { period: string; index: number };    // a download of several months: the one it is on
  submitted: Partial<Record<Registrar, number>>;
  ended: 'done' | 'stopped' | 'nothing' | null;
  stop: Stop | null;                            // why it stopped, when it did by itself
  used: string;                                 // own invoices: "Used 74/26-27 to 78/26-27", '' when none
  enter: Entered[];                             // own invoices without books, submitted: to enter in their books
  left: Left[];                                 // own invoices the books would not take this run
  summary: string;                              // the app's one line about how it ended
  total: number;                                // what was submitted, with GST
  stopAsked: boolean;                           // the person pressed Stop
}

class Store {
  snap = $state<Snapshot | null>(null);
  run = $state<RunLive | null>(null);
  setupCaptcha = $state<CaptchaAsk | null>(null);
  setupPin = $state<PinAsk | null>(null);        // a token's PIN, asked while setup signs a test
  updatePct = $state<number | null>(null);
  updateError = $state<UpdateFailure | null>(null);   // why [Update now] stopped, until it is pressed again
  closeRequested = $state(0);                   // bumps each time the person presses the window's close button
  toastQueue = $state<{ id: number; text: string }[]>([]);
  private seq = 0;
  private early: Push[] = [];                   // run pushes that arrive before startRun has answered with the id

  async start() {
    app.listen(p => this.onPush(p));
    this.snap = await app.load();
    ui.clash = this.snap.clash;
  }

  toast(text: string) {
    const id = ++this.seq;
    this.toastQueue = [...this.toastQueue, { id, text }];
    setTimeout(() => { this.toastQueue = this.toastQueue.filter(t => t.id !== id); }, 4000);
  }

  /** The app has started a run: the run window shows it from here. */
  beginRun(id: string, registrars: Registrar[], what: RunKind, period: string) {
    this.run = { id, what, period, registrars, steps: [], startedAt: Date.now(), ask: null, waitingEmail: null, waitingBooks: null, submitted: {},
      ended: null, stop: null, used: '', enter: [], left: [], summary: '', total: 0, stopAsked: false };
    const early = this.early;
    this.early = [];
    for (const p of early) if (!('run' in p) || p.run === id) this.onPush(p);
  }

  endRun() { this.run = null; this.early = []; }

  private onPush(p: Push) {
    const r = this.run;
    const forRun = p.type === 'steps' || p.type === 'waiting_email' || p.type === 'books_waiting' || p.type === 'submitted' || p.type === 'run_ended'
      || (p.type === 'ask' && !((p.ask.type === 'captcha' || p.ask.type === 'pin') && p.ask.during === 'setup'));
    if (forRun && !r) {
      this.early = [...this.early.slice(-20), p];           // startRun has not answered with the run's id yet
      return;
    }
    switch (p.type) {
      case 'snapshot': {
        const before = this.snap;
        this.snap = p.snapshot;
        ui.clash = p.snapshot.clash;
        if (before?.update && !p.snapshot.update) { this.updatePct = null; this.updateError = null; }
        break;
      }
      case 'steps':
        if (r && r.id === p.run) {
          r.steps = p.steps;
          if (!p.steps.some(s => s.state === 'running' && /email/i.test(s.line))) r.waitingEmail = null;
        }
        break;
      case 'ask':
        if (p.ask.type === 'captcha' && p.ask.during === 'setup') this.setupCaptcha = p.ask;
        else if (p.ask.type === 'pin' && p.ask.during === 'setup') this.setupPin = p.ask;
        else if (r) { r.ask = p.ask; r.waitingEmail = null; }
        break;
      case 'ask_withdrawn':
        if (r?.ask?.id === p.id) r.ask = null;
        if (this.setupCaptcha?.id === p.id) this.setupCaptcha = null;
        if (this.setupPin?.id === p.id) this.setupPin = null;
        break;
      case 'notify':
        if (p.toast) this.toast(p.text);
        break;
      case 'run_month':
        if (r && r.id === p.run) { r.month = { period: p.period, index: p.index }; r.waitingEmail = null; }
        break;
      case 'waiting_email':
        if (r && r.id === p.run) r.waitingEmail = { since: p.since, ref: p.ref, skip: !!p.skip, months: p.months };
        break;
      case 'books_waiting':
        if (r && r.id === p.run) r.waitingBooks = p.on ? { company: p.company, said: p.said, kind: p.kind } : null;
        break;
      case 'submitted':
        if (r && r.id === p.run) r.submitted = { ...r.submitted, [p.registrar]: p.count };
        break;
      case 'run_ended':
        if (r && r.id === p.run) {
          r.ended = p.how; r.stop = p.stop; r.used = p.used; r.enter = p.enter ?? []; r.left = p.left ?? []; r.waitingBooks = null; r.summary = p.summary; r.total = p.total; r.waitingEmail = null; r.ask = null;
          r.submitted = { ...r.submitted, ...p.counts };
        }
        break;
      case 'update_progress':
        this.updatePct = p.pct;
        break;
      case 'update_failed':
        this.updatePct = null;
        this.updateError = p.reason;
        break;
      case 'go': {
        // just updated: back where the person was (a page the opening order allows; App.svelte still has the last word)
        const { page, section, month } = p.place;
        if (page === 'overview' || page === 'invoices' || page === 'settings') {
          ui.page = page as Page;
          if (section && (SECTIONS as readonly string[]).includes(section)) ui.section = section as Section;
          if (page === 'invoices' && month) ui.invoicesMonth = month;
        }
        break;
      }
      case 'close_requested':
        this.closeRequested++;
        break;
    }
  }

  /** Answer the run's question on screen, and take it off. */
  answerRun(a: Parameters<typeof app.answer>[1]) {
    const r = this.run;
    if (!r?.ask) return;
    const id = r.ask.id;
    r.ask = null;
    app.answer(id, a);
  }
}

export const store = new Store();
