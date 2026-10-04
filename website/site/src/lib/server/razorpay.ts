/* Razorpay (test mode for now): create an order, and check the signatures on a payment and on a webhook.
   Keys come only from Worker secrets (.dev.vars locally). */
import { env } from 'cloudflare:workers';
import { hmac, same } from './util';

export async function createOrder(amount: number, receipt: string, notes: Record<string, string>) {
  const res = await fetch('https://api.razorpay.com/v1/orders', {
    method: 'POST',
    headers: {
      authorization: 'Basic ' + btoa(`${env.RAZORPAY_KEY_ID}:${env.RAZORPAY_KEY_SECRET}`),
      'content-type': 'application/json',
    },
    body: JSON.stringify({ amount, currency: 'INR', receipt, notes, payment_capture: 1 }),
  });
  const data = await res.json<any>().catch(() => ({}));
  if (!res.ok || !data.id) {
    console.error('razorpay order failed', res.status, JSON.stringify(data?.error ?? data));
    return null;
  }
  return data as { id: string; amount: number; currency: string };
}

/* The checkout's success callback: HMAC-SHA256(order_id|payment_id) with the key secret. */
export async function paymentSignatureOk(orderId: string, paymentId: string, signature: string) {
  return same(await hmac(env.RAZORPAY_KEY_SECRET, `${orderId}|${paymentId}`), signature);
}

/* A webhook: HMAC-SHA256 of the raw body with the webhook secret, in X-Razorpay-Signature. */
export async function webhookSignatureOk(raw: string, signature: string) {
  return !!env.RAZORPAY_WEBHOOK_SECRET && same(await hmac(env.RAZORPAY_WEBHOOK_SECRET, raw), signature);
}

export const keyId = () => env.RAZORPAY_KEY_ID;
