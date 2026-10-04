/* GET ?id=12              → { ok, report, files } · one thing the app sent, with its log and its record's file names
   GET ?id=12&file=<name> → that file of its record (a picture, the log, a saved page as plain text)
   GET ?id=12&zip=1       → the whole record, as the zip it was sent as
   All read from the software's own server (lib/server/software.ts). */
import { json, fail } from '../../../lib/server/http';
import { gated } from '../../../lib/server/admin';
import { softwareReport, softwareFile, softwareRecord } from '../../../lib/server/software';
export const prerender = false;

export const GET = gated('control', async (_req, url) => {
  const id = Number(url.searchParams.get('id'));
  if (!Number.isInteger(id) || id < 1) return fail(400, 'bad_id');
  const name = url.searchParams.get('file');
  if (name || url.searchParams.get('zip')) {
    const r = name ? await softwareFile(id, name) : await softwareRecord(id);
    if (!r) return fail(404, 'not_found');
    return new Response(r.body, { headers: {
      'content-type': r.headers.get('content-type') || 'application/octet-stream', 'cache-control': 'private, no-store',
      'x-content-type-options': 'nosniff',
      ...(name ? {} : { 'content-disposition': `attachment; filename="run-${id}.zip"` }) } });
  }
  const got = await softwareReport(id);
  return got ? json({ ok: true, ...got }) : fail(404, 'not_found');
});
