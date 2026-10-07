/* The sample month the pages show: Neil Lunavat's 17 invoices for October 2026 (the same rows as the app's prototype).
   The home page draws three of them and runs its demo on all of them; Security follows the HDFC one. */
import { invNo } from '../consts';

const ROWS: [amc: string, reg: 'CAMS' | 'KFintech', taxable: number, igst?: 1][] = [
  ['Aditya Birla Sun Life', 'CAMS', 21480.35],
  ['Axis', 'KFintech', 16840.0],
  ['Bandhan', 'CAMS', 8264.7],
  ['Bank of India', 'KFintech', 4312.18],
  ['DSP', 'CAMS', 12604.45],
  ['Franklin Templeton', 'CAMS', 10998.62, 1],
  ['HDFC', 'CAMS', 40856.0],
  ['ICICI Prudential', 'CAMS', 33592.27],
  ['Invesco', 'KFintech', 7998.31],
  ['JM Financial', 'KFintech', 5406.9],
  ['Kotak Mahindra', 'CAMS', 14660.44],
  ['Mahindra Manulife', 'CAMS', 6120.08],
  ['Nippon India', 'KFintech', 22440.0],
  ['Quant', 'KFintech', 9118.56],
  ['SBI', 'CAMS', 28915.0],
  ['Tata', 'CAMS', 8400.42],
  ['WhiteOak Capital', 'CAMS', 4104.73],
];

const r2 = (n: number) => Math.round(n * 100) / 100;
export type SampleInvoice = { amc: string; reg: 'CAMS' | 'KFintech'; taxable: number; igst: number; half: number; total: number; no: string };

/* CGST + SGST 9% each, or IGST 18% for the one fund house outside the state */
export const INVOICES: SampleInvoice[] = ROWS.map(([amc, reg, taxable, ig], i) => {
  const half = ig ? 0 : r2(taxable * 0.09), igst = ig ? r2(taxable * 0.18) : 0;
  return { amc, reg, taxable, igst, half, total: r2(taxable + igst + 2 * half), no: invNo(i) };
});
export const sum = (l: SampleInvoice[]) => r2(l.reduce((s, x) => s + x.total, 0));
export const invoice = (amc: string) => INVOICES.find(x => x.amc === amc)!;

/* 40856 → "40,856.00"; rs → "₹40,856.00" */
export const fm = (n: number) => n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const rs = (n: number) => '₹' + fm(n);
