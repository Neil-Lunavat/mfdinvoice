/* The made-up app, for looking at screens in `bun run dev`: it stands behind the same boundary as the real one, with
   sample data and no network. A run goes through its steps, asks for a captcha, CAMS's files and Your check, and
   "submits"; any stop can be made to happen. Its switches live in src/dev/devFake.ts, which only a development build
   contains. Nothing here is the product. */

import type {
  Answer, App, Ask, CamsFiles, Cert, Condition, Consent, DetailsPatch, Link, Month, NextNumber, Plan, Profile, ProfileDraft, SetupState,
  Push, Registrar, RunKind, Snapshot, StepView, Stop, BooksLookQuery, BooksLook, Invoice, Entered, Left
} from '../types';
import { NAME } from '../../brand';
import { clashAfter, type Clash } from '../../logic/clash';
import { inr, sum } from '../../logic/format';
import * as D from './data';
import { captcha, registrarPage, signature } from './images';

export interface Scenario {
  signedIn: boolean;
  hasArn: boolean;
  condition: Condition;
  update: boolean;
  month: D.MonthState;
  secondArn: boolean;
  stop: string;                 // the next run stops this way, once
  slowEmail: boolean;           // CAMS's email takes a while
  byHand: boolean;              // no mailbox: CAMS's files are asked for
  plan: 'paid' | 'trial' | 'none' | 'used' | 'ended' | 'unknown';   // what the plan says ('used': none, trial already had)
  survey: boolean;              // a survey is live and not answered yet
  booksOff: boolean;            // own invoices, but no books connected: the last number is asked, and the end lists what to enter
  tallyDown: boolean;           // the next run finds TallyPrime shut, until Refresh
  renumber: boolean;            // the next run has an invoice Tally would renumber the others for
  newYear: boolean;             // the next run is a new financial year with nothing in Tally yet
  booksAsk: boolean;            // the next run asks Tally's questions
}

interface ArnData {
  profile: Profile;
  state: D.MonthState;
  month: Month;
  notes: Snapshot['notes'];
  activity: Snapshot['activity'];
  second: boolean;
}

const sleep = (ms: number) => new Promise<void>(r => setTimeout(r, ms));
const now = () => { const d = new Date(), p = (n: number) => String(n).padStart(2, '0'); return `${D.TODAY}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`; };
const WORDS = ['K7PMX', 'R4TQA', 'W2HNB', 'J9XEF', 'M3YDU'];

class Closed extends Error {}
type NoId<T> = T extends unknown ? Omit<T, 'id'> : never;

export class FakeApp implements App {
  scenario: Scenario = {
    signedIn: false, hasArn: false, condition: 'normal', update: false, month: 'to_do', secondArn: true, stop: '', slowEmail: false, byHand: false,
    plan: 'none', survey: false, booksOff: false, tallyDown: false, renumber: false, newYear: false, booksAsk: false
  };
  private listeners = new Set<(p: Push) => void>();
  protected arns: ArnData[] = [];
  protected sel = 0;
  private email = 'rkmehta@gmail.com';
  private version = '0.9.2';
  private pending = new Map<string, (a: Answer) => void>();
  private seq = 0;
  private sigTurns = 0;
  private codeTries = 3;
  private clash: Clash | null = null;
  private run: null | { id: string; registrars: Registrar[]; what: RunKind; period: string; views: StepView[]; started: number; closed: boolean } = null;

  constructor() { this.rebuild(); }

  // --- the store -------------------------------------------------------------------------------------------------

  private data(state: D.MonthState, second: boolean, base = second ? D.SR : D.RK): ArnData {
    return {
      profile: { ...base, signature: { way: 'image', present: true, image: signature(0), size: 100, cert: null } },
      state, month: D.october(state, second), notes: D.notes(state), activity: D.activity(state), second
    };
  }

  /** Lay the store out again from the scenario (the development panel changed it). */
  rebuild() {
    const s = this.scenario;
    this.arns = !s.hasArn ? [] : [this.data(s.month, false), ...(s.secondArn ? [this.data('to_do', true)] : [])];
    this.sel = Math.min(this.sel, Math.max(0, this.arns.length - 1));
    if (s.condition === 'offline' && this.retryAt < Date.now()) this.retryAt = Date.now() + 8000;
    this.publish();
  }

  private retryAt = 0;

  protected get cur(): ArnData | null { return this.arns[this.sel] ?? null; }

  private plan(): Plan {
    const arns = this.arns.map(a => a.profile.arn), base = { slots: Math.max(2, arns.length), arns, checkedAt: now() };
    switch (this.scenario.plan) {
      case 'paid': return { ...base, state: 'active', source: 'paid', until: '2027-09-26' };
      case 'trial': return { ...base, state: 'active', source: 'trial', until: '2026-10-18', slots: 1, arns: arns.slice(0, 1) };
      case 'ended': return { ...base, state: 'ended', source: 'trial', until: '2026-09-30', slots: 1 };
      case 'none': return { ...base, state: 'none', source: '', until: '', slots: 0, arns: [] };
      case 'used': return { ...base, state: 'none', source: '', until: '', slots: 0, arns: [], trialUsed: true };
      case 'unknown': return { ...base, state: 'unknown', source: '', until: '', slots: 0, arns: [] };
    }
  }

  private snapshot(): Snapshot {
    const s = this.scenario, c = this.cur;
    const year = c && c.month.invoices.length ? D.yearRows(c.month, c.second) : c && c.month.everRun ? D.yearRows(c.month, c.second).slice(1) : [];
    return {
      version: this.version,
      condition: s.condition,
      network: { online: s.condition !== 'offline', retryAt: s.condition === 'offline' ? this.retryAt : 0 },
      update: s.update ? { version: '0.9.3', why: 'CAMS changed its upload page. This version handles it.', failed: false } : null,
      account: s.signedIn ? { email: this.email, maxArns: 6 } : null,
      plan: s.signedIn ? this.plan() : null,
      survey: s.signedIn && s.survey ? D.SURVEY : null,
      arns: this.arns.map(a => {
        const rej = a.month.invoices.filter(x => x.status === 'Rejected').length;
        const sent = a.month.invoices.some(x => x.status !== 'Not submitted');
        return {
          arn: a.profile.arn, name: a.profile.name, rejected: rej,
          status: rej ? 'Rejected' : !sent ? 'Not submitted' : a.month.invoices.every(x => x.status === 'Approved') ? 'Approved' : 'Submitted'
        };
      }),
      arn: c?.profile.arn ?? '',
      today: D.TODAY,
      profile: c ? { ...structuredClone(c.profile), books: s.booksOff ? '' as const : c.profile.books } : null,
      month: c ? structuredClone(c.month) : null,
      year,
      notes: c ? structuredClone(c.notes) : [],
      activity: c ? structuredClone(c.activity) : [],
      fy: '2026-27',
      run: this.run && c ? { run: this.run.id, registrars: this.run.registrars, startedAt: new Date(this.run.started).toISOString(), what: this.run.what, period: this.run.period } : null,
      clash: this.clash,
      deleting: '',
      elsewhere: ''
    };
  }

  protected push(p: Push) { for (const l of this.listeners) l(p); }
  protected publish() { this.push({ type: 'snapshot', snapshot: this.snapshot() }); }

  async load() { return this.snapshot(); }

  listen(onPush: (p: Push) => void) {
    this.listeners.add(onPush);
    return () => { this.listeners.delete(onPush); };
  }

  // --- sign in ---------------------------------------------------------------------------------------------------

  async sendCode(email: string) {
    await sleep(700);
    if (/^many@/i.test(email.trim())) return { ok: false as const, reason: 'too_many_codes' as const, wait: 0 };
    this.codeTries = 3;
    return { ok: true as const };
  }

  async verifyCode(email: string, code: string, replace = false) {
    await sleep(700);
    // other@…: the account is on another PC until the question is answered with "Sign it out and sign in here"
    if (/^other@/i.test(email.trim()) && !replace) return { ok: false as const, reason: 'other_pc' as const, left: 0, deleteAfter: '', device: 'DESKTOP-4K2P', lastSeen: new Date(Date.now() - 2 * 3600_000).toISOString() };
    if (/^gone@/i.test(email.trim())) return { ok: false as const, reason: 'pending_deletion' as const, left: 0, deleteAfter: `${D.TODAY}T18:30:00` };
    if (code === '000000') {
      const left = --this.codeTries;
      return { ok: false as const, reason: left > 0 ? 'wrong' as const : 'locked' as const, left, deleteAfter: '' };
    }
    this.email = email.trim();
    this.scenario.signedIn = true;
    this.publish();
    return { ok: true as const };
  }

  async signOut(_remove: boolean) { await sleep(300); this.scenario.signedIn = false; this.publish(); }

  async activateTrial() { await sleep(500); this.scenario.plan = 'trial'; this.publish(); return { ok: true as const }; }

  async checkPlan() { await sleep(500); this.publish(); }

  async agree(c: Consent) {
    if (this.cur) this.cur.profile.consent = { ...c, device: 'THIS-PC' };
    this.publish();
    return { ok: true as const };
  }

  // --- setup -----------------------------------------------------------------------------------------------------

  async testMailbox(m: { provider: string; address: string; appPassword: string }) {
    await sleep(1200);
    const letters = m.appPassword.replace(/[^a-z]/gi, '');
    if (m.provider === 'gmail' && /^(.)\1+$/.test(letters)) return { ok: false as const, said: "Gmail didn't accept this app password." };
    return { ok: true as const, found: 3, as: m.provider === 'outlook' ? 'rkmehta@outlook.com' : m.address };
  }

  /* The portal the fake stands in for knows one ARN per login: ARN-12345, unless the email or the username starts
     with "other" (another ARN's login: ARN-99999). An email starting with "locked" is one CAMS has locked. */
  async testCams(c: { email: string }) {
    await sleep(1400);
    if (/^locked/i.test(c.email)) return { ok: false as const, said: 'Your email ID is locked. Please try again after 30 minutes' };
    return { ok: true as const, arn: /^other/i.test(c.email) ? 'ARN-99999' : 'ARN-12345', name: 'R K MEHTA' };
  }

  async testKfintech(k: { username: string; password: string; expect?: string }) {
    await sleep(900);
    try {
      await this.captchaLoop('setup');
    } catch {
      return { ok: false as const, said: '' };
    }
    await sleep(600);
    if (/wrong/i.test(k.password)) return { ok: false as const, said: 'Invalid username or password.' };
    const other = /^other/i.test(k.username);
    return { ok: true as const, as: other || k.username.toLowerCase().startsWith('sr') ? 'S R MEHTA' : 'R K MEHTA', arn: other ? 'ARN-99999' : 'ARN-12345',
      name: 'R K MEHTA & CO', gstin: /^nogst/i.test(k.username) ? '' : '27ABCPM1234F1Z3' };
  }

  async prepareSignature() {
    await sleep(1200);
    this.sigTurns = 0;
    return { ok: true as const, image: signature(0) };
  }

  async rotateSignature() {
    this.sigTurns++;
    return { image: signature(this.sigTurns) };
  }

  async dropSignatureDraft() {}

  private setupKept: SetupState | null = null;
  async saveSetup(state: unknown) { this.setupKept = state as SetupState; }
  async loadSetup() { return this.setupKept; }
  async dropSetup() { this.setupKept = null; }

  async findCertificates() {
    await sleep(700);
    const certs: Cert[] = [{ thumbprint: 'A1B2C3D4E5F60718293A4B5C6D7E8F9012345678', name: 'RAJESH KUMAR MEHTA',
      issuer: 'Capricorn Sub CA for Individual DSC 2022', expires: '2028-03-14', route: 'windows', tested: false }];
    return { certs };
  }

  async testCertificate() {
    await sleep(1500);
    return { ok: true as const };
  }

  async tokenHere() { return true; }

  async reconnect() {
    await sleep(700);
    if (this.scenario.condition === 'offline') { this.retryAt = Date.now() + 5000; this.publish(); }
    return { online: this.scenario.condition !== 'offline' };
  }

  async finishSetup(p: ProfileDraft, adding: boolean) {
    await sleep(400);
    if (this.arns.some(a => a.profile.arn === p.arn)) return { ok: false as const, said: `${p.arn} is already on this account.` };
    const books = p.zoho?.orgId ? 'zoho' as const : p.tally?.company ? 'tally' as const : '' as const;
    const profile: Profile = { ...structuredClone(p), arnConfirmed: true, lastLogin: { CAMS: '', KFINTECH: '' },
      kept: { kind: books, company: p.zoho?.orgId ? p.zoho.org : p.tally?.company ?? '', ledgers: 0 }, books, usedTop: '',
      consent: p.consent ? { ...p.consent, device: 'THIS-PC' } : null };
    const fresh: ArnData = { profile, state: 'first_run', month: D.october('first_run'), notes: [], activity: [], second: adding };
    fresh.activity = [{ at: now(), text: `Set up ${p.arn}`, registrar: null, who: 'you, on this PC', tone: 'setting' }];
    this.arns.push(fresh);
    this.sel = this.arns.length - 1;
    this.scenario.hasArn = true;
    this.publish();
    return { ok: true as const };
  }

  async saveDetails(p: DetailsPatch) {
    const c = this.cur;
    if (!c) return { ok: false as const, said: 'No ARN is set up.' };
    if (p.camsEmail) this.clash = clashAfter(c.profile, p.camsEmail) ?? this.clash;
    if (p.mailbox) this.clash = null;
    Object.assign(c.profile, structuredClone(p));
    const what = p.camsEmail ? `CAMS email changed to ${p.camsEmail}` : p.mailbox ? `Mailbox changed to ${p.mailbox.address}`
      : p.kfintech ? (p.kfintech.used ? 'KFintech login changed' : "KFintech turned off for this ARN") : p.signature ? 'Signature replaced'
      : p.gstin || p.name ? 'Your details changed' : 'Details changed';
    c.activity.unshift({ at: now(), text: what, registrar: null, who: 'you, on this PC', tone: 'setting' });
    this.publish();
    return { ok: true as const };
  }

  async switchArn(arn: string) {
    const i = this.arns.findIndex(a => a.profile.arn === arn);
    if (i >= 0) { this.sel = i; this.publish(); }
  }

  // --- the month -------------------------------------------------------------------------------------------------

  async month(period: string): Promise<Month> {
    const c = this.cur!;
    return structuredClone(period === c.month.period ? c.month : D.earlier(period, c.second));
  }

  async preview() { return ''; }
  async previewInvoice() { await sleep(400); return ''; }
  async previewRegistrar() { await sleep(400); return registrarPage(); }
  async exportMonth(period: string) { await sleep(500); return { ok: true as const, name: `${NAME} ${period}.zip` }; }
  // Tally, made up: a company that numbers its own invoices, with whatever was imported in this session
  private inTally = new Map<string, string>();
  private async tallyOf(q: BooksLookQuery): Promise<BooksLook> {
    const m = await this.month(q.period), own = this.cur!.profile.invoices.source === 'own';
    let next = 150 + this.inTally.size;
    const sent = (x: Invoice) => !['Not submitted', 'Fetched', 'Signed', 'Checked'].includes(x.status);
    const rows = m.invoices.map(x => {
      const number = this.inTally.get(x.key) ?? '', later = !number && q.which === 'submitted' && !sent(x);
      const asked = !number && !later && !q.answers[`sales:${x.amc}`];
      const action = number ? 'in_books' as const : own ? (sent(x) ? 'past' as const : 'run' as const) : later ? 'later' as const : asked ? 'ask' as const : 'import' as const;
      return { key: x.key, registrar: x.registrar, amc: x.amc, date: x.date, total: x.taxable + x.cgst + x.sgst + x.igst,
        submitted: sent(x), gstin: '27AAATB0102C1ZR', number, will: action === 'import' ? `${++next}/26-27` : '',
        party: `${x.amc} Mutual Fund`, partyNew: false, sales: `${x.amc} MF Commission`, action,
        note: number ? `Already in your books as ${number}` : later ? 'Not submitted yet' : '' };
    });
    return { kind: 'tally', state: 'ready', said: '', companies: ['Lunavat & Co'], company: 'Lunavat & Co', period: q.period, label: m.label, own,
      which: q.which, vtype: 'Sales', method: 'Automatic', tallyNumbers: true, last: `${150 + this.inTally.size}/26-27`, askLast: false,
      rows, creates: [...new Set(rows.filter(r => r.action === 'import' || r.action === 'ask').map(r => r.party))].map(name => ({ kind: 'party' as const, name, gstin: '27AAATB0102C1ZR' })),
      asks: [...new Set(rows.filter(r => r.action === 'ask').map(r => r.amc))].map(a => ({ id: `sales:${a}`,
        question: `Which sales ledger does ${a}'s commission go under?`, options: ['Commission Income', 'Brokerage Received'] })).concat(
        q.answers.gstin === 'yes' ? [] : [{ id: 'gstin', options: ['yes'],
          question: `Lunavat & Co's GSTIN in Tally is 27AAAPL9999F1Z1. Yours here is ${this.cur?.profile.gstin ?? ''}. Is this the right company?` }]), warn: [],
      counts: { submitted: m.invoices.filter(sent).length, all: rows.length, going: rows.filter(r => r.action === 'import').length,
        byHand: 0, inBooks: rows.filter(r => r.action === 'in_books').length } };
  }
  async booksLook(q: BooksLookQuery) {
    await sleep(600);
    const kind = q.kind || this.cur!.profile.books;
    if (!kind) return { ...(await this.tallyOf(q)), kind: '' as const, state: 'none' as const, rows: [] };
    return this.tallyOf(q);
  }
  async booksImport(q: BooksLookQuery & { adopt: string[] }) {
    await sleep(1200);
    const going = (await this.tallyOf(q)).rows.filter(r => r.action === 'import');
    for (const r of going) this.inTally.set(r.key, r.will);
    return { ...(await this.tallyOf(q)), done: { imported: going.map(r => r.key), adopted: [], numbers: going.map(r => r.will), stoppedAt: '', refused: [] } };
  }
  async booksSetup(q: { kind: 'tally' | 'zoho'; gstin: string }) {
    await sleep(500);
    return { state: 'ready' as const, said: '',
      companies: q.kind === 'tally' ? [{ name: 'Lunavat & Co', guid: 'g1', gstin: q.gstin, same: true },
        { name: 'Mehta Family Trust', guid: 'g2', gstin: '27AAATM1234C1Z5', same: false }] : [],
      orgs: q.kind === 'zoho' ? [{ id: 'z1', name: 'Lunavat & Co', gstin: q.gstin, same: true },
        { id: 'z2', name: 'Mehta Family Trust', gstin: '27AAATM1234C1Z5', same: false }] : [] };
  }
  async booksUse() { return { ok: true }; }
  async zohoConnect() { await sleep(1500); return { ok: true as const }; }
  async zohoCancel() {}
  async zohoDisconnect() { return { ok: true }; }
  async booksNext() {
    await sleep(300);
    // dev: ?books=none gives a company with no invoice this year on plain Automatic numbering
    if (new URLSearchParams(location.search).get('books') === 'none') return { state: 'ready', company: 'Lunavat & Co', last: '', next: '', at: -1, method: 'Automatic' };
    return { state: 'ready', company: 'Lunavat & Co', last: '73/26-27', next: '74/26-27', at: 0, method: 'Manual' };
  }
  async refreshBooks() { this.refreshed = true; }
  private refreshed = false;
  async booksForget() { return { ok: true }; }
  async openPdf() {}
  async showInFolder() {}
  async openFolder() {}
  async uninstall() { return 'not_installed'; }
  async skipCams() {}
  private claimedAt = 0;
  async forwardClaim() { await sleep(700); this.claimedAt = Date.now(); return { ok: true }; }
  async forwardState() {
    await sleep(400);
    const s = (Date.now() - this.claimedAt) / 1000;
    return { proved: this.claimedAt > 0 && s > 12, confirm: this.claimedAt > 0 && s > 6 ? 'https://mail-settings.google.com/mail/vf-example' : '' };
  }
  async forwardConfirm() { await sleep(200); return true; }
  private box: CamsFiles = { added: [], refused: [], waiting: [] };
  private snapBox(): CamsFiles { return { added: [...this.box.added], refused: [...this.box.refused], waiting: [...this.box.waiting], said: this.box.said }; }
  private addPeriod(period: string, count: number, name: string) {
    this.box.added = [...this.box.added.filter(a => a.period !== period), { period, count, name }];
  }
  async checkMail() { await sleep(900); return { got: [{ period: 'SEP-2026', count: 10 }], waiting: ['OCT-2026'], said: '' }; }
  async camsFilesStart() { this.box = { added: [], refused: [], waiting: [] }; return this.snapBox(); }
  async chooseCamsFiles() {
    await sleep(500);
    this.addPeriod('OCT-2026', 5, 'GST_REPORT_224793670R106_1.zip and .xls');
    this.addPeriod('SEP-2026', 10, 'GST_REPORT_224793670R105_1.zip and .xls');
    this.box.waiting = [...this.box.waiting, { name: 'GST_REPORT_224793670R104_1.zip', why: "Waiting for its Excel report." }];
    return this.snapBox();
  }
  async dropCamsFiles(files: { name: string }[]) {
    await sleep(500);
    const groups = new Map<string, string[]>();
    for (const f of files) {
      const m = /^GST_REPORT_(\d+)R\d+_\d+\.(zip|xls)$/i.exec(f.name);
      if (!m) { this.box.refused = [...this.box.refused, { name: f.name, why: "Not one of CAMS's files: theirs are named GST_REPORT_…" }]; continue; }
      groups.set(m[1], [...(groups.get(m[1]) ?? []), f.name]);
    }
    const months = ['AUG-2026', 'SEP-2026', 'OCT-2026'];
    let i = this.box.added.length;
    for (const names of groups.values()) {
      const exts = names.map(n => n.slice(-3).toLowerCase());
      if (exts.includes('zip') && exts.includes('xls')) {
        this.addPeriod(months[i++ % months.length], 4 + i, names.join(' and '));
        this.box.waiting = this.box.waiting.filter(w => !names.some(n => n.replace(/\.\w+$/, '') === w.name.replace(/\.\w+$/, '')));
      } else this.box.waiting = [...this.box.waiting, { name: names[0], why: exts[0] === 'zip' ? 'Waiting for its Excel report.' : 'Waiting for its zip of invoices.' }];
    }
    return this.snapBox();
  }
  async pickFile(kind: 'zip' | 'xls') { return { kind, name: kind === 'zip' ? 'GST_REPORT_224793670R106_1.zip' : 'GST_REPORT_224793670R106_1.xls' }; }
  async dropFile(f: { name: string }) { const kind = /\.zip$/i.test(f.name) ? 'zip' : /\.xlsx?$/i.test(f.name) ? 'xls' : ''; return { kind, name: kind ? f.name : '' }; }

  // --- the run ---------------------------------------------------------------------------------------------------

  private ask(a: NoId<Ask>): Promise<Answer> {
    const id = 'q' + ++this.seq, r = this.run;
    return new Promise((resolve, reject) => {
      const watch = r ? setInterval(() => { if (r.closed) { clearInterval(watch); this.pending.delete(id); reject(new Closed()); } }, 200) : undefined;
      this.pending.set(id, v => { clearInterval(watch); resolve(v); });
      this.push({ type: 'ask', ask: { ...a, id } as Ask });
    });
  }

  answer(id: string, a: Answer) {
    const r = this.pending.get(id);
    this.pending.delete(id);
    r?.(a);
  }

  private async captchaLoop(during: 'run' | 'setup') {
    let attempt = 1, w = Math.floor(Math.random() * WORDS.length), message = '';
    for (;;) {
      const word = WORDS[w % WORDS.length];
      const a = await this.ask({ type: 'captcha', image: captcha(word), attempt, message, during });
      if (a.type !== 'captcha') throw new Closed();
      if (a.refresh) { w++; message = ''; continue; }
      if (!a.text) throw new Closed();
      await sleep(500);
      if (a.text.trim().toUpperCase() === word) return;
      attempt++; w++; message = "Not quite. Here's a new one.";
    }
  }

  private say(name: string, state: StepView['state'], text = '') {
    const r = this.run!;
    r.views = r.views.map(v => v.name === name ? { ...v, state, ...(state === 'done' ? { result: text } : { line: text || v.line }) }
      : v.state === 'running' && state === 'running' ? { ...v, state: 'done' as const } : v);
    this.push({ type: 'steps', run: r.id, steps: r.views });
  }

  async startRun(a: { registrars: Registrar[]; period: string; what: RunKind; periods?: string[]; last?: NextNumber | null }) {
    const id = 'run-' + Date.now().toString(36);
    const booked = this.cur?.profile.invoices.source === 'own' && !!this.cur.profile.books && !this.scenario.booksOff;
    const regNames = a.registrars.map(r => (r === 'CAMS' ? 'CAMS' : 'KFintech'));
    const names = a.what === 'run' ? ['Check', 'Get', 'Read', ...(booked ? ['Your check', 'Your books', 'Sign'] : ['Sign', 'Your check']), ...regNames]
      : a.what === 'download' ? ['Check', 'Get', 'Read'] : ['Check'];
    this.run = { id, registrars: a.registrars, what: a.what, period: a.period, started: Date.now(), closed: false,
      views: names.map((name, index) => ({ index, name, state: 'waiting', line: '', result: '' })) };
    if (a.last && this.cur) this.cur.profile.invoices = { ...this.cur.profile.invoices, last: a.last.text, at: a.last.at };
    this.publish();
    void this.drive().catch(e => { if (!(e instanceof Closed)) throw e; });
    return { run: id };
  }

  stopRun() {
    const r = this.run;
    if (!r) return;
    r.closed = true;
    this.end('stopped');
  }

  closeRun() { this.stopRun(); }

  private end(how: 'done' | 'stopped' | 'nothing', more: { summary?: string; used?: string; counts?: Partial<Record<Registrar, number>>; total?: number; stop?: Stop; enter?: Entered[]; left?: Left[] } = {}) {
    const r = this.run;
    if (!r) return;
    const c = this.cur;
    if (c && r.what === 'run') { c.month.everRun = true; c.month.lastRun = { how, at: now(), said: how === 'stopped' ? 'This run stopped' : '', portal: '', code: '' }; }
    this.push({ type: 'run_ended', run: r.id, how, what: r.what, used: more.used ?? '', summary: more.summary ?? '', enter: more.enter ?? [], left: more.left ?? [], notes: [], counts: more.counts ?? {}, total: more.total ?? 0, stop: more.stop ?? null });
    this.run = null;
    this.publish();
  }

  private STOPS: Record<string, { title: string; lines: string[]; said?: string; reg?: Registrar }> = {
    arn_mismatch: { title: "CAMS's ARN (ARN-118830) doesn't match your ARN (ARN-104512)", lines: ["Nothing was submitted. Check that the CAMS email and the KFintech login are both this ARN's."], reg: 'CAMS' },
    account_locked: { title: 'CAMS is locked for now', lines: ['CAMS locks an email when it is signed in to too many times in a short while. Try again in 15 minutes.'], said: 'Your email ID is locked. Please try again after 30 minutes', reg: 'CAMS' },
    refused: { title: 'KFintech said no', lines: ['Nothing was submitted by this step.'], said: 'Invalid username or password.', reg: 'KFINTECH' },
    not_listed: { title: "October's invoices aren't listed yet", lines: ['Fund houses usually list them in the first days of the month. Nothing was submitted.'] },
    nothing_to_do: { title: 'Nothing to do for October', lines: ['Every invoice for October is already submitted to CAMS and KFintech portals.'] },
    mailbox: { title: "Your mailbox couldn't be read", lines: ['Nothing was asked of CAMS. Fix the mailbox in Settings › Connections, then run again.'], said: 'Application-specific password required.', reg: 'CAMS' },
    mailback_late: { title: "CAMS's email hasn't arrived yet", lines: ["CAMS was asked at 10:42. Run again in a few minutes: the run looks for that email first and doesn't ask twice."], reg: 'CAMS' },
    wrong_files: { title: "These files aren't October 2026's", lines: ["The Excel report is for September 2026. Choose the zip and the Excel from CAMS's email for October 2026."], reg: 'CAMS' },
    mismatch: { title: 'CAMS read the upload differently', lines: ["Nothing was submitted. The next run gets CAMS's invoices again."], said: "SBI: Taxable Value is 28915.00 in the upload and 28519.00 in CAMS's review", reg: 'CAMS' },
    portal_validation: { title: "CAMS didn't accept 1 of 11 invoices", lines: ['Nothing was submitted. Run again and untick them at Your check; the rest can go.'], said: 'HDFC: Invoice amount does not match the brokerage paid.', reg: 'CAMS' },
    unknown_submit: { title: "CAMS didn't answer the Submit", lines: ["It may or may not have gone through. Nothing is sent twice: the next run reads CAMS's status first and sends only what CAMS doesn't have."], reg: 'CAMS' },
    not_submitting: { title: 'Stopped just before Submit', lines: ['Everything up to here was real, and the registrars have checked the uploads. Submit is switched off on this PC.'] },
    ours: { title: `Something on CAMS's side isn't what ${NAME} expects`, lines: ['Run again in a few minutes. If it keeps happening, Send to support.'], reg: 'CAMS' },
    arn_unbound: { title: "This ARN couldn't be added to your account", lines: ["Nothing was submitted. CAMS's files for this month are on this PC, so the next run starts from them."], said: "Another account has this ARN. Send it to support and we'll sort it out.", reg: 'CAMS' },
    both: { title: "These files aren't October 2026's", lines: ["The Excel report is for September 2026. Choose the zip and the Excel from CAMS's email for October 2026."], reg: 'CAMS' },
    unreachable: { title: `${NAME} can't reach its server`, lines: [`${NAME} can't reach its server right now, so it can't be sure it is up to date with the portals.`, 'Nothing was done. Try again in a few minutes.'] }
  };

  /** The scenario's stop, once: its screen, and the run is over. */
  private async stopNow(name: string, soFar = ''): Promise<boolean> {
    const kind = this.scenario.stop, r = this.run!;
    if (!kind || !this.STOPS[kind]) return false;
    this.scenario.stop = '';
    const s = this.STOPS[kind];
    r.views = r.views.map(v => v.name === name ? { ...v, state: 'bad' as const } : v);
    this.push({ type: 'steps', run: r.id, steps: r.views });
    // 'both': CAMS's stop with KFintech's beside it, as when both registrars stopped
    const others = kind === 'both' ? [{ kind: 'kfin_down', title: "KFintech's site didn't load its invoices", said: '', lines: ['Its server answered with errors. Nothing was sent to KFintech. Run again in a few minutes.'], registrar: 'KFINTECH' as const }] : undefined;
    this.end(kind === 'nothing_to_do' ? 'nothing' : 'stopped', { stop: { kind: kind === 'both' ? 'wrong_files' : kind, title: s.title, said: s.said ?? '', lines: s.lines, so_far: soFar, registrar: s.reg ?? null, others } });
    return true;
  }

  private async drive() {
    const r = this.run!, c = this.cur!, regs = r.registrars;
    const has = (x: Registrar) => regs.includes(x);
    const guard = () => { if (r.closed) throw new Closed(); };
    const early = ['arn_mismatch', 'account_locked', 'refused', 'not_listed', 'nothing_to_do', 'unreachable'];
    const open = c.month.invoices.filter(x => has(x.registrar) && !['Waiting approval', 'Approved', 'Submitted'].includes(x.status));
    const cams = open.filter(x => x.registrar === 'CAMS'), kf = open.filter(x => x.registrar === 'KFINTECH');

    // Check: sign in to each registrar (KFintech's captcha is asked here), read what each already has
    if (has('KFINTECH')) { this.say('Check', 'running', 'Signing in to KFintech'); await sleep(700); guard(); await this.captchaLoop('run'); }
    if (has('CAMS')) { this.say('Check', 'running', 'Signing in to CAMS'); await sleep(900); guard(); }
    if (early.includes(this.scenario.stop) && await this.stopNow('Check')) return;
    this.say('Check', 'running', `Reading what ${has('CAMS') ? 'CAMS' : 'KFintech'} already has`);
    await sleep(900); guard();
    c.month.checkedAt = now();
    const checked = regs.map(x => `${x === 'CAMS' ? 'CAMS' : 'KFintech'} nothing submitted yet`).join(' · ');
    this.say('Check', 'done', checked);
    if (r.what === 'check') { this.end('done', { summary: checked }); return; }

    // Get: KFintech by download; CAMS by email, or from the person when no mailbox is connected
    this.say('Get', 'running', 'Getting the invoices');
    if (['mailbox', 'mailback_late'].includes(this.scenario.stop) && await this.stopNow('Get')) return;
    if (has('CAMS')) {
      this.say('Get', 'running', "Asking CAMS to email October 2026's invoices");
      await sleep(900); guard();
      if (c.profile.mailbox.provider === 'folder' || this.scenario.byHand) {
        this.say('Get', 'running', "Choose CAMS's invoice files");
        await this.ask({ type: 'pick_files', month: 'October 2026', sentTo: c.profile.camsEmail, skip: true, message: this.scenario.byHand ? "These files are September 2026's, not October 2026's." : '' });
      } else {
        this.say('Get', 'running', "Waiting for CAMS's email");
        this.push({ type: 'waiting_email', run: r.id, since: new Date().toISOString(), ref: '224851745 WBR106' });
        await sleep(this.scenario.slowEmail ? 9000 : 3000);
      }
      guard();
    }
    if (['wrong_files', 'both'].includes(this.scenario.stop) && await this.stopNow('Get')) return;
    this.say('Get', 'done', [cams.length && `CAMS ${cams.length}`, kf.length && `KFintech ${kf.length}`].filter(Boolean).join(' · '));

    this.say('Read', 'running', "Reading the invoices");
    await sleep(900); guard();
    const taxable = sum(open.map(x => x.taxable)), gstSum = sum(open.map(x => x.cgst + x.sgst + x.igst));
    if (r.what === 'download') {
      this.say('Read', 'done', `${open.length} invoices on this PC`);
      this.end('done', { summary: `${open.length} invoices for October downloaded.` });
      return;
    }
    this.say('Read', 'done', `${open.length} invoices to do · ${inr(taxable)} taxable · ${inr(gstSum)} GST`);

    const own = c.profile.invoices.source === 'own';
    const booked = own && !!c.profile.books && !this.scenario.booksOff;
    if (booked) {
      this.say('Read', 'running', 'Reading your Tally');
      await sleep(700); guard();
      if (this.scenario.tallyDown) {
        this.scenario.tallyDown = false;
        this.refreshed = false;
        this.push({ type: 'books_waiting', run: r.id, on: true, company: 'Lunavat & Co', said: '', kind: 'tally' });
        for (let i = 0; i < 40 && !this.refreshed; i++) { await sleep(500); guard(); }
        this.push({ type: 'books_waiting', run: r.id, on: false, company: '', said: '', kind: 'tally' });
      }
      if (this.scenario.booksAsk) {
        this.scenario.booksAsk = false;
        await this.ask({ type: 'books_ask', asks: [
          { id: 'vtype', question: 'Lunavat & Co has 2 kinds of sales voucher. Which one do these invoices go in as?', options: ['Sales', 'Commission Sales'] },
          { id: 'gstin', question: "Lunavat & Co's GSTIN in Tally is 27AAAPL9999F1Z1. Yours here is 27ABCPM1234F1Z3. Is this the right company?", options: ['yes'] }] });
        guard();
      }
    } else {
      this.say('Sign', 'running', 'Signing the invoices');
      await sleep(900); guard();
      this.say('Sign', 'done', own ? 'Made after your check' : `${open.length} signed`);
    }

    this.say('Your check', 'running', 'Your check');
    const first = Number((c.profile.invoices.last.match(/^\d+/) ?? ['73'])[0]) + 1;
    const ordered = [...cams, ...kf], can = ordered.filter(x => !(own && x.igst));
    const aside = booked && this.scenario.renumber ? ordered[ordered.length - 1]?.key : '';
    const newYear = booked && this.scenario.newYear;
    this.scenario.renumber = this.scenario.newYear = false;
    const check = await this.ask({
      type: 'your_check', notes: [],
      books: booked ? { kind: 'tally' as const, company: 'Lunavat & Co', after: newYear ? '' : 'September', first: newYear ? { fy: '2027-28', proposed: '1/27-28' } : null,
        creates: [{ kind: 'party', name: 'Aditya Birla Sun Life AMC', gstin: '27AAACB0000A1Z5' }, { kind: 'party', name: 'HDFC Asset Management', gstin: '27AAACH0000A1Z5' }] } : null,
      rows: ordered.map((x, i) => ({
        key: x.key, registrar: x.registrar, amc: x.amc,
        number: own && !booked && !x.igst ? `${first + can.indexOf(x)}/26-27` : '', ...(own && !booked && !x.igst ? { seq: can.indexOf(x), kept: false } : {}),
        taxable: x.taxable, gst: sum([x.cgst, x.sgst, x.igst]), igst: x.igst > 0, included: x.key !== aside,
        blocked: own && x.igst ? "Charged IGST, which your own invoice doesn't do yet" : '', rejection: x.status === 'Rejected' ? x.rejection : '',
        ...(booked && i === 0 && !newYear ? { note: 'In Tally as 71/26-27, not sent yet' } : {}),
        ...(x.key === aside ? { renumber: { date: '2026-09-04', type: 'Sales' } } : {})
      }))
    });
    if (check.type !== 'your_check' || !check.confirmed) { this.run = null; this.publish(); return; }
    this.say('Your check', 'done', `${check.included.length} ticked`);
    if (booked) {
      this.say('Your books', 'running', 'Fetching your last invoice number');
      await sleep(600); guard();
      for (const x of ordered.filter(o => check.included.includes(o.key))) {
        this.say('Your books', 'running', `Putting ${x.amc}'s invoice into Tally`);
        await sleep(500); guard();
      }
      this.say('Your books', 'done', `${check.included.length} invoices in Tally`);
      this.say('Sign', 'running', 'Making your invoices');
      await sleep(900); guard();
      this.say('Sign', 'done', `${check.included.length} made`);
    }

    const chosen = new Set(check.included), counts: Partial<Record<Registrar, number>> = {};
    for (const reg of ['CAMS', 'KFINTECH'] as Registrar[]) {
      const name = reg === 'CAMS' ? 'CAMS' : 'KFintech';
      const n = open.filter(x => x.registrar === reg && chosen.has(x.key)).length;
      if (!has(reg)) continue;
      if (!n) { this.say(name, 'done', 'nothing ticked'); continue; }
      this.say(name, 'running', reg === 'CAMS' ? "Preparing CAMS's upload" : "Filling in KFintech's page");
      await sleep(1100); guard();
      const soFar = Object.entries(counts).map(([k, v]) => `${k === 'CAMS' ? 'CAMS' : 'KFintech'}: ${v} submitted`).join(' · ');
      if (['mismatch', 'portal_validation', 'ours', 'unknown_submit', 'not_submitting'].includes(this.scenario.stop) && await this.stopNow(name, soFar)) return;
      this.say(name, 'running', `Submitting to ${name}`);
      await sleep(1400); guard();
      c.month.invoices = c.month.invoices.map(x => chosen.has(x.key) && x.registrar === reg ? D.withStatus(x, 'Waiting approval', D.TODAY) : x);
      c.activity.unshift({ at: now(), text: `Submitted ${n} invoices`, registrar: reg, who: '', tone: 'plain' });
      counts[reg] = n;
      this.push({ type: 'submitted', run: r.id, registrar: reg, count: n });
      this.say(name, 'done', `${n} submitted`);
    }
    const sent = open.filter(x => chosen.has(x.key));
    c.month.submittedOn ||= D.TODAY;
    c.state = 'submitted';
    const left = open.length - sent.length;
    const summary = `${sent.length} invoices submitted for October.${left ? ` ${left} left for later.` : ''}`;
    c.notes.unshift({ id: 'n' + Date.now(), kind: 'run_done', text: summary, detail: '', opens: 'overview', when: now(), read: false });
    this.end('done', { summary, counts, total: sum(sent.map(x => x.taxable + x.cgst + x.sgst + x.igst)),
      used: own && sent.length ? `${booked ? 'Invoice numbers from Tally:' : 'Used'} ${first}/26-27 to ${first + sent.length - 1}/26-27` : '',
      enter: own && !booked ? sent.map((x, i) => ({ registrar: x.registrar, amc: x.amc, key: x.key, number: `${first + i}/26-27` })) : [] });
  }

  // --- the rest --------------------------------------------------------------------------------------------------

  async markNotesRead() { this.cur?.notes.forEach(n => (n.read = true)); this.publish(); }
  async sendSupport(_: { text: string }) { await sleep(600); return { sent: true }; }
  async sendIdea(_: { text: string }) { await sleep(600); return { sent: true }; }
  async answerSurvey() { await sleep(700); this.scenario.survey = false; this.publish(); return { sent: true }; }
  async open(_: Link) {}
  async checkForUpdates() { await sleep(700); return { upToDate: true }; }

  async updateNow() {
    for (let p = 0; p <= 100; p += 7) { this.push({ type: 'update_progress', pct: Math.min(p, 100) }); await sleep(120); }
    this.push({ type: 'update_progress', pct: 100 });
    await sleep(300);
    this.scenario.update = false;
    this.version = '0.9.3';
    this.publish();
  }

  async here() {}

  quit() { location.reload(); }
}
