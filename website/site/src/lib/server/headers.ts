/* Security headers on every response (the static pages too: the Worker runs first for every request, and the same
   list is in public/_headers for anything served straight from the assets).
   The Content-Security-Policy allows what the pages load: our own scripts and styles, Google Fonts, and, on Checkout
   only, Razorpay's and Cashfree's checkout. Loosened site-wide: style-src 'unsafe-inline' (the pages use style
   attributes and Astro inlines small stylesheets); img-src data: (the select arrows are data: SVGs in the CSS). */
const FONTS_CSS = 'https://fonts.googleapis.com', FONTS = 'https://fonts.gstatic.com';
const PAY = {
  script: 'https://checkout.razorpay.com https://sdk.cashfree.com',
  frame: 'https://api.razorpay.com https://checkout.razorpay.com https://sdk.cashfree.com https://*.cashfree.com',
  connect: 'https://api.razorpay.com https://lumberjack.razorpay.com https://*.cashfree.com',
  img: 'https://*.razorpay.com https://*.cashfree.com',
};

export function csp(path: string) {
  const pay = path === '/checkout';
  return [
    "default-src 'self'",
    `script-src 'self'${pay ? ' ' + PAY.script : ''}`,
    `style-src 'self' 'unsafe-inline' ${FONTS_CSS}`,
    `font-src 'self' ${FONTS}`,
    `img-src 'self' data: blob:${pay ? ' ' + PAY.img : ''}`,
    `connect-src 'self'${pay ? ' ' + PAY.connect : ''}`,
    `frame-src ${pay ? PAY.frame : "'none'"}`,
    "frame-ancestors 'none'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join('; ');
}

export const PERMISSIONS = 'accelerometer=(), autoplay=(), camera=(), display-capture=(), geolocation=(), gyroscope=(), hid=(), magnetometer=(), microphone=(), midi=(), serial=(), usb=(), browsing-topics=()';

export function withSecurityHeaders(req: Request, res: Response) {
  const out = new Response(res.body, res);
  const h = out.headers;
  h.set('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
  h.set('X-Content-Type-Options', 'nosniff');
  h.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  h.set('X-Frame-Options', 'DENY');
  h.set('Permissions-Policy', PERMISSIONS);
  h.set('Content-Security-Policy', csp(new URL(req.url).pathname));
  return out;
}
