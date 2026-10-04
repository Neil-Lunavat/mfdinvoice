/* GET ?from=YYYY-MM-DD&to=YYYY-MM-DD → a CSV, one row per receipt/invoice issued in those days (India time). */
import { fail } from '../../../lib/server/http';
import { gated, salesCsv } from '../../../lib/server/admin';
export const prerender = false;

const DAY = /^\d{4}-\d{2}-\d{2}$/;
export const GET = gated('control', async (_req, url) => {
  const from = url.searchParams.get('from') || '', to = url.searchParams.get('to') || '';
  if (!DAY.test(from) || !DAY.test(to) || from > to) return fail(400, 'bad_dates');
  return new Response(await salesCsv(from, to), {
    headers: { 'content-type': 'text/csv; charset=utf-8', 'content-disposition': `attachment; filename="sales-${from}-to-${to}.csv"`, 'cache-control': 'no-store' },
  });
});
