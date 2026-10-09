/* The real app, behind the same `App` interface as the fake: pywebview's bridge to the Python side
   (client/src/client/hands/window.py, hosted by shell.py).

   One way in, one way out:
     the window asks   → `pywebview.api.call(method, args)`, which runs the app's method and resolves with its answer
     the app pushes    → `window.__automation.push(p)`, called by the app, in order

   The app holds its pushes until `listen` is called, so nothing it says before the page has loaded is lost. */

import type {
  Answer, App, CamsFiles, Cert, CodeRefusal, Consent, DetailsPatch, InvoiceSettings, Link, MailProvider, NextNumber, Month, Place, ProfileDraft, Push, SetupState,
  Registrar, Result, RunKind, Snapshot, SurveyAnswers, VerifyRefusal, BooksLookQuery, BooksLook, BooksSetup, ZohoConnect, TallyPick, ZohoPick
} from './types';

interface PyApi { call(method: string, args?: unknown[]): Promise<unknown> }

declare global {
  interface Window {
    pywebview?: { api: PyApi };
    __automation?: { push(p: Push): void };
  }
}

export class RealApp implements App {
  private listeners = new Set<(p: Push) => void>();
  private ready: Promise<PyApi>;

  constructor() {
    window.__automation = { push: p => { for (const l of this.listeners) l(p); } };
    this.ready = new Promise(resolve => {
      const now = () => window.pywebview?.api;
      if (now()) resolve(now()!);
      else window.addEventListener('pywebviewready', () => resolve(now()!), { once: true });
    });
  }

  private async call<T>(method: string, ...args: unknown[]): Promise<T> {
    const api = await this.ready;
    return (await api.call(method, args)) as T;
  }

  load() { return this.call<Snapshot>('load'); }

  listen(onPush: (p: Push) => void) {
    this.listeners.add(onPush);
    void this.call('listen');
    return () => { this.listeners.delete(onPush); };
  }

  sendCode(email: string) { return this.call<{ ok: true } | { ok: false; reason: CodeRefusal; wait: number }>('sendCode', email); }
  verifyCode(email: string, code: string, replace = false) {
    return this.call<{ ok: true } | { ok: false; reason: VerifyRefusal; left: number; deleteAfter: string; device?: string; lastSeen?: string }>('verifyCode', email, code, replace);
  }
  signOut(remove: boolean) { return this.call<void>('signOut', remove); }
  activateTrial() { return this.call<Result>('activateTrial'); }
  checkPlan() { return this.call<void>('checkPlan'); }
  agree(c: Consent) { return this.call<Result>('agree', c); }

  testMailbox(m: { provider: MailProvider; address: string; appPassword: string }) { return this.call<Result<{ found: number; as: string }>>('testMailbox', m); }
  testCams(c: { email: string }) { return this.call<Result<{ arn: string; name: string }>>('testCams', c); }
  testKfintech(k: { username: string; password: string; expect?: string }) { return this.call<Result<{ as: string; arn: string; name: string; gstin: string }>>('testKfintech', k); }
  prepareSignature(photo: { bytes: string }) { return this.call<Result<{ image: string }>>('prepareSignature', photo); }
  rotateSignature() { return this.call<{ image: string }>('rotateSignature'); }
  dropSignatureDraft() { return this.call<void>('dropSignatureDraft'); }
  saveSetup(state: unknown) { return this.call<void>('saveSetup', state); }
  loadSetup() { return this.call<SetupState | null>('loadSetup'); }
  dropSetup() { return this.call<void>('dropSetup'); }
  findCertificates() { return this.call<{ certs: Cert[] }>('findCertificates'); }
  testCertificate(c: { thumbprint: string; route: Cert['route'] }) {
    return this.call<{ ok: true } | { ok: false; said: string; other: boolean }>('testCertificate', c);
  }
  reconnect() { return this.call<{ online: boolean }>('reconnect'); }
  tokenHere() { return this.call<boolean>('tokenHere'); }
  finishSetup(p: ProfileDraft, adding: boolean) { return this.call<Result>('finishSetup', p, adding); }
  saveDetails(p: DetailsPatch) { return this.call<Result>('saveDetails', p); }
  switchArn(arn: string) { return this.call<void>('switchArn', arn); }

  month(period: string) { return this.call<Month>('month', period); }
  preview(key: string) { return this.call<string>('preview', key); }
  previewInvoice(settings: InvoiceSettings & { name?: string; gstin?: string; signatureSize?: number; way?: string; certName?: string }, number: string) { return this.call<string>('previewInvoice', settings, number); }
  previewRegistrar(p: { kind: 'cams' | 'kfintech'; name: string; gstin: string; arn: string; signatureSize: number; way?: string; certName?: string }) { return this.call<string>('previewRegistrar', p); }
  exportMonth(period: string) { return this.call<Result<{ name: string }>>('exportMonth', period); }
  openPdf(key: string) { return this.call<void>('openPdf', key); }
  showInFolder(key: string) { return this.call<void>('showInFolder', key); }
  openFolder(what: Registrar | 'files', period?: string) { return this.call<void>('openFolder', what, period ?? ''); }
  uninstall() { return this.call<string>('uninstall'); }
  skipCams(run: string) { return this.call<void>('skipCams', run); }
  forwardClaim(email: string) { return this.call<{ ok: boolean; said?: string }>('forwardClaim', email); }
  forwardState() { return this.call<{ proved: boolean; confirm: string; said?: string }>('forwardState'); }
  forwardConfirm() { return this.call<boolean>('forwardConfirm'); }
  sendIdea(s: { text: string; picture?: { name: string; data: string } }) { return this.call<{ sent: boolean }>('sendIdea', s); }
  answerSurvey(id: number, answers: SurveyAnswers | null) { return this.call<{ sent: boolean }>('answerSurvey', id, answers); }
  booksLook(q: BooksLookQuery) { return this.call<BooksLook>('booksLook', q); }
  booksImport(q: BooksLookQuery & { adopt: string[] }) { return this.call<BooksLook>('booksImport', q); }
  booksNext(q: { company?: string; arn?: string; kind?: '' | 'tally' | 'zoho'; orgId?: string } = {}) { return this.call<{ state: string; company: string; last: string; next: string; at: number; method: string }>('booksNext', { company: q.company ?? '', arn: q.arn ?? '', kind: q.kind ?? '', orgId: q.orgId ?? '' }); }
  refreshBooks(run: string) { return this.call<void>('refreshBooks', run); }
  booksSetup(q: { kind: 'tally' | 'zoho'; gstin: string; arn?: string }) { return this.call<BooksSetup>('booksSetup', { kind: q.kind, gstin: q.gstin, arn: q.arn ?? '' }); }
  booksUse(q: { kind: 'tally' | 'zoho'; pick: TallyPick | ZohoPick }) { return this.call<{ ok: boolean }>('booksUse', q); }
  booksForget() { return this.call<{ ok: boolean }>('booksForget'); }
  zohoConnect(arn = '') { return this.call<ZohoConnect>('zohoConnect', arn); }
  zohoCancel() { return this.call<void>('zohoCancel'); }
  zohoDisconnect(arn = '') { return this.call<{ ok: boolean }>('zohoDisconnect', arn); }
  camsFilesStart() { return this.call<CamsFiles>('camsFilesStart'); }
  checkMail() { return this.call<{ got: { period: string; count: number }[]; waiting: string[]; said: string }>('checkMail'); }
  chooseCamsFiles() { return this.call<CamsFiles>('chooseCamsFiles'); }
  dropCamsFiles(files: { name: string; bytes: string }[]) { return this.call<CamsFiles>('dropCamsFiles', files); }
  pickFile(kind: 'zip' | 'xls') { return this.call<{ kind: string; name: string }>('pickFile', kind); }
  dropFile(f: { name: string; bytes: string }) { return this.call<{ kind: string; name: string }>('dropFile', f); }

  startRun(r: { registrars: Registrar[]; period: string; what: RunKind; periods?: string[]; last?: NextNumber | null }) { return this.call<{ run: string; said?: string }>('startRun', { ...r, periods: r.periods ?? null, last: r.last ?? null }); }
  answer(id: string, a: Answer) { void this.call('answer', id, a); }
  stopRun(run: string) { void this.call('stopRun', run); }
  closeRun(run: string) { void this.call('closeRun', run); }

  markNotesRead() { return this.call<void>('markNotesRead'); }
  sendSupport(s: { text: string; where: string }) { return this.call<{ sent: boolean }>('sendSupport', s); }
  open(link: Link) { return this.call<void>('open', link); }
  checkForUpdates() { return this.call<{ upToDate: boolean }>('checkForUpdates'); }
  updateNow() { return this.call<void>('updateNow'); }
  here(place: Place) { return this.call<void>('here', place); }
  quit() { void this.call('quit'); }
}
