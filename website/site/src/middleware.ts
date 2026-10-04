/* A page that throws (a server-rendered page, not an API route: those catch their own) is recorded as an error. */
import { defineMiddleware } from 'astro:middleware';
import { record, kindOf } from './lib/server/errors';

export const onRequest = defineMiddleware(async (ctx, next) => {
  if (ctx.isPrerendered) return next();
  try {
    return await next();
  } catch (e) {
    await record(kindOf(e), `${ctx.request.method} ${ctx.url.pathname}`, e);
    throw e;
  }
});
