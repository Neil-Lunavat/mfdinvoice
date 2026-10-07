/* How the panel shows what the software sent (pages and their scripts share it).

   A report's result, as a colour: green, it ended well; amber, it stopped on the person's side (or they pressed
   Stop); red, ours to fix. A person's own message is amber too, an idea blue. Reports from an app before 1.0.0 carry
   no `ended`, and show by their kind only. The stops that end well are the software's CALM ones
   (client/window/src/logic/stops.ts). */
const WELL = new Set(['well', 'nothing_to_do', 'not_listed']);
export function RESULT(r: { kind: string; ended: string | null }): [string, string] {
  if (r.kind === 'problem') return ['From a person', 'amber'];
  if (r.kind === 'idea') return ['An idea', 'blue'];
  if (r.kind === 'ours' || r.ended === 'ours') return ['Ours to fix', 'red'];
  if (!r.ended) return ['Run', ''];
  if (WELL.has(r.ended)) return ['Ended well', 'green'];
  return ['Their side', 'amber'];
}

/* 2m 05s */
export const took = (s: number | null) =>
  s == null ? '' : s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`;

export const STATE: Record<string, [string, string]> = { seen: ['Seen', 'blue'], fixed: ['Fixed', 'green'] };
