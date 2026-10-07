/* Surveys made in the panel and answered in the software (migrations/0013_surveys.sql). Shared by the panel's pages
   and the server: what a survey is, and the checks on what is saved. No question is required: a person answers what
   they like, and an empty answer is left out. */

export type QType = 'one' | 'many' | 'text';
export type SQuestion = { key: string; q: string; type: QType; options: string[]; other: boolean };
export type SAnswer = { picked: string[]; text: string };
export type Survey = { id: number; title: string; questions: SQuestion[]; state: 'draft' | 'live' | 'closed';
  created_at: string; created_by: string; live_at: string | null; closed_at: string | null };

export const TYPES: Record<QType, string> = { one: 'One choice', many: 'Several choices', text: 'Short answer' };
export const LIMITS = { title: 120, questions: 20, q: 300, options: 12, option: 120, text: 1000 };

const s = (v: unknown, max: number) => (typeof v === 'string' ? v.trim().slice(0, max) : '');

/* A survey's questions as the panel posted them, cleaned; or the reason they can't be saved. */
export function cleanQuestions(raw: unknown): SQuestion[] | string {
  if (!Array.isArray(raw) || !raw.length) return 'no_questions';
  if (raw.length > LIMITS.questions) return 'too_many_questions';
  const out: SQuestion[] = [];
  for (const [i, x] of raw.entries()) {
    const type: QType = ['one', 'many', 'text'].includes(x?.type) ? x.type : 'one';
    const q = s(x?.q, LIMITS.q);
    if (!q) return 'empty_question';
    const options = type === 'text' ? [] : [...new Set((Array.isArray(x?.options) ? x.options : []).map((o: unknown) => s(o, LIMITS.option)).filter(Boolean))].slice(0, LIMITS.options) as string[];
    if (type !== 'text' && options.length < 2) return 'few_options';
    out.push({ key: `q${i + 1}`, q, type, options, other: type !== 'text' && !!x?.other });
  }
  return out;
}

/* A person's answers, kept only where they fit the questions: picks among the options (one at most for 'one'), the
   typed text for a short answer or for "Other". */
export function cleanReply(qs: SQuestion[], raw: unknown): Record<string, SAnswer> {
  const got = (raw && typeof raw === 'object' ? raw : {}) as Record<string, any>;
  const out: Record<string, SAnswer> = {};
  for (const q of qs) {
    const a = got[q.key];
    if (!a || typeof a !== 'object') continue;
    let picked = (Array.isArray(a.picked) ? a.picked : []).filter((p: unknown) => typeof p === 'string' && q.options.includes(p));
    if (q.type === 'one') picked = picked.slice(0, 1);
    const text = q.type === 'text' || q.other ? s(a.text, LIMITS.text) : '';
    if (picked.length || text) out[q.key] = { picked, text };
  }
  return out;
}
