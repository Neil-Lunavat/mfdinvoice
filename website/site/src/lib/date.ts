/* Dates as the site shows them. A day is 'YYYY-MM-DD'; a stored time is an ISO string in UTC. */

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

/* '2027-09-24' → '24 September 2027' */
export const longDate = (day: string) => `${+day.slice(8, 10)} ${MONTHS[+day.slice(5, 7) - 1]} ${day.slice(0, 4)}`;
/* '2026-09-24' → '24 Sep 2026' */
export const shortDate = (day: string) => `${+day.slice(8, 10)} ${MONTHS[+day.slice(5, 7) - 1].slice(0, 3)} ${day.slice(0, 4)}`;
/* '2026-10-03…' → 'October 2026' */
export const monthYear = (day: string) => `${MONTHS[+day.slice(5, 7) - 1]} ${day.slice(0, 4)}`;

/* a stored UTC time → its day in India */
export const istDay = (iso: string) => new Date(Date.parse(iso) + 5.5 * 3_600_000).toISOString().slice(0, 10);
