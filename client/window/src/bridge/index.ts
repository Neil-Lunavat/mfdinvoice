/* The one way the window talks to the app. Every screen imports `app` from here and nothing else.

   A build (what the app shows) talks to the real app through pywebview's bridge (`real.ts`). `bun run dev` keeps the
   fake app and its development switches, which never reach a build. Both implement the same `App` interface. */

import type { App } from './types';
import { RealApp } from './real';
import { DevFakeApp } from '../dev/devFake';

export const app: App = import.meta.env.DEV ? new DevFakeApp() : new RealApp();

export type * from './types';
