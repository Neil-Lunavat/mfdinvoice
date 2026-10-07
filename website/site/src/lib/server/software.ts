/* What the app sends to the software's own server (server/ at the repo's root): every run's record, and what a
   person sends with Send to support. It is kept there, not in this database; the panel reads it with that server's
   admin key. SOFTWARE_SERVER is its address (wrangler.jsonc vars); SOFTWARE_ADMIN_KEY is a secret
   (bunx wrangler secret put SOFTWARE_ADMIN_KEY: the contents of ~/.mfdinvoice/server-admin.key). */
import { env } from 'cloudflare:workers';

/* run, ended, seconds: sent by the app from 1.0.0 (null before). run is the run's id on the person's PC; a Send to
   support carries the id of the run it attaches. ended: 'well', 'stopped', or the stop's kind. state: '', 'seen' or
   'fixed', set in the panel. */
export type SoftwareReport = { id: number; kind: 'run' | 'ours' | 'problem' | 'idea'; email: string; arn: string; message: string;
  place: string; version: string; steps: string; pc: string; record: number; created_at: string; log?: string;
  run: string | null; ended: string | null; seconds: number | null; state: '' | 'seen' | 'fixed' };

const settings = () => env as unknown as { SOFTWARE_SERVER?: string; SOFTWARE_ADMIN_KEY?: string };
export const softwareReady = () => !!settings().SOFTWARE_SERVER && !!settings().SOFTWARE_ADMIN_KEY;

/* One call to the software's server. null: it gave no answer, or not the one asked for. */
async function ask(path: string, init: RequestInit = {}): Promise<Response | null> {
  const s = settings();
  if (!s.SOFTWARE_SERVER || !s.SOFTWARE_ADMIN_KEY) return null;
  try {
    const r = await fetch(`${s.SOFTWARE_SERVER.replace(/\/$/, '')}${path}`,
      { ...init, headers: { 'x-admin-key': s.SOFTWARE_ADMIN_KEY, 'user-agent': 'site', ...(init.body ? { 'content-type': 'application/json' } : {}) } });
    return r.ok ? r : null;
  } catch { return null; }
}

/* The latest, newest first; `kind` and `email` narrow it. null: the software's server could not be read. */
export async function softwareReports(kind = '', limit = 200, email = '', before = 0): Promise<SoftwareReport[] | null> {
  const q = new URLSearchParams({ limit: String(limit), ...(kind ? { kind } : {}), ...(email ? { email } : {}), ...(before ? { before: String(before) } : {}) });
  const r = await ask(`/admin/reports?${q}`);
  return r ? (await r.json<{ reports: SoftwareReport[] }>()).reports : null;
}

/* Every report kept, counted on the software's server (its /admin/stats): runs per day by result, what waits on
   someone, why runs stopped, ours grouped by their words, and each email's runs and version. null: no answer
   (or a server not yet deployed with /admin/stats). */
export type Result = 'well' | 'theirs' | 'ours' | 'none';
export type SoftwareStats = {
  today: string; keep_days: number;
  days: { day: string; result: Result; n: number }[];
  open: { kind: string; n: number }[];
  stops: { ended: string; n: number }[];
  ours: { message: string; place: string; n: number; latest: number; open: number }[];
  people: { email: string; runs: number; last: string | null; kind: string | null; ended: string | null; version: string }[];
};
export async function softwareStats(): Promise<SoftwareStats | null> {
  const r = await ask('/admin/stats');
  return r ? r.json<SoftwareStats>().catch(() => null) : null;
}

/* One, with its log lines, the names of the files in its record, and the same run's other reports (the run's own,
   and what a person sent about it). */
export async function softwareReport(id: number) {
  const [one, files] = await Promise.all([ask(`/admin/reports/${id}`), ask(`/admin/reports/${id}/files`)]);
  if (!one) return null;
  const got = await one.json<{ report: SoftwareReport; same?: SoftwareReport[] }>();
  return { report: got.report, same: got.same ?? [],
    files: files ? (await files.json<{ files: { name: string; size: number }[] }>()).files : [] };
}

/* Seen or fixed, for whoever fixes things ('' clears it). */
export const setSoftwareState = async (id: number, state: string) =>
  !!(await ask(`/admin/reports/${id}/state`, { method: 'POST', body: JSON.stringify({ state }) }));

/* One file of a record (a picture, the log, a saved page as text), or the whole record as its zip. */
export const softwareFile = (id: number, name: string) => ask(`/admin/reports/${id}/file?name=${encodeURIComponent(name)}`);
export const softwareRecord = (id: number) => ask(`/admin/reports/${id}/record`);
