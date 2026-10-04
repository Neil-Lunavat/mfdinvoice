/* ARN-123456, arn 123456 or 123456 → '123456' (or null) */
export function normArn(v: unknown) {
  const m = typeof v === 'string' ? v.trim().toUpperCase().match(/^(?:ARN[-\s]?)?(\d{1,8})$/) : null;
  return m ? m[1] : null;
}
