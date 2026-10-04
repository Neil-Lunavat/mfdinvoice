/* A failure is written to the Worker's log (Cloudflare dashboard → Workers → site → Logs), sorted by what failed.
   Never throws: the caller carries on (or fails) as it would have. */
export type ErrorKind = 'server' | 'signin_email' | 'email' | 'db' | 'r2' | 'order' | 'job';

const text = (e: unknown) => (e instanceof Error ? `${e.name}: ${e.message}` : String(e)).slice(0, 1000);

/* A thrown error, sorted by what failed. */
export function kindOf(e: unknown): ErrorKind {
  const m = text(e);
  if (/D1_|SQLITE|database/i.test(m)) return 'db';
  if (/\bR2\b|bucket/i.test(m)) return 'r2';
  return 'server';
}

export async function record(kind: ErrorKind, place: string, e: unknown) {
  console.error(`[${kind}] ${place}: ${text(e)}`);
}
