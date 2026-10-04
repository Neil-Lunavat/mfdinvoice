/* The checks setup runs as the person types. Errors show only after a few characters or on leaving the field. */

const GS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';

/** A GSTIN with its real checksum. */
export function gstinOk(g: string): boolean {
  if (!/^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/.test(g)) return false;
  let s = 0;
  for (let i = 0; i < 14; i++) {
    const v = GS.indexOf(g[i]) * (i % 2 ? 2 : 1);
    s += Math.floor(v / 36) + (v % 36);
  }
  return GS[(36 - (s % 36)) % 36] === g[14];
}

export const STATES: Record<string, string> = {
  '27': 'Maharashtra', '24': 'Gujarat', '29': 'Karnataka', '07': 'Delhi', '33': 'Tamil Nadu', '19': 'West Bengal',
  '09': 'Uttar Pradesh', '08': 'Rajasthan', '36': 'Telangana', '32': 'Kerala', '23': 'Madhya Pradesh', '06': 'Haryana',
  '03': 'Punjab', '10': 'Bihar', '21': 'Odisha', '37': 'Andhra Pradesh', '30': 'Goa', '22': 'Chhattisgarh',
  '20': 'Jharkhand', '18': 'Assam', '05': 'Uttarakhand', '02': 'Himachal Pradesh', '01': 'Jammu and Kashmir', '04': 'Chandigarh'
};

export const panOf = (g: string) => g.slice(2, 12);
export const stateOf = (g: string) => `${STATES[g.slice(0, 2)] ?? 'State'} (${g.slice(0, 2)})`;

export const emailOk = (e: string) => /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(e.trim());
export const arnOk = (a: string) => /^ARN-\d{3,7}$/.test(a);

/** "ARN-" is typed for them; digits only after it. */
export function arnInput(raw: string): string {
  const d = raw.replace(/^ARN-?/i, '').replace(/\D/g, '').slice(0, 7);
  return d || /^a/i.test(raw) ? 'ARN-' + d : '';
}

export const gstinInput = (raw: string) => raw.toUpperCase().replace(/[^0-9A-Z]/g, '').slice(0, 15);

export function gstinError(g: string): string {
  return g.length < 15 ? `${15 - g.length} more characters` : "This GSTIN doesn't add up. Check the last character.";
}

/** A Gmail app password: 16 letters, shown in groups of four. */
export const appPasswordLetters = (raw: string) => raw.replace(/[^a-z]/gi, '').slice(0, 16).toLowerCase();
export const appPasswordShown = (raw: string) => appPasswordLetters(raw).replace(/(.{4})(?=.)/g, '$1 ');
