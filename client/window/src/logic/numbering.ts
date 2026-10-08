/* The last invoice number, exactly as the person prints it, and the part of it that goes up by 1 (prototype #8).
   No format codes and no financial-year field: the number is fixed text with one counting part, tapped by the person.
   The run keeps the same rules (automation/numbering.py): zero padding is kept (073 -> 074). */

/** GST Rule 46: at most 16 characters, only letters, digits, - and /; and KFintech's own: at least 3. '' when the number may be used (empty is not set
    yet), else the words to refuse it with. The Python side holds the same rule (automation/numbering.py). */
export const RULE_46 = 'GST allows up to 16 characters: letters, digits, - and / only.';
export const KFIN_SHORT = 'KFintech needs at least 3 characters.';
export function rule46(text: string): string {
  const t = text.trim();
  if (!/^[A-Za-z0-9/-]{0,16}$/.test(t)) return RULE_46;
  return t.length > 0 && t.length < 3 ? KFIN_SHORT : '';
}

export interface Part { text: string; digits: boolean; start: number }

/** The number split into runs of digits and everything else, each with where it starts. */
export function parts(text: string): Part[] {
  const out: Part[] = [];
  const re = /\d+|\D+/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) out.push({ text: m[0], digits: /^\d/.test(m[0]), start: m.index });
  return out;
}

/** Which part goes up when the person has not tapped one: the last run of digits that is not half of a year pair like
    26-27 or 2026-27 (pasting 73/26-27 picks 73, not 27). -1 when there are no digits. */
export function defaultCounter(text: string): number {
  const ps = parts(text), runs = ps.filter(p => p.digits);
  const inYearPair = (i: number) => {
    const idx = ps.indexOf(runs[i]);
    return (ps[idx + 1]?.text === '-' && !!ps[idx + 2]?.digits) || (ps[idx - 1]?.text === '-' && !!ps[idx - 2]?.digits);
  };
  for (let i = runs.length - 1; i >= 0; i--) if (!inYearPair(i)) return runs[i].start;
  return runs.length ? runs[runs.length - 1].start : -1;
}

/** The number `by` after this one (before it, when `by` is negative), counting the digits that start at `at`. '' when
    nothing counts there, or it would go below 0. */
export function bump(text: string, at: number, by = 1): string {
  const p = parts(text).find(x => x.digits && x.start === at);
  if (!p || Number(p.text) + by < 0) return '';
  const n = String(Number(p.text) + by).padStart(p.text.length, '0');
  return text.slice(0, p.start) + n + text.slice(p.start + p.text.length);
}

/** The counting part to use: the one tapped if it still exists, else the default. */
export function counterOf(text: string, at: number): number {
  return parts(text).some(p => p.digits && p.start === at) ? at : defaultCounter(text);
}

/** Is `typed` lower than `top`, the highest invoice number used, in the same series (the same text round the counting
    digits that start at `at`)? Another series is never below. */
export function below(typed: string, at: number, top: string): boolean {
  const split = (t: string) => {
    const p = parts(t).find(x => x.digits && x.start === at);
    return p ? { before: t.slice(0, p.start), after: t.slice(p.start + p.text.length), n: Number(p.text) } : null;
  };
  const a = split(typed.trim()), b = split(top.trim());
  return !!a && !!b && a.before === b.before && a.after === b.after && a.n < b.n;
}
