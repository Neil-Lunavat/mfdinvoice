/* The questions asked while a payment is checked (Checkout's "we're checking" screens). All optional. Answers are
   stored one row per answer (the `answers` table), so questions can be added, or a new survey started, without a
   schema change. An answer is an option's key; "other" also stores the typed text under `<key>_other`. */

export const SURVEY = 'after_payment';

export type Question = { key: string; q: string; options: [key: string, label: string][]; other?: string };

export const QUESTIONS: Question[] = [
  { key: 'heard', q: 'Where did you hear about us?', other: 'other', options: [
    ['team', 'Someone from our team'], ['mfd', 'Another MFD'], ['google', 'Google'],
    ['whatsapp', 'A WhatsApp group'], ['youtube', 'YouTube'], ['other', 'Other'],
  ] },
  { key: 'kind', q: 'Which describes you best?', options: [
    ['own', 'An MFD, working on my own'], ['big', 'An MFD with a large practice'], ['firm', 'A distribution firm with a team'],
  ] },
  { key: 'size', q: 'How big is your firm?', options: [
    ['1', 'Just me'], ['2-5', '2–5 people'], ['6-20', '6–20 people'], ['20+', 'More than 20'],
  ] },
  { key: 'invoices', q: 'About how many commission invoices do you raise a month?', options: [
    ['<10', 'Under 10'], ['10-50', '10–50'], ['50-200', '50–200'], ['200+', 'More than 200'],
  ] },
];

/* The thank-you after the questions, in one of three kinds, so it reads as if written for them. "Which describes you
   best?" decides; if it's skipped, the firm's size, then the invoices a month; nothing answered is a normal user. */
export type Kind = 'normal' | 'power' | 'firm';
export function kindOf(a: Record<string, string>): Kind {
  if (a.kind === 'firm') return 'firm';
  if (a.kind === 'big') return 'power';
  if (a.kind === 'own') return 'normal';
  if (a.size === '6-20' || a.size === '20+') return 'firm';
  if (a.invoices === '50-200' || a.invoices === '200+') return 'power';
  return 'normal';
}
/* HTML: the firm's line links to Contact */
export const THANKS: Record<Kind, string> = {
  normal: 'Perfect! You’ll love this software.',
  power: 'Perfect. This software is made especially for heavy users, you will love this!',
  firm: 'Great! You’ll love this software. If you need any customised solution for your firm, just <a class="tlink" href="/contact">let us know</a>.',
};

/* An answer's label, for the panel. */
export const answerLabel = (question: string, answer: string) =>
  QUESTIONS.find(q => q.key === question)?.options.find(o => o[0] === answer)?.[1] ?? answer;
