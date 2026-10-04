# The site's API (for the app and the app's server)

Base URL: the site (`https://site.develop-tbc.workers.dev` today, `https://mfdinvoice.co.in` later).
Every body is JSON (`content-type: application/json`), and so is every response. An error is always
`{ "error": "<code>", ...details }` with a 4xx or 5xx status; the codes below are the ones to handle.
Send a `User-Agent` that names the caller (for example `MFDApp/1.0`). Cloudflare refuses Python's bare `urllib`
default (`403`, "error code: 1010", not JSON); `requests`, `httpx` and `aiohttp` are fine as they are.
Any caller may get `429 too_many_requests` (too many requests from one IP), `415 json_only`, `400 bad_json` or `500 server_error`.

## For the app

Sign-in is the same as the website's: an email gets a 6-digit code, and the right code signs in. An email we
haven't seen creates the account. The app gets a token instead of a cookie. A token lasts a year from its last use.
Send it as `Authorization: Bearer <token>`. Don't send an `Origin` header (if one is sent, it must be the site's).

### `POST /api/app/code`
`{ "email": "a@b.com" }` → `200 { "ok": true }`. The code goes to that email. It lasts 10 minutes.
- `400 bad_email`
- `404 no_account`: no account has this email. The app never makes one: the person signs up on the website
- `429 wait` `{ wait: <seconds> }`: a code was sent under 45 s ago (it's still good; count down `wait`, then allow a resend)
- `429 locked` `{ wait }`: the last code took three wrong tries; a new one can be sent when `wait` runs out
- `429 too_many_codes`: 5 codes in the last hour for this email
- `502 send_failed`: the email couldn't be sent; try again

### `POST /api/app/verify`
`{ "email": "a@b.com", "code": "123456", "version": "1.0.0", "device": "DESKTOP-4K2P" }` → `200 { "token": "<43 chars>", "email": "a@b.com" }`.
Keep the token; it is shown once. `version` (the app's) and `device` (the PC's name) are optional; they show in the
account's activity in the admin panel.
- `400 bad_email`, `400 bad_code` (not six digits)
- `400 wrong` `{ tries_left: 1|2 }`
- `400 locked`: three wrong tries; send a new code (after `wait`, see above)
- `400 expired`: no live code for this email (expired, used, or replaced by a newer one); send a new code
- `409 pending_deletion` `{ delete_after }`: the person asked on the website to delete this account, and it will be
  deleted after `delete_after` (ISO time, about a day after they asked). No token is given. Signing in on the website
  before then lets them keep it; tell them so.

A gift (a free plan given to an email) starts when that email signs in here or on the website; `/api/app/me` then
shows it with `source: "grant"`. The free trial starts when the app binds the account's first ARN
(`/api/app/bind`); it then shows with `source: "trial"`.

### `POST /api/app/signout`
Bearer token, no body needed (send `{}`) → `200 { "ok": true }`. The token stops working. Always 200.

### `GET /api/app/me`
Bearer token →
```json
{ "email": "a@b.com", "active": true, "paid_until": "2027-09-26", "source": "paid",
  "slots": 2, "arns": [{ "arn": "123456", "holder": "R K Mehta" }],
  "app": { "version": "1.0.0", "sha256": "<the installer's>", "note": "One sentence for the update screen." } }
```
- `active`: the plan runs through `paid_until` (a day in India, inclusive). No plan: `active: false`, `paid_until: null`, `source: null`, `slots: 0`.
- `source`: `"paid"`, `"grant"` (a gift: given without payment) or `"trial"` (the free trial: 15 days, once per account).
  Buying during a trial makes it `"paid"`, and `paid_until` then runs a year from the trial's last day.
- `arn` is the number without "ARN-".
- `app`: the app's current version (`APP` in `src/consts.ts`). It is also the oldest that may run: an app older than
  `app.version` shows only Update now, downloads `/api/download`, and checks the file against `app.sha256`.
- `401 bad_token`: unknown, signed out, expired, the account was deleted, or its deletion is pending (asking to
  delete an account ends every token at once). Sign in again.

### `POST /api/app/bind`
Bearer token, `{ "arn": "ARN-123456", "holder": "R K Mehta" }` (`arn` may be `"ARN-123456"`, `"123456"` or
`"arn 123456"`) → `200 { "ok": true, "arn": "123456", "already": false, "slots": 2, "used": 1 }`.
Binds an ARN to a free slot on the signed-in account. The app calls it when setup finishes, after the person's own
CAMS and KFintech sign-ins have shown that ARN. Binding an ARN the account already has is fine: `already: true`.
**The free trial:** on an account that has never had a plan, this call starts the 15-day free trial with this ARN in
its one slot, and the answer adds `"trial_until": "2026-10-16"` (its last day, in India). The app calls it when the
person presses Activate free trial. Each account gets one trial; a second ARN is bought.
- `409 arn_taken`: another account has this ARN, on a plan that is running. Tell the person to write to support.
  An ARN on an account whose plan has ended is not taken: it moves to the account binding it.
- `409 no_free_slot` `{ slots, used }`: every slot is in use. They can buy more ARNs on the website (Account → Buy more ARNs).
- `403 no_active_plan` `{ paid_until }`: the plan (or the trial) has ended.
- `400 bad_arn`, `400 no_holder`, `401 bad_token`

### `GET /api/download`
Bearer token → the installer (`application/vnd.microsoft.portable-executable`, with
`content-disposition: attachment; filename="MFDInvoice-Setup.exe"` and `content-length`). There's one: each release
replaces it. How the app learns a new one is out is the app's side. The same route the website's Download button
uses; the plan is checked on every request. An account with no plan yet may download (its trial starts in the app).
- `401 bad_token`
- `403 no_active_plan`: the plan (or the trial) has ended
- `503 installer_missing`

## What the website uses (for reference; cookie sessions, same-origin `Origin` required on POSTs)
`POST /api/auth/code`, `POST /api/auth/verify` (`{ email, code, keep }`, sets the cookies; adds `delete_after` and
`delete_on` if the account's deletion is pending), `POST /api/auth/signout`, `GET /api/me`, `POST /api/account/billing`,
`POST /api/account/delete` (schedules the deletion a day ahead), `POST /api/account/keep` (cancels it),
`POST /api/checkout/order`, `POST /api/checkout/proof` (the UPI screenshot, multipart), `POST /api/checkout/verify`
(card gateways), `POST /api/support` (a support request, multipart), `GET /api/download`, `GET /blog/images/<name>`,
`GET /sitemap.xml`, and the providers' own `POST /api/razorpay/webhook`, `POST /api/cashfree/webhook`,
`GET /api/cashfree/return`.

The admin panel (`/api/admin/*`) and the blog editor (`/api/write/*`) exist only on their own hosts, behind
Cloudflare Access; they are not part of this API.

**A plan's `source`** is `paid` for any purchase (UPI today), `grant` for one given without payment, and `trial` for
the free trial.
