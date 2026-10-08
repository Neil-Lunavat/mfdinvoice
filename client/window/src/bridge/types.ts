/* The boundary between the window and the app, as types. The app's side is `client/src/client/hands/window.py`.

   Two directions:
     the app tells the window   → `Push`, delivered to the listener passed to `App.listen`
     the window asks the app    → the methods of `App`, each returning a promise

   Everything the window draws comes from the app's local store (`Snapshot`), so the window renders straight away and
   never waits on the network. */

export type CamsFiles = {
  added: { period: string; count: number; name: string }[];
  refused: { name: string; why: string }[];
  waiting: { name: string; why: string }[];
  said?: string;
};

export type Registrar = 'CAMS' | 'KFINTECH';

/** The one status vocabulary. Both registrars are mapped onto these words. */
export type Status =
  | 'Not submitted' | 'Fetched' | 'Signed' | 'Checked' | 'Needs your attention' | 'Submitted'
  | 'Waiting approval' | 'Approved' | 'Rejected' | 'Mismatch';

/** A hard day. A required update is separate: it blocks everything. */
export type Condition = 'normal' | 'offline' | 'down';

// --- what the window reads: the app's local store --------------------------------------------------------------

export interface Snapshot {
  version: string;                 // the app's own version, e.g. "0.9.2"
  condition: Condition;
  network: { online: boolean; retryAt: number };   // retryAt: epoch ms of the next automatic try while offline
  update: UpdateInfo | null;       // this app must update, and no run is going here: nothing else is usable
  account: Account | null;         // null: signed out on this PC
  arns: ArnSummary[];              // every ARN on the account, in the switcher's order
  arn: string;                     // the selected ARN; '' when none is set up yet
  today: string;                   // ISO date on this PC
  profile: Profile | null;         // the selected ARN's details
  month: Month | null;             // this month, for the selected ARN
  year: MonthRow[];                // the financial year's months, newest first
  notes: Note[];                   // the bell, newest first
  activity: ActivityEntry[];       // Settings › History, newest first. Never edited.
  fy: string;                      // the financial year the months are in, "2026-27"
  run: RunInProgress | null;       // a run the app believes is still going for this ARN
  clash: Clash | null;             // the CAMS email moved away from the mailbox; kept by the app until settled
  plan: Plan | null;               // what the account's plan says, as the website last said it; null before it has
  survey?: SurveyAsk | null;       // a survey written in the panel, asked on Overview until answered or closed
  deleting: string;                // signed out because the account's deletion was asked for: the ISO time it goes; else ''
}

/** The account's plan, from the website. 'unknown' is the website giving no answer just now, never "no plan".
    `arns`: the ARNs bound to the account; an ARN set up on this PC that is not among them cannot run. */
export interface Plan {
  state: 'active' | 'none' | 'ended' | 'unknown';
  source: '' | 'paid' | 'grant' | 'trial';  // shown as a plan or a free trial; never "gift"
  until: string;                   // the plan's last day, YYYY-MM-DD; '' when none
  slots: number;
  arns: string[];                  // ARN-… bound to the account, at most `slots` of them
  trialUsed?: boolean;             // this email has had its free trial (one per email, even after deleting the account)
  checkedAt: string;
}

/** A survey from the website's panel (website/site/src/lib/surveys.ts). No question is required. */
export interface SurveyAsk { id: number; title: string; questions: SurveyQuestion[] }
export interface SurveyQuestion { key: string; q: string; type: 'one' | 'many' | 'text'; options: string[]; other: boolean }
export type SurveyAnswers = Record<string, { picked: string[]; text: string }>;

/** The person's authority to act for an ARN: the sentence ticked at setup, on the CAMS and KFintech steps. */
export interface Consent {
  version: number;
  text: string;                    // exactly as shown
  at: string;                      // ISO time it was ticked
  device?: string;                 // the PC it was ticked on, as the app keeps it
}

/** The mailbox clash: the run waits until the person picks a mailbox. */
export interface Clash {
  mailbox: string;                 // the address the mailbox still reads
  camsEmail: string;               // where CAMS now sends, masked (p***@gmail.com): it is a credential
}

export interface UpdateInfo {
  version: string;
  why: string;                     // one plain sentence, e.g. "CAMS changed its upload page. This version handles it."
  failed: boolean;                 // the last try installed it but it didn't start, so this PC went back
}

/** Why [Update now] didn't get as far as installing. */
export type UpdateFailure = 'no_plan' | 'signed_out' | 'missing' | 'unreachable' | 'mismatch' | 'not_installed' | 'failed';

/** Where the window is, so an update comes back there. */
export interface Place { page?: string; section?: string; month?: string }

export interface Account {
  email: string;
  maxArns: number;                 // 6
}

export interface ArnSummary {
  arn: string;
  name: string;
  status: 'Not submitted' | 'Submitted' | 'Approved' | 'Rejected';
  rejected: number;
}

export type MailProvider = 'forward' | 'gmail' | 'folder';   // forwarded to us, Gmail with an app password, or by hand

export interface Profile {
  arn: string;
  name: string;                    // name on invoices
  gstin: string;
  arnConfirmed: boolean;           // a portal's sign-in showed this ARN at setup, and it is bound to the account
  bindOnRun?: boolean;             // set up without KFintech: bound by the first run that reads CAMS's emailed files
  bindAsked?: boolean;             // ...and the person has pressed Activate free trial for it, so runs are on
  camsUsed: boolean;               // false: this ARN has nothing on CAMS, so a run leaves CAMS out
  camsEmail: string;               // masked, p***@gmail.com: the email itself is in the app's vault
  camsArn: string;                 // the ARN CAMS showed when this email was tested; '' while it has not been
  mailbox: { provider: MailProvider; address: string; connected: boolean };
  kfintech: Kfintech;              // username masked (pri***), like the email
  signature: Signature;           // the person's way of signing
  invoices: Invoices;              // which invoice is uploaded, and the person's own
  lastLogin: { CAMS: string; KFINTECH: string };                  // ISO dates, '' if never
  books: '' | 'tally' | 'zoho';    // the books connected to this ARN: its own invoices go into them during a run
  usedTop: string;                 // own invoices without books: the highest invoice number used this financial year; ''
  kept: { kind: '' | 'tally' | 'zoho'; company: string; gstin?: string; ledgers: number };   // the Tally company or Zoho Books organisation this ARN imports into, its GSTIN there, and how many fund houses are matched
  consent: Consent | null;         // what was agreed at setup, on the CAMS and KFintech steps; null for an ARN set up before it was asked
}

/** The KFintech login. `arn`: the ARN KFintech showed when the login was tested, '' before a test passes. */
export interface Kfintech { used: boolean; username: string; loggedInAs: string; arn: string }

/** How the person signs: their stamped image or a USB DSC, chosen by them, either way as good.
    `present`: the chosen way is set up. The other way's setup is kept, so switching back costs nothing. */
export interface Signature {
  way: 'image' | 'dsc';
  present: boolean;
  image: string;                   // a data URL made on this PC, for display; '' when no photo was given
  size: number;                    // the image's size, 60-140
  cert: Cert | null;               // the token's certificate picked, when there is one
}

/** A signing certificate on a USB token, as the person recognises it. Never a key, never a PIN. */
export interface Cert {
  thumbprint: string;
  name: string;                    // who it is issued to
  issuer: string;                  // which certifying authority
  expires: string;                 // ISO date
  route: 'windows' | 'pin';        // pin: the token's driver is used and its PIN is typed in our window
  tested: boolean;                 // a test signature worked on this PC
}

/** The person's own invoice: what Settings calls theirs. Everything else on it - the fund
    house, the figures, the dates - is the registrar's. */
export interface InvoiceSettings {
  template: 'tally';               // one template to begin with: the Tally standard print
  address: string[];               // their address block, one line each
  phone: string;
  email: string;
  website: string;
  particulars: string;             // the item line's wording, e.g. "Commission"
  particularsAmc: boolean;         // with the fund house's name in front
  remarks: string;
}

/** Which invoice is uploaded (setup's "Your invoices"). `last` and `at`: the last number they issued, exactly as
    printed, and where the part that goes up by 1 starts. '' before the person has chosen. */
export interface Invoices {
  source: '' | 'registrar' | 'own';
  last: string;
  at: number;
  settings: InvoiceSettings;
}

export interface Invoice {
  key: string;                     // the CAMS invoice number or the KFintech reference
  registrar: Registrar;
  amc: string;                     // the fund house, as the person knows it
  number: string;                  // the number printed on the invoice
  date: string;                    // ISO date on the invoice
  taxable: number;
  cgst: number;
  sgst: number;
  igst: number;
  status: Status;
  said: string;                    // the registrar's own words for the status (shown on hover)
  rejection: string;               // the registrar's words when it rejected it, else ''
  timeline: { what: string; when: string; who?: string }[];   // when: ISO date
  gstin: string;                   // the fund house's GSTIN, as its invoice prints it; '' on one read before it was kept
  tally: string;                   // its number in the person's Tally once imported ('in': there, number not known), else ''
  books?: string;                  // ... the same in Zoho Books, or in either from 8 Oct on
}

/** One invoice against the person's books: what an import would do with it. `number`: the one it has there;
    `will`: the one it will get. `refused`: the books' own words, after an import that did not take it. The person's own
    invoices are never imported here: `run` (they go in during their run) and `past` (already sent). */
export interface BooksRow {
  key: string; registrar: Registrar; amc: string; date: string; total: number; submitted: boolean; gstin: string;
  number: string; will: string; party: string; partyNew: boolean; sales: string;
  action: 'import' | 'in_books' | 'by_hand' | 'ask' | 'stop' | 'later' | 'run' | 'past';
  note: string; refused?: string;
}

/** A look at a month against the person's books. `kind`: which. `state`: none (no books chosen yet), connect (Zoho
    Books needs letting in), off (no answer), closed (Tally: no company open), pick (several companies or organisations
    and none is remembered), ready. `tallyNumbers`: Tally gives the numbers itself and ignores any sent.
    `askLast`: we number them, so the person's last invoice number is asked. `done`: what an import just did. */
export interface BooksLook {
  kind: '' | 'tally' | 'zoho';
  state: 'none' | 'connect' | 'off' | 'closed' | 'pick' | 'ready';
  said: string; companies: string[]; orgs?: { id: string; name: string }[]; orgId?: string; company: string; period: string; label: string; own: boolean;
  which: 'submitted' | 'all'; vtype: string; method: string; tallyNumbers: boolean; last: string; askLast: boolean;
  rows: BooksRow[];
  creates: { kind: 'party' | 'tax' | 'sales'; name: string; gstin: string }[];
  asks: { id: string; question: string; options: string[] }[];
  warn: string[];
  counts: { submitted: number; all: number; going: number; byHand: number; inBooks: number };
  done?: { imported: string[]; adopted: string[]; numbers: string[]; stoppedAt: string;
           refused: { key: string; amc: string; said: string }[] };
}

export interface BooksLookQuery { period: string; company: string; which: 'submitted' | 'all'; last: string; answers: Record<string, string>; kind?: '' | 'tally' | 'zoho'; orgId?: string }

export interface Month {
  period: string;                  // CAMS's payment month, e.g. "OCT-2026"
  label: string;                   // "October 2026"
  kfLabel: string;                 // KFintech's trail month for the same invoices: "September 2026"
  deadline: string;                // unused: the person keeps their own dates
  checkedAt: string;               // ISO date-time of the last status check, '' if never
  listed: boolean;                 // its invoices are on this PC, or a registrar listed them at the last look
  notListed: Registrar[];          // the registrars that did not list the month yet, at the last look
  everRun: boolean;                // any run has ever been done for this ARN
  submittedOn: string;             // ISO date of the first submit this month, '' if none
  lastRun: LastRun | null;         // how this month's latest run ended; null when it has never been run
  camsWaiting?: boolean;           // CAMS was asked for its email and its files aren't in yet
  invoices: Invoice[];             // nothing is here until it has been fetched
}

/** An own invoice number, exactly as printed, and where its part that goes up by 1 starts. */
export interface NextNumber { text: string; at: number }

/** This month's latest run, as it was recorded. `said` is the Stopped screen's heading; `portal` the portal's own
    words, if it gave any; `code` which stop it was (`not_listed`: the registrars list nothing yet). */
export interface LastRun {
  how: 'done' | 'stopped' | 'nothing' | 'going';
  at: string;                      // ISO date-time it ended (or started, while going)
  said: string;
  portal: string;
  code: string;
}

export interface MonthRow {
  period: string;
  label: string;
  count: number;
  total: number;
  status: 'Not submitted' | 'Submitted' | 'Approved' | 'Rejected';
  rejected: number;
}

export interface Note {
  id: string;
  kind: string;                    // what it is about (ui.notify `kind`)
  text: string;                    // one plain sentence
  detail: string;                  // the second line, '' if none
  opens: 'overview' | 'invoices' | 'settings' | '';
  when: string;                    // ISO date-time
  read: boolean;
}

export interface ActivityEntry {
  at: string;                      // ISO date-time
  text: string;                    // a plain sentence: "Got 11 invoices by email (ref 224851745)"
  registrar: Registrar | null;
  who: string;                     // "you, on this PC" · "OFFICE-PC" · '' when the software did it
  tone: 'plain' | 'bad' | 'setting';
}

export interface RunInProgress {
  run: string;
  registrars: Registrar[];
  startedAt: string;
  what: RunKind;
  period: string;
}

// --- the run: what the app pushes -------------------------------------------------------------------------------

/** A run of the month, a look at what the registrars have, or the month's invoices fetched onto this PC. */
export type RunKind = 'run' | 'check' | 'download';

/** One of the run's steps. All of them arrive every time, in order; their names and lines are the app's. */
export interface StepView {
  index: number;
  name: string;                    // "Check", "Your check", "CAMS"
  state: 'waiting' | 'running' | 'done' | 'bad';
  line: string;                    // what it is doing now: "Signing in to KFintech"
  result: string;                  // its one-line result once done
}

/** A row at Your check. Its PDF's first page comes from `App.preview(key)`. */
export interface CheckRow {
  key: string;
  registrar: Registrar;
  amc: string;
  number: string;                  // own invoices: the number it gets if every row before it stays ticked; else ''
  seq?: number;                    // own invoices: its place in the number order (see logic/check `numbersFor`)
  kept?: boolean;                  // own invoices: it already holds its number for good
  taxable: number;
  gst: number;
  igst: boolean;
  included: boolean;               // false: it starts unticked (it was left out last time)
  blocked: string;                 // why this run cannot send it, '' when it can; a blocked row cannot be ticked
  note?: string;                   // own invoices with books: "In Tally as 74/26-27, not sent yet", or typed there by hand
  renumber?: { date: string; type: string };   // own invoices with books: Tally would renumber the invoices after it
  rejection: string;               // the registrar's words when it rejected it before, else ''
}

/** Why a run stopped, in the app's words. The run is over when this arrives; nothing is answered. */
export interface Stop {
  kind: string;                    // which stop (logic/stops.ts)
  title: string;
  said: string;                    // the portal's own words, quoted as they are; '' if none
  lines: string[];                 // one or two plain sentences
  so_far: string;                  // what each registrar got to
  registrar: Registrar | null;
  others?: Omit<Stop, 'so_far' | 'others'>[];   // the other registrar's stop, when both stopped: each has its own block
}

/** A question the app puts to the person. Each carries an id; the window answers with `App.answer(id, …)`. */
export type Ask =
  | {
      id: string; type: 'captcha';
      image: string;                                     // data URL of the cropped captcha, made on this PC
      attempt: number;                                   // 1 first; later ones say "not quite"
      message: string;
      during: 'run' | 'setup';
    }
  | { id: string; type: 'signature'; key: string; amc: string }     // the first run: one signed invoice to look at
  | { id: string; type: 'pick_files'; month: string; sentTo: string; skip: boolean; message: string }   // CAMS's zip and Excel, from the person; skip: CAMS may be left out instead
  | {
      id: string; type: 'pin';                          // a token Windows cannot reach. Never stored.
      said: string;                                      // the token's words after a wrong PIN, '' the first time
      during: 'run' | 'setup';
    }
  | { id: string; type: 'your_check'; rows: CheckRow[]; notes: string[]; books?: BooksNote | null }
  | { id: string; type: 'books_ask'; asks: BooksQuestion[] };   // Tally's questions: which kind of sales voucher, which ledger

/** Own invoices with books connected: what Your check says about them. `after`: the month of a newer invoice already
    in the books ("September"). `first`: a new financial year with Manual numbering and no invoice yet, so the
    person types its first invoice number (proposed from last year's style). */
export interface BooksNote { kind: 'tally' | 'zoho'; company: string; after: string; first: { fy: string; proposed: string } | null;
  creates: { kind: 'party' | 'tax' | 'sales'; name: string; gstin: string }[] }
export interface BooksQuestion { id: string; question: string; options: string[] }
/** Own invoices without books, submitted: what the person enters in their books. */
export interface Entered { registrar: Registrar; amc: string; key: string; number: string }
/** Own invoices the books would not take this run: the fund house and the books' words. */
export interface Left { amc: string; why: string }

export type Answer =
  | { type: 'captcha'; text: string; refresh: boolean }
  | { type: 'signature'; looksRight: boolean; fixed: boolean }   // fixed: changed in place, so sign it again
  | { type: 'pick_files'; skip?: boolean }                 // both files are in (`pickFile`, `dropFile`), or CAMS is skipped
  | { type: 'pin'; value: string | null }                 // goes to the token, kept nowhere; null: closed
  | { type: 'your_check'; confirmed: boolean; included: string[]; first?: string; dated?: string[] }
  // first: the new year's first invoice number. dated: the invoices
  // to date the day they are sent, because Tally would renumber the ones after them
  | { type: 'books_ask'; answers: Record<string, string> };

/** Everything the app tells the window. */
export type Push =
  | { type: 'snapshot'; snapshot: Snapshot }             // the local store changed; the window redraws from it
  | { type: 'steps'; run: string; steps: StepView[] }
  | { type: 'ask'; ask: Ask }
  | { type: 'ask_withdrawn'; id: string }                // the question no longer needs an answer
  | { type: 'notify'; kind: string; text: string; opens: Note['opens']; toast: boolean }
  | { type: 'run_month'; run: string; period: string; index: number }       // a download of several months: on this one now
  | { type: 'waiting_email'; run: string; since: string; ref: string; skip?: boolean; months?: string[] }   // CAMS has been asked; its email is awaited (skip: Skip CAMS is offered; months: several months' emails awaited together)
  | { type: 'submitted'; run: string; registrar: Registrar; count: number } // the registrar's status shows them
  | { type: 'books_waiting'; run: string; on: boolean; company: string; said: string; kind: 'tally' | 'zoho' }   // the run waits for the books (on), or no longer
  | { type: 'run_ended'; run: string; how: 'done' | 'stopped' | 'nothing'; what: RunKind;
      used: string;                                      // own invoices: "Used 74/26-27 to 78/26-27"
      enter: Entered[];                                  // own invoices without books, submitted: to enter in their books
      left: Left[];                                      // own invoices the books would not take this run
      summary: string;                                   // "17 invoices submitted for October. 2 left for later."
      counts: Partial<Record<Registrar, number>>; total: number;
      stop: Stop | null }                                // why it stopped; null when it finished or the person stopped it
  | { type: 'update_progress'; pct: number }             // downloading; at 100 the app hands over to the installer
  | { type: 'update_failed'; reason: UpdateFailure }
  | { type: 'go'; place: Place }                         // just updated: back where the person was
  | { type: 'close_requested' };                         // the person pressed the window's close button

// --- what the window asks the app -------------------------------------------------------------------------------

/** `said`: why not. The portal's own words, quoted as such, unless `ours`: then it is our own sentence. */
export type Result<T = object> = ({ ok: true } & T) | { ok: false; said: string; ours?: boolean; changed?: boolean };   // changed: a portal's page misbehaved twice in a row

export interface ProfileDraft {
  arn: string;
  name: string;
  gstin: string;
  camsUsed: boolean;
  camsEmail: string;               // as typed, in setup or a Change; empty in a Change until the person types it
  camsArn: string;                 // the ARN CAMS showed for that email; '' until Verify sign-in passes, and after an edit
                                   // In setup `arn` is read, not typed: the first portal verified sets it, the second must show the same.
  mailbox: { provider: MailProvider; address: string; connected: boolean };
  kfintech: Kfintech;
  signature: Signature;
  invoices: Invoices;
  consent: Consent | null;         // what setup keeps: made from `ticks` when it finishes; required to finish setup
  ticks?: { cams: Consent | null; kfintech: Consent | null };   // setup's ticks, one on each registrar's step
  tally?: TallyPick;               // setup's books step: the Tally company the invoices go into; absent when skipped
  zoho?: ZohoPick;                 // ... or the Zoho Books organisation (one of the two)
}

/** The Tally company chosen at setup. `sure`: its GSTIN differs from this ARN's and the person said it is the one. */
export interface TallyPick { company: string; guid: string; gstin: string; same: boolean; sure: boolean }
/** What Tally says at setup: `off` (no answer), `closed` (no company open), `ready` (the companies open now). */
export interface TallySetup { state: 'off' | 'closed' | 'ready'; companies: { name: string; guid: string; gstin: string; same: boolean }[] }
/** The Zoho Books organisation chosen at setup (`sure`: as for Tally). */
export interface ZohoPick { orgId: string; org: string; gstin: string; same: boolean; sure: boolean }
export interface ZohoOrg { id: string; name: string; gstin: string; same: boolean }
/** What the books say at setup, either kind: Tally fills `companies`, Zoho Books `orgs`. `said`: why not, in Zoho's words. */
export interface BooksSetup { state: 'off' | 'closed' | 'ready'; said: string; companies: TallySetup['companies']; orgs: ZohoOrg[] }
/** Letting Zoho Books in, in the person's own browser: `state` says why not (cancelled, denied, timeout, off). */
export type ZohoConnect = { ok: true } | { ok: false; state: 'cancelled' | 'denied' | 'timeout' | 'off'; said: string }

export type DetailsPatch = Partial<Omit<ProfileDraft, 'arn' | 'consent' | 'ticks'>>;

/** Every answer the website gives to sign-in, in its own code (`website/site/API.md`); `unreachable`: no answer. */
export type CodeRefusal = 'bad_email' | 'no_account' | 'wait' | 'locked' | 'too_many_codes' | 'send_failed' | 'unreachable';
export type VerifyRefusal = 'bad_email' | 'bad_code' | 'wrong' | 'locked' | 'expired' | 'pending_deletion' | 'unreachable';

export type Link = 'site' | 'signup' | 'status' | 'billing' | 'help';

export interface App {
  /** Read the local store. Answers from disk; never waits on the network. */
  load(): Promise<Snapshot>;
  /** Start hearing pushes. Returns a function that stops them. */
  listen(onPush: (p: Push) => void): () => void;

  // sign in, with the website (wait: seconds before another code may be sent; left: tries; deleteAfter: ISO time)
  sendCode(email: string): Promise<{ ok: true } | { ok: false; reason: CodeRefusal; wait: number }>;
  verifyCode(email: string, code: string): Promise<{ ok: true } | { ok: false; reason: VerifyRefusal; left: number; deleteAfter: string }>;
  /** Sign out of this PC; `remove`: also take the passwords and the signature off it. */
  signOut(remove: boolean): Promise<void>;

  // the plan
  /** Bind the ARN on screen to the account: on one that has never had a plan, the 15-day free trial starts now;
      on one with a plan, the ARN takes a free slot. */
  activateTrial(): Promise<Result>;
  checkPlan(): Promise<void>;                            // Try again, on "We couldn't check your plan just now"
  agree(c: Consent): Promise<Result>;                    // the authority sentence, ticked again for the ARN on screen

  // setup, and every "Change" (the same controls)
  testMailbox(m: { provider: MailProvider; address: string; appPassword: string }): Promise<Result<{ found: number; as: string }>>;
  /** Sign in to CAMS with this email, once, and read the ARN CAMS shows. `arn`: the ARN being set up. */
  testCams(c: { email: string }): Promise<Result<{ arn: string; name: string }>>;
  /** A test login; `arn` in the answer is the ARN KFintech shows. A captcha Ask arrives meanwhile. */
  testKfintech(k: { username: string; password: string; expect?: string }): Promise<Result<{ as: string; arn: string; name: string; gstin: string }>>;
  prepareSignature(photo: { bytes: string }): Promise<Result<{ image: string }>>;   // the photo, base64; cleaned on this PC
  rotateSignature(): Promise<{ image: string }>;
  /** A photo that was prepared and then not kept (Discard, Cancel, a setup begun afresh): forget it. */
  dropSignatureDraft(): Promise<void>;
  /** The signing certificates on the USB tokens plugged in now. */
  findCertificates(): Promise<{ certs: Cert[] }>;
  /** A test signature with this certificate: the token's own software asks for its PIN (on route 'pin', a `pin` Ask
      arrives). `other`: it did not sign through Windows, but trying with the PIN typed here may work. */
  testCertificate(c: { thumbprint: string; route: Cert['route'] }): Promise<{ ok: true } | { ok: false; said: string; other: boolean }>;
  /** Is the token this ARN signs with plugged in? true for the image. */
  tokenHere(): Promise<boolean>;
  /** Check the network at once; answers when that check is done. */
  reconnect(): Promise<{ online: boolean }>;
  finishSetup(p: ProfileDraft, adding: boolean): Promise<Result>;
  saveDetails(p: DetailsPatch): Promise<Result>;
  switchArn(arn: string): Promise<void>;

  // the month
  month(period: string): Promise<Month>;
  preview(key: string): Promise<string>;                  // the signed PDF's first page as a data URL, '' if none yet
  /** The person's own invoice with these settings, drawn on this PC with their signature where it goes: its first
      page as a data URL, '' when it could not be drawn. `signatureSize`: the size on screen, 60-140. */
  previewInvoice(settings: InvoiceSettings & { name?: string; gstin?: string; signatureSize?: number }, number: string): Promise<string>;
  /** An example of a registrar's own invoice, made out to this person, with their signature where a run puts it:
      its first page as a data URL, '' when it could not be drawn. */
  previewRegistrar(p: { kind: 'cams' | 'kfintech'; name: string; gstin: string; arn: string; signatureSize: number }): Promise<string>;
  exportMonth(period: string): Promise<Result<{ name: string }>>;
  openPdf(key: string): Promise<void>;
  showInFolder(key: string): Promise<void>;
  openFolder(what: Registrar | 'files', period?: string): Promise<void>;
  uninstall(): Promise<string>;
  skipCams(run: string): Promise<void>;                    // while CAMS's email is awaited: go on with KFintech
  /** Forwarding CAMS's mailbacks to us: a code to the CAMS email, then that code typed here proves it is theirs. */
  forwardStart(email: string): Promise<{ ok: boolean; said?: string }>;
  forwardVerify(email: string, code: string): Promise<{ ok: boolean; said?: string }>;
  /** Gmail's forwarding confirmation code, once Gmail has sent it to our address; '' until then. */
  forwardGmailCode(): Promise<string>;                            // starts Windows' uninstaller and closes; '' or why not ('not_installed')
  /** What importing a month into the person's books (Tally or Zoho Books) would do. Nothing in the books changes. */
  booksLook(q: BooksLookQuery): Promise<BooksLook>;
  /** Put the month in. `adopt`: the invoices typed by hand to change to the registrar's figures. */
  booksImport(q: BooksLookQuery & { adopt: string[] }): Promise<BooksLook>;
  /** Where the person's own invoice numbers continue from, in their books; `company`, `arn` and `kind` while setup is still open. */
  booksNext(q?: { company?: string; arn?: string; kind?: '' | 'tally' | 'zoho'; orgId?: string }): Promise<{ state: string; company: string; last: string; next: string; at: number; method: string; bare?: boolean }>;
  /** Refresh, while a run waits for the books. */
  refreshBooks(run: string): Promise<void>;
  /** Setup's books step: the companies open in Tally, or the organisations in Zoho Books, each with its GSTIN beside this ARN's. */
  booksSetup(q: { kind: 'tally' | 'zoho'; gstin: string; arn?: string }): Promise<BooksSetup>;
  /** Use these books for this ARN from now on (Settings, the Books tab): the other kind is let go of. */
  booksUse(q: { kind: 'tally' | 'zoho'; pick: TallyPick | ZohoPick }): Promise<{ ok: boolean }>;
  /** Forget what was chosen for this ARN (Zoho Books is also revoked). */
  booksForget(): Promise<{ ok: boolean }>;
  /** Open Zoho's Accept page in the person's browser and wait for them (up to 5 minutes). */
  zohoConnect(arn?: string): Promise<ZohoConnect>;
  /** The person gave up waiting. */
  zohoCancel(): Promise<void>;
  /** Let go of Zoho Books for this ARN; its access is revoked at Zoho. */
  zohoDisconnect(arn?: string): Promise<{ ok: boolean }>;
  /** CAMS's files for any months, at once. Opening the box clears it; each call returns the box's whole state so far. */
  camsFilesStart(): Promise<CamsFiles>;
  checkMail(): Promise<{ got: { period: string; count: number }[]; waiting: string[]; said: string }>;   // CAMS's emails looked for now
  chooseCamsFiles(): Promise<CamsFiles>;
  dropCamsFiles(files: { name: string; bytes: string }[]): Promise<CamsFiles>;
  /** One of CAMS's two files, from Windows' own Open box. Only the file's name comes back ('' if cancelled). */
  pickFile(kind: 'zip' | 'xls'): Promise<{ kind: string; name: string }>;
  /** A file dropped on the window, as base64: a zip is CAMS's invoices, an Excel its report. `kind` '' if neither. */
  dropFile(f: { name: string; bytes: string }): Promise<{ kind: string; name: string }>;

  // the run
  /** Start a run of the month, a look at what the registrars have, or a download of the month's invoices. `last`: the
      last invoice number in the person's books, as they just confirmed it. `said`: why it did not start. */
  /** `periods`: a download of several months, one after the other, in one go (`period` is the first). */
  startRun(r: { registrars: Registrar[]; period: string; what: RunKind; periods?: string[]; last?: NextNumber | null }): Promise<{ run: string; said?: string }>;
  answer(id: string, a: Answer): void;
  stopRun(run: string): void;                             // Stop: ends now, or right after a Submit's answer
  closeRun(run: string): void;                            // the window closed mid-run and the person confirmed

  // the rest
  markNotesRead(): Promise<void>;
  /** Send to support: what the person wrote and where, with the app's version, this PC and the app's last log
      lines. Nobody is answered from it; `sent` is all that comes back. */
  sendSupport(s: { text: string; where: string }): Promise<{ sent: boolean }>;
  /** Settings › Send an idea: the words, and a picture the person chose (base64, at most 5 MB), to the software's
      server as an idea. Nothing is answered: the idea is read. */
  sendIdea(s: { text: string; picture?: { name: string; data: string } }): Promise<{ sent: boolean }>;
  /** The survey's answers, or its X (null): either way it isn't asked again. */
  answerSurvey(id: number, answers: SurveyAnswers | null): Promise<{ sent: boolean }>;
  open(link: Link): Promise<void>;
  checkForUpdates(): Promise<{ upToDate: boolean }>;
  updateNow(): Promise<void>;                             // progress arrives as `update_progress`, then the app restarts
  here(place: Place): Promise<void>;                      // where the window is now
  quit(): void;
}
