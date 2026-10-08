/* The consent record: one sentence and a required tick on each registrar's setup step (CAMS, KFintech), kept per ARN
   once setup finishes. The wording has a version; a new wording asks again (Overview), and Settings › Your details shows what was agreed and when. */

import type { Consent } from '../bridge/types';
import { NAME } from '../brand';

export const CONSENT_VERSION = 1;

/** The sentence for the registrars it covers: ['CAMS'], ['KFintech'], or both. */
export const consentText = (names: string[]) => `I authorise ${NAME} to sign in and act for me on ${names.join(' and ')}.`;

/** The tick, as the software keeps it: this wording, now. */
export const consentNow = (names: string[]): Consent => ({ version: CONSENT_VERSION, text: consentText(names), at: localNow() });

/** Agreed to the wording in use. An ARN set up before it was asked, or under an older wording, is asked again. */
export const consentCurrent = (c: Consent | null | undefined) => !!c && c.version >= CONSENT_VERSION;

function localNow() {
  const d = new Date(), p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}
