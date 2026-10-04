/* What the app opens to: the first one that is true shows.

     1 Update required   a full screen; nothing else is usable
     2 Our service down  a banner, Run off; history and files still open
     3 Offline           a banner, Run off
     4 Signed out        Sign in
     5 No ARN set up     Setup
     7 Plan ended, or no plan   the plain plan screen, or Activate free trial (logic/plan.ts), in Overview's place
     8 Normal            Overview

   2 and 3 are banners over whatever screen 4, 5 or 8 picks, because "everything on the PC still opens" (§12).
   7 sits where Overview does, with the sidebar around it, for the same reason: the months and files stay open.
   6 (new computer) is a launch screen, not built yet; the snapshot has no field for it. */

import type { Condition } from '../bridge/types';

export type Screen = 'update' | 'signin' | 'setup' | 'overview';
export type Banner = 'down' | 'offline' | null;

export interface Opening {
  screen: Screen;
  banner: Banner;
  runOff: boolean;
}

export interface OpeningFacts {
  updateRequired: boolean;
  condition: Condition;
  signedIn: boolean;
  hasArn: boolean;
}

export function opening(f: OpeningFacts): Opening {
  const banner: Banner = f.condition === 'down' ? 'down' : f.condition === 'offline' ? 'offline' : null;
  if (f.updateRequired) return { screen: 'update', banner: null, runOff: true };
  const screen: Screen = !f.signedIn ? 'signin' : !f.hasArn ? 'setup' : 'overview';
  return { screen, banner, runOff: banner !== null };
}
