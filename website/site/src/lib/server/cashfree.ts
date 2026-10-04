/* Cashfree Payment Gateway: create an order, confirm it was paid, check a webhook's signature.
   Keys come only from Worker secrets (.dev.vars locally). CASHFREE_MODE: 'sandbox' (test) or 'production'. */
import { env } from 'cloudflare:workers';
import { same } from './util';

const VERSION = '2025-01-01';
const base = () => ((env.CASHFREE_MODE as string) === 'production' ? 'https://api.cashfree.com/pg' : 'https://sandbox.cashfree.com/pg');
const headers = () => ({
  'x-client-id': env.CASHFREE_APP_ID, 'x-client-secret': env.CASHFREE_SECRET_KEY, 'x-api-version': VERSION,
  'content-type': 'application/json', accept: 'application/json',
});

/* amount in paise; Cashfree takes rupees with two decimals. Returns the session the browser checkout opens with. */
export async function createOrder(o: { id: string; amount: number; account: number; email: string; phone: string; origin: string }) {
  const https = o.origin.startsWith('https://');
  const res = await fetch(base() + '/orders', {
    method: 'POST', headers: headers(),
    body: JSON.stringify({
      order_id: o.id, order_amount: o.amount / 100, order_currency: 'INR',
      customer_details: { customer_id: `acct_${o.account}`, customer_email: o.email, customer_phone: o.phone },
      order_meta: {
        return_url: `${o.origin}/api/cashfree/return?order_id={order_id}`,
        /* Cashfree only calls https addresses, so not under wrangler dev */
        ...(https ? { notify_url: `${o.origin}/api/cashfree/webhook` } : {}),
      },
    }),
  });
  const data = await res.json<any>().catch(() => ({}));
  if (!res.ok || !data.payment_session_id) {
    console.error('cashfree order failed', res.status, JSON.stringify(data));
    return null;
  }
  return { sessionId: data.payment_session_id as string };
}

/* Asks Cashfree whether the order is paid, for the amount we set. Returns the payment id, or null. */
export async function paidPayment(orderId: string, amount: number): Promise<string | null> {
  const o = await fetch(`${base()}/orders/${encodeURIComponent(orderId)}`, { headers: headers() }).then(r => r.json<any>()).catch(() => null);
  if (!o || o.order_status !== 'PAID' || Math.round(Number(o.order_amount) * 100) !== amount) return null;
  const pays = await fetch(`${base()}/orders/${encodeURIComponent(orderId)}/payments`, { headers: headers() }).then(r => r.json<any>()).catch(() => null);
  const ok = Array.isArray(pays) ? pays.find((p: any) => p.payment_status === 'SUCCESS') : null;
  return ok ? String(ok.cf_payment_id) : null;
}

/* Webhook: base64(HMAC-SHA256(timestamp + raw body)) with the secret key, in x-webhook-signature. */
export async function webhookSignatureOk(raw: string, timestamp: string, signature: string) {
  if (!env.CASHFREE_SECRET_KEY || !timestamp || !signature) return false;
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(env.CASHFREE_SECRET_KEY), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const mac = new Uint8Array(await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(timestamp + raw)));
  return same(btoa(String.fromCharCode(...mac)), signature);
}

export const mode = () => ((env.CASHFREE_MODE as string) === 'production' ? 'production' : 'sandbox');
