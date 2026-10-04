/* The Stopped screen. A stop ends its run: nothing is retried by itself and nothing is scheduled, so every stop has
   Close, and the person runs again when they choose. What it says (the heading, the portal's own words, one or two
   plain sentences) is the app's. The window adds only what a stop lets the person do on the spot. */

import type { Stop } from '../bridge/types';

export interface StopScreen {
  kind: string;
  mark: 'bad' | 'stop' | 'ok';      // red !, the square of a stop the person asked for, or a plain tick
  title: string;
  quote: string;                    // the portal's own words, shown in quotes; '' if none
  lines: string[];
  again: boolean;                   // "Run again" is offered beside Close
  fix: ('cams' | 'kf' | 'mb')[];    // what can be changed in place on this screen, before running again
  support: boolean;                 // Send to support is offered
}

const CALM = new Set(['nothing_to_do', 'not_listed']);                 // nothing went wrong
const ASKED = new Set(['ended', 'not_submitting']);                    // the person, or this PC's own setting, stopped it
const AGAIN = new Set(['arn_mismatch', 'mailbox', 'mailback_late', 'wrong_files', 'mismatch', 'portal_validation',
  'session_ended', 'unreachable', 'refused']);

export function stopScreen(stop: Stop): StopScreen {
  const kind = stop.kind;
  return {
    kind,
    mark: CALM.has(kind) ? 'ok' : ASKED.has(kind) ? 'stop' : 'bad',
    title: stop.title || 'This run stopped',
    quote: stop.said.trim(),
    lines: stop.lines.map(l => l.trim()).filter(Boolean),
    again: AGAIN.has(kind),
    // the ARN itself is bound to the plan, so it is the two sign-ins that can be put right here
    fix: kind === 'arn_mismatch' ? ['cams', 'kf'] : kind === 'mailbox' ? ['mb'] : [],
    support: !CALM.has(kind) && !ASKED.has(kind)
  };
}
