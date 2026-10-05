# The website: everything left (5 Oct 2026)

One file for everything the website still needs: what Claude Code does now, what we go back and forth on, and what
waits for launch day, the proprietorship and the private limited. Tick a line when it is done; delete a section when
it is empty. Older lists (`website/todo/`, the website part of `TODO.md`) are folded in here; this file wins.

How we work on it: the cloud session reads `main` and keeps this file; Neil makes the changes with Claude Code on his
PC and looks at them on the local site; then he pushes, and the cloud session reads `main` again.

## What is decided (remember these)

- **Price:** ₹4,000 a year for the first ARN, ₹2,000 a year for each extra ARN, up to 6 ARNs on an account. More than
  six: write to us (Contact). **Prices are before GST.** No GST is charged until the proprietorship is registered for
  it; the pages say nothing about GST until then.
- **An ARN added partway through the year** ends on the plan's last day and costs ₹2,000 × months left ÷ 12, part
  months counting whole (7 months left: ₹1,167).
- **One free trial per email**, 15 days, on one ARN. Deleting the account and signing up again with the same email
  gives no second trial. The same ARN under different emails is allowed.
- **An ARN is free** when it is on no running plan (trial, gift or paid). A free ARN can be bound by any account; a
  bound one cannot.
- **Business:** Ayen Systems, a sole proprietorship of Neil Lunavat, M-16 Kumar Park, Bibwewadi Kondhwa Road, Pune
  411037, Maharashtra. Courts: Pune. Grievance officer: Neil Lunavat, support@mfdinvoice.co.in, +91 75179 11229.
  GSTIN and SAC: after the proprietorship's GST registration.
- **No lawyer's facts sheet.** Neil has someone in touch for the legal pages.
- **Windows 11 only** in every claim. The exclamation mark on the home page stays.
- **Move to mfdinvoice.co.in** after all the polishing, as the last step before launch.
- **Analytics:** Cloudflare Web Analytics, no cookies.

---

## Part 1. Tasks for Claude Code (decided; do them as written)

After each task: `bun run check` in `website/site` (all must pass), then look at the pages on the local site.
Clean stale words in comments of any file touched.

### 1. Business details and the legal pages
- [ ] `BUSINESS` in `src/consts.ts`: `address` = "M-16 Kumar Park, Bibwewadi Kondhwa Road, Pune 411037", `courts` =
      "Pune", `grievanceOfficer` = "Neil Lunavat". On the Privacy page the grievance line then reads: name,
      support@mfdinvoice.co.in, +91 75179 11229, once (today the email would appear twice).
- [ ] `TERMS_VERSION` = the day of the change.
- [ ] Remove "A draft, until our lawyer has reviewed it." (`src/components/Legal.astro`) and its style.
- [ ] One trial per email, in the same words everywhere: Terms ("The free trial"), Refunds ("Try it first" says
      "Every ARN gets a free trial": wrong), FAQ ("Is there a free trial?").
- [ ] Terms, "Plans and payment" and "Your ARN": a plan covers one or more ARNs (up to six) for a year; an ARN added
      later ends on the same day and costs its share of the year. Today it says "A plan covers one ARN" and "the ARN
      you add".
- [ ] Privacy, "What reaches us from the app": the app sends the PC's name, its Windows version, its memory (GB) and
      its free disk space, not only the name and Windows version (`client/src/client/hands/window.py`, the `pc` line
      in `_report`). Say all four. Security's "What we keep" gets the same.
- [ ] Privacy: the run record is kept 90 days. The deleting is not built yet (it is on the software's server, Part 6).
      The words stay; the delete must exist before launch.

### 2. Fonts from our own site
- [ ] Geist (300–700) and Geist Mono (400, 500) as `.woff2` files in `public/fonts/`, with `@font-face`; `Fonts.astro`
      points at them (both the public layout and the panel's use it).
- [ ] The Content-Security-Policy in both `src/lib/server/headers.ts` and `public/_headers` drops
      `fonts.googleapis.com` and `fonts.gstatic.com`. The two lists stay identical.
- [ ] Privacy, "Who else handles it": remove the Google Fonts line.
- [ ] Check: the browser's Network tab shows no request to Google on any page.

### 3. Price ₹2,000 for each extra ARN
- [ ] `PRICE.extra = 2000` in `src/consts.ts`; fix the comments that say ₹500 there and in `src/lib/price.ts`.
- [ ] `scripts/check.ts` line ~745, "part-year price": 7 months is now ₹1,167 per ARN, ₹3,501 for 3 (it says ₹292 and
      ₹876 and will fail). Look for any other amount in the checks built on ₹500.
- [ ] Look at: Pricing (stepper, "₹2,000 a year for each ARN you add"), Checkout (new plan with 2+ ARNs, and Buy more
      ARNs mid-year), a receipt.

### 4. Sign-in and Try for Free
- [ ] The code step does not submit by itself at six digits (typed or pasted). The person presses Continue (Enter
      works too). The app's sign-in is the model: `client/window/src/screens/SignIn.svelte`.
- [ ] After Continue, no "You're signed in · Continue" card: go straight to where they were going, and show a toast
      "Signed in successfully" on that page, only when no other toast is shown (account deleted, gift expired). The
      toast must survive the page change (a flag in sessionStorage, read on load). Keep the gift's card (it has its
      own message) and the "set to be deleted · Keep it?" step.
- [ ] Try for Free (`src/components/Cta.astro`): signed out → `/signin?next=/downloads`; signed in → `/downloads`.
      It sits on Home (hero and end) and Pricing.
- [ ] Home hero: the secondary "Downloads" button becomes "Demo", which scrolls to the app window (`#how`).
- [ ] After a payment, Continue goes to Downloads only when the account has no ARN yet; otherwise to Account. Both in
      `src/pages/checkout.astro` (`paid`) and `src/pages/api/cashfree/return.ts`.
- [ ] Look for any other button that lands a signed-out person on a page that then says "sign in first", and make it
      go through Sign in with `next`.

### 5. One free trial per email, enforced
- [ ] Before a trial starts (`src/lib/server/trial.ts`, `startTrial`, called from `/api/app/bind`), refuse it if
      `trials` already has a row for this email. The account then needs a plan; the bind answers as for an account
      with no plan.
- [ ] The app must show words for that answer ("This email has had its free trial. Buy a plan on the website.").
      Check what `client/window` shows today for it; if new words are needed, that waits for the next app release.
- [ ] "Had a plan" (the `hp` cookie, `/api/me`, Account's Try for Free / Buy now) also counts a past trial for this
      email, so an account re-made with the same email sees Buy now, not Try for Free.
- [ ] A check in `scripts/check.ts`: delete an account that had a trial, sign up again with the same email, bind an
      ARN: no trial.

### 6. Copy fixes
- [ ] FAQ, "How is this different from GST invoice software?": "It doesn't just make invoices: it gets them from CAMS
      and KFintech, signs them, uploads them and follows them to approval." (`src/lib/faq.ts`)
- [ ] Home demo: "We'll notify you once approved." → "Check now shows you when it's approved." Twice in
      `src/pages/index.astro` (after Submit, after Send again).
- [ ] Pricing: remove "Analytics and insights · Coming soon".
- [ ] Checkout: "three quick questions" → "four quick questions" (`checkout.astro`, `survey()`).

### 7. Downloads and Release notes reset
- [ ] `RELEASES` in `src/consts.ts` keeps one entry: 1.0.3, its date, size and sha256 unchanged, note and change "The
      first release.". Do not change the version or the sha256: installed apps read them to know the current version
      and to check the installer.
- [ ] Look at Downloads and Release notes.

### 8. The home page's app window, redrawn to match the app
Compare with `client/window/src/screens/Overview.svelte` and the real app.
- [ ] The month picker: the month's name as a dropdown, with the arrows either side.
- [ ] Under the heading: "KFintech's trail month: September".
- [ ] The Run button with its menu beside it: Run CAMS only, Run KFintech only, Download invoices.
- [ ] The chips as the app says them: Not submitted, Submitted, Approved, Stopped.
- [ ] Not drawn: the bell, Refresh, the red banners.

### 9. The Security page tells the truth about passwords
The page says the app removes passwords "in every form they could take" and shows three: as typed, inside a web
address (`Mehta%401987`), encoded (base64). The app removes only the first, and only from the logs
(`window.py`, `_never_sent`, `_blank`, `_log_tail`).
- [ ] Change the Security page (and the home page's "checks for any passwords in the data and removes them", and the
      same line in Privacy) to what is true: passwords are blanked out of the run's log and the app's log before they
      are sent; typed text is logged by its length only. Remove the "Inside a web address" and "Encoded" rows, or see
      Part 2, item 6.

### 10. Favicon and link-preview image (in the cloud session, after 1–9)
- [ ] Favicon (and the Apple touch icon) from the blue tick.
- [ ] The link-preview image WhatsApp and LinkedIn show (`og:image`, 1200 × 630), from the wordmark and a line.

---

## Part 2. Back and forth (needs Neil; the lean is the cloud session's)

1. **Checkout.** Neil goes through it in Claude Code. Notes: the price lines with ₹2,000; nothing says why there is no
   GST (Lean: say nothing, as decided); the UPI pays Neil's own ID (Lean: keep until the proprietorship's bank
   account exists); the details for the receipt are asked before the QR.
2. **Security page.** Neil goes through it in Claude Code, after Part 1 task 9.
3. **Setup page.** Neil rebuilds it: one picture per step (9), from the app on its made-up backend (`bun run dev` in
   `client/window`, so no real data), then his videos. The app's "How to · 1 min" buttons open `/setup`.
4. **The app's "Sign up" link** opens `/signin`, and after the code the person lands on the home page. They already
   have the app. Lean: the app opens `/signin?from=app`, and after the code the website says "You're set. Go back to
   MFDInvoice and sign in with <email>." The website part can be built now; the app's part is one line
   (`client/src/client/hands/window.py`, `LINKS["signup"]`) in the next app release.
5. **When an ARN is taken over** (its plan ended, another account binds it): today the ARN moves, the old account's
   activity records it, and **no email** goes to the old account. The old PC keeps every file it had (the website and
   the servers hold no invoices; the run records go after 90 days); the app there has no plan, so it does nothing.
   If the old owner buys again, their account no longer has that ARN, and it is not theirs while the new owner's plan
   runs. Lean: (a) email the old account once: "ARN-X has been added by another MFDInvoice account. Your files on your
   PC are untouched." (b) nothing more: it is the rule the Terms already state. (c) Check what the old owner's app
   shows when it runs that ARN after buying again (it should say the ARN is on another account, not crash).
6. **Removing encoded passwords too** (the app, not the website). Lean: in a later app release, also blank the
   URL-encoded and base64 forms, and blank them in the page HTML that goes with an "ours" stop; then the Security
   page can show the three forms again.
7. **Software tab in the admin panel** (`src/pages/control/software.astro`). Lean in brackets:
   1. a run's result as a colour: ended well, stopped on the person's side, ours (yes);
   2. a person's message tied to the run it is about (yes);
   3. Seen / Fixed on "Ours to fix" and "From a person" (yes);
   4. a Reply button: an email from support@ with the run number in the subject (later; the mail app does this);
   5. how long the run took (yes, small);
   6. an account's runs on its own page (later);
   7. the panel's Overview: runs today, "Ours to fix" open (later).
   Also: the table and the View box were changed on 4 Oct without being looked at.
8. **An ARN that comes back under many emails** (allowed). Lean: show "this ARN had N trials before" on the account's
   page in the panel, so it can be seen; nothing blocked.
9. **Every page, read once as a visitor**, desktop and phone: Home, Setup, Security, Pricing, FAQ, Downloads, Release
   notes, Contact, Support, Blog, Terms, Privacy, Refunds, 404, Sign in, Account, Checkout, a receipt.
10. **Every email, read once** (`bun run emails` renders them): the code; payment received; receipt; payment rejected;
    you can pay again; one step away (unfinished payment); trial ending; trial ended; ARN slot free; support received;
    gift given; gift started; account to be deleted; email changed (old and new); your data; and the two that go to
    Neil (payment to check, support request).
11. **The admin panel, page by page:** Overview, Accounts, an account, Payments, Sales (and its CSV), Gifts, Support,
    Survey, Software, a receipt. **The blog editor:** posts, a post, images, preview.
12. **The four checkout questions.** "Which describes you best?" and "How big is your firm?" overlap. Lean: keep all
    four for October; read the answers after.
13. **The blog** stays empty, with the footer link, until the person Neil delegates it to writes. Also wanted: a
    default cover for a post with none.
14. **Logo.** Today the blue tick and the MFD**Invoice** wordmark.
15. **Zoho Books "soon"** is on Home (hero), Pricing and the FAQ. When it ships, or if it slips past launch, change all
    three.
16. **A place for a signed-in person to send an idea.** Neil is thinking about it.
17. **Speed and access**: one Lighthouse pass on a phone for Home, Pricing and Downloads. Lean: after the content is
    final.

---

## Part 3. Before launch, on Neil's PC (or by people)

- [ ] Cloudflare Email Routing: a test mail to support@ and hello@ each arrives in Neil's inbox.
- [ ] Cloudflare Access: add the blog's writers (and Anand, if he wants the panel).
- [ ] The person for the legal pages reads Terms, Privacy and Refunds.
- [ ] How-to videos for `/setup`.
- [ ] The run record's delete after 90 days, built and deployed on the software's server (`server/`): rows and R2
      files. The Privacy page promises it.
- [ ] Clean the live databases (the website's and the software's server's) and the file store; remove Neil's own test
      account and ARN.
- [ ] Relaunch as 1.0.0: `ops/release.py` writes `RELEASES`; empty the old entries first. Version, date, size and
      sha256 all from that release.
- [ ] Neil's own pass on the live site, end to end: sign up, Try for Free, download, trial, pay by UPI, approve in the
      panel, receipt, Buy more ARNs, support request, a copy of my data, delete the account, sign up again with the
      same email (no second trial).

## Part 4. Launch day (the move to mfdinvoice.co.in)

- [ ] `website/site/wrangler.jsonc`: add `mfdinvoice.co.in` to `routes`; `SITE_ORIGIN` = `https://mfdinvoice.co.in`.
      Links in emails follow.
- [ ] **Keep `site.develop-tbc.workers.dev` answering** (`workers_dev: true`) until every installed app has updated:
      the app asks that address whether it must update, so switching it off first strands every installed app.
- [ ] The app: `site` in `client/src/client/brand.json` → `https://mfdinvoice.co.in`; build, release, and the forced
      update moves everyone. Then `workers_dev` can go.
- [ ] Emails from no-reply@mfdinvoice.co.in land in the inbox, not spam (Gmail and one other).
- [ ] `INDEXING = true` in `src/consts.ts`; deploy.
- [ ] Google Search Console: add the site, submit `https://mfdinvoice.co.in/sitemap.xml`.
- [ ] Cloudflare Web Analytics on, and one line in Privacy ("Cloudflare counts visits, without cookies"); move
      `TERMS_VERSION`.

## Part 5. After launch

- [ ] Blog posts (delegated).
- [ ] Read the checkout answers and the analytics after October.
- [ ] The Software tab's later items (Part 2, item 7: 4, 6, 7).
- [ ] App items that touch the website, in the next app release: the Sign up link (Part 2, item 4); the words for
      "this email has had its trial" if new (Part 1, task 5); encoded passwords (Part 2, item 6).

## Part 6. After the sole proprietorship is registered

Until then: UPI to Neil's own ID, checked by hand, a receipt, no GST.

**Card payments (Cashfree; built and parked)**
- [ ] A Cashfree account in the proprietorship's name; its two keys as secrets `CASHFREE_APP_ID`,
      `CASHFREE_SECRET_KEY`.
- [ ] Test with the sandbox keys (`CASHFREE_MODE: "sandbox"`), then `"production"`.
- [ ] `PAYMENTS: "cashfree"` in `wrangler.jsonc`. UPI stops taking new payments and keeps the old ones. Checkout then
      asks for a mobile number (built).
- [ ] Decide: keep the UPI code and the panel's Payments page as a backup, or remove them.
- [ ] Words that say UPI and screenshots today: Privacy ("Payments", "What this website keeps": UTR and screenshot),
      Terms ("Plans and payment": "You pay by UPI and send us the payment's screenshot … usually within a few hours"),
      Refunds ("How to ask": the UTR number). Change them to Cashfree.
- [ ] Until Cashfree: if UPI goes on after registering, `UPI` in `consts.ts` moves to the proprietorship's bank
      account's UPI ID.

**GST (if the proprietorship registers for it)**
- [ ] `SALES.gst = true` in `consts.ts`: 18% on top, Checkout asks for a GSTIN, buyers get tax invoices instead of
      receipts, and the Terms and FAQ lines about "not registered for GST" switch by themselves.
- [ ] `gstin` and `sac` in `BUSINESS` (the CA gives the SAC).
- [ ] Pricing: a "+ 18% GST" line beside the price that shows only when `SALES.gst` is on (today nothing on Pricing
      mentions GST either way). Same check on Checkout's lines and on the receipt.
- [ ] The CA checks the tax invoice's layout (open any receipt in the panel).
- [ ] `TERMS_VERSION` moves.

**Code signing**
- [ ] Ask the certificate sellers whether a proprietorship (or Neil as a person) can get one. If yes: sign the
      installer, and the Setup page's "Windows protected your PC · More info · Run anyway" goes.

## Part 7. After the private limited company is registered

- [ ] `legalName` ("Ayen Systems Private Limited") and `entity` in `BUSINESS`. Every page, the footer and new receipts
      follow; old receipts keep the old name.
- [ ] The company's GSTIN, address and bank in `BUSINESS`; the payment provider's account moves to the company.
- [ ] `TERMS_VERSION` moves; the legal pages are read once more.
- [ ] Code signing, if it could not be done with the proprietorship.
