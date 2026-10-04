/* The run's steps, as the window draws them. Their names, their lines and their results are the app's: the window
   never works out progress on its own, and draws exactly the rows it was last sent. */

import type { StepView } from '../bridge/types';

export type Bar = 'waiting' | 'running' | 'need' | 'done' | 'bad';

export interface StepsView {
  bars: Bar[];
  line: string;                                 // what the running step is doing now
  meta: string;                                 // "Get · step 2 of 7" · "Stopped at Get" · "Done"
  current: string;                              // the running (or stopped) step's name, '' when none
  done: { name: string; result: string }[];     // finished steps, in order
  finished: boolean;                            // every step done
  stopped: boolean;
}

/** `needsYou`: a question is on screen (a captcha, the files, Your check), so the running step's bar pulses. */
export function stepsView(steps: StepView[], needsYou = false): StepsView {
  const rows = [...steps].sort((a, b) => a.index - b.index);
  const bad = rows.find(s => s.state === 'bad');
  const live = rows.find(s => s.state === 'running');
  const finished = rows.length > 0 && rows.every(s => s.state === 'done');
  const at = bad ?? live;
  return {
    bars: rows.map(s => (s.state === 'running' && needsYou ? 'need' : s.state)),
    line: live?.line || (rows.length ? '' : 'Starting'),
    meta: bad ? `Stopped at ${bad.name}` : finished ? 'Done' : live ? `${live.name} · step ${live.index + 1} of ${rows.length}` : 'Starting',
    current: at?.name ?? '',
    done: rows.filter(s => s.state === 'done').map(s => ({ name: s.name, result: s.result })),
    finished, stopped: !!bad
  };
}
