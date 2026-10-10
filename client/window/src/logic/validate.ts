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

/** GST state codes (the first two characters of a GSTIN), with the state's name. */
export const STATES: Record<string, string> = {
  '01': 'Jammu and Kashmir', '02': 'Himachal Pradesh', '03': 'Punjab', '04': 'Chandigarh', '05': 'Uttarakhand',
  '06': 'Haryana', '07': 'Delhi', '08': 'Rajasthan', '09': 'Uttar Pradesh', '10': 'Bihar', '11': 'Sikkim',
  '12': 'Arunachal Pradesh', '13': 'Nagaland', '14': 'Manipur', '15': 'Mizoram', '16': 'Tripura', '17': 'Meghalaya',
  '18': 'Assam', '19': 'West Bengal', '20': 'Jharkhand', '21': 'Odisha', '22': 'Chhattisgarh', '23': 'Madhya Pradesh',
  '24': 'Gujarat', '26': 'Dadra and Nagar Haveli and Daman and Diu', '27': 'Maharashtra', '29': 'Karnataka',
  '30': 'Goa', '31': 'Lakshadweep', '32': 'Kerala', '33': 'Tamil Nadu', '34': 'Puducherry',
  '35': 'Andaman and Nicobar Islands', '36': 'Telangana', '37': 'Andhra Pradesh', '38': 'Ladakh'
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
