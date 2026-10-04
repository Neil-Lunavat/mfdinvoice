/* What the app sends to the software's own server (server/ at the repo's root): every run's record, and what a
   person sends with Send to support. It is kept there, not in this database; the panel reads it with that server's
   admin key. SOFTWARE_SERVER is its address (wrangler.jsonc vars); SOFTWARE_ADMIN_KEY is a secret
   (bunx wrangler secret put SOFTWARE_ADMIN_KEY: the contents of ~/.mfdinvoice/server-admin.key). */
import { env } from 'cloudflare:workers';

export type SoftwareReport = { id: number; kind: 'run' | 'ours' | 'problem' | 'idea'; email: string; arn: string; message: string;
  place: string; version: string; steps: string; pc: string; record: number; created_at: string; log?: string };

const settings = () => env as unknown as { SOFTWARE_SERVER?: string; SOFTWARE_ADMIN_KEY?: string };
export const softwareReady = () => !!settings().SOFTWARE_SERVER && !!settings().SOFTWARE_ADMIN_KEY;

/* One call to the software's server. null: it gave no answer, or not the one asked for. */
async function ask(path: string): Promise<Response | null> {
  const s = settings();
  if (!s.SOFTWARE_SERVER || !s.SOFTWARE_ADMIN_KEY) return null;
  try {
    const r = await fetch(`${s.SOFTWARE_SERVER.replace(/\/$/, '')}${path}`, { headers: { 'x-admin-key': s.SOFTWARE_ADMIN_KEY, 'user-agent': 'site' } });
    return r.ok ? r : null;
  } catch { return null; }
}

/* The latest, newest first; `kind` narrows it. null: the software's server could not be read. */
export async function softwareReports(kind = '', limit = 200): Promise<SoftwareReport[] | null> {
  const r = await ask(`/admin/reports?limit=${limit}${kind ? `&kind=${encodeURIComponent(kind)}` : ''}`);
  return r ? (await r.json<{ reports: SoftwareReport[] }>()).reports : null;
}

/* One, with its log lines and the names of the files in its record. */
export async function softwareReport(id: number) {
  const [one, files] = await Promise.all([ask(`/admin/reports/${id}`), ask(`/admin/reports/${id}/files`)]);
  if (!one) return null;
  return { report: (await one.json<{ report: SoftwareReport }>()).report,
    files: files ? (await files.json<{ files: { name: string; size: number }[] }>()).files : [] };
}

/* One file of a record (a picture, the log, a saved page as text), or the whole record as its zip. */
export const softwareFile = (id: number, name: string) => ask(`/admin/reports/${id}/file?name=${encodeURIComponent(name)}`);
export const softwareRecord = (id: number) => ask(`/admin/reports/${id}/record`);
