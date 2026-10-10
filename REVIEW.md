# Review of 10 Oct 2026: what was found, what Neil decided, where it stands

A read-only review of the whole codebase (automation first, website last), then Neil's answers. Numbers are the ones
used in the conversation. Status: **W0/W1** = being done now, **W2** labs, **W3** dev is real, **W4** speed and blind
spots, **parked**, **dropped**, **done**.

## Security
1. `/report` takes anything from anyone (256 KB log into D1, 20 MB zip into R2, 60 an hour per IP); a full D1 would stop forwarding too. → caps, logs into R2. **W1**
2. The website sends a sign-in code to any address: email bombing ruins the domain's reputation. → Turnstile on the web sign-in. **W1**
3. Nothing caps Cloudflare spend. → a billing alert (Neil). **W0**
4. Plan, ARN binding and one PC are checked only in the window; Python starts any run. → the same rule in `start_run`. **W1**
5. The installed exe honours `SITE` / `SERVER` from the environment: a fake website gives free use. → only in a checkout. **W1**
6. The steps are a public download of plain `.py` for anyone. → steps only for a paid account (design piece, Neil decides). **W1 decision**
7. Extracted steps are trusted forever after download. → checked on every load. **W1**
8. Forwarding claim may be taken over by replaying a genuine CAMS mail with a forged envelope sender. → lab L8 on staging. **W2**
9. Pictures of portal pages with every run, kept 90 days. → off at 1.1.x. **parked**
10. The browser is driven through port 9222, open to any program on the PC. → a pipe (lab L6). **W2**
11. Installer and exe unsigned. → in progress (Neil). **parked**
36. A free trial is per email; an ARN can come back under new emails. → allowed on purpose, and counted on the panel (demand, and revenue lost). **W1**
37. `TEST_LOGIN_DOMAIN` / `TEST_LOGIN_CODE` on the live website would give accounts without an inbox. → check, remove from live, keep for staging. **W0**
38. The signing key is a plain file on the PC agents work on, and pulled reports (which anyone can post) are read by agents. → passphrase on the key; reports are untrusted. **W0**

## Bugs
12/39. A USB token on the PIN route can't sign in a run (`Door.unlock` is never called; the run's PIN screen is never opened); the expiry check never runs. → lab L5. **W2**
13. KFintech own-invoice rows matched by taxable + GST only. → lab L9 (Neil checks the grid). **W2**
14. "Network not connected" means both portals unreachable. → goes with 28. **W4**
15. The window is taller than a 1080p screen at 150%. → clamp to the work area + CSS zoom. **W3**
16. `files.py` docstring says the CAMS sheet is never rebuilt; it is. CAMS approved a blank PDF: it checks nothing. → comment fixed with 45. **W1**
40. The signature-photo cleaner loops per speck over the whole image: a noisy photo can hang. → lab L4. **W2**
41. Downloads offers April 2026; CAMS's and KFintech's GST invoices began with May 2026. → start at May. **W1**
53. A CAMS-only ARN (bound by its first run) may never get Run: `runOffOf` calls `planBlocksRun` without the profile, so an unbound `bindOnRun` ARN reads as "unbound". → pass the profile. **W1**

## Shortcuts (A→C)
17. Old-software shims in the steps and window. → deleted (updates are forced). **W1**
18. The vault keeps every secret twice. → per-ARN only; rewrites the vault on people's PCs, so its own test round. **W4**
19. Three loops wait for CAMS's email. → one. **W4**
20. Rule 46 three times. → two: the window's (as typed) and the steps' (the law). **W1**
21. The failing registrar found by searching step text. → tracked. **W1**
22. `browser.py` vs Playwright's own Edge/Chrome. → lab L6. **W2**
23/45. Dead code and stale words. → cleaned. **W1**
42. The window's made-up backend (~1,030 lines). → goes, with 29. **W3**
43. Tally and Zoho each write two ways (Books tab, run). → one `place()`, lab L1/L2. **W2**
44. Five PDF libraries. → `pypdfium2` for text; lab L3. **W2**
50. `publish` packs the working folder. → from git, refuses uncommitted steps, deploys in the same command. **W0**

## Speed and cost
24. Registrars one after the other. → in parallel, CAMS's email asked early; lab L7. **W2**
25/46. Tally re-reads the whole year many times per run (hit Partner's big company on 10 Oct). → once per run, lab L1. **W2**
47. Zoho re-lists the year per invoice placed. → once per run, lab L2. **W2**
26. A new Playwright per run. → one for the software's life. **W4**
27. The window's state rebuilt from every month's file on every change. **W4**
28. A connection to CAMS every 10 s. **W4**
29. Window changes need a rebuild. → Vite live reload against the real Python. **W3**
48. The token's certificate chain read for every invoice. → once per run. **W4**
49. Plan check every 5 min (~8,600 requests a month per PC). → on window focus + every 30 min. **W4**

## Dev and prod
30. Dev claims Gmail forwarding on the real server. → Neil uses the Gmail app password in dev. **done (decided)**
31. Staging copies of both servers; `devsite.py` goes. **W3**

## Blind spots
32. Antivirus, office proxies, laptop sleep (stay awake during a run), wrong clock (the website's `Date` header), Workspace IMAP off. **W4**
33. PC fingerprint and ISP on `/api/app/me`, setup funnel, crash report before the window opens, chaos checklist. **W4**
51. Broken runs found only by asking. → the software's server emails neillunavat3192@gmail.com when a run breaks. **W1**
52. Odd Tally names (line breaks, `&`, Hindi) → into lab L1. **W2**

## Decided, not changing
34. Check now replays its lines for a reading under 10 minutes old (Neil's UX decision). **dropped**
35. No offline grace period: Run is off without the website. **dropped**
The crack-release idea. **dropped**

## Labs (Wave 2): each finds what the real thing does, then its fix
L1 Tally (43, 46, 52) · L2 Zoho (43, 47) · L3 PDF text (44) · L4 signature photos (40) · L5 DSC token (12, 39) ·
L6 browser launch (10, 22) · L7 registrars in parallel (24) · L8 forwarding takeover, on staging (8) · L9 KFintech grid (13)
