# Launch day (when you say)

## Move to mfdinvoice.co.in
- [ ] Point the domain at the Worker: in `site/wrangler.jsonc`, add `mfdinvoice.co.in` to `routes` and set `SITE_ORIGIN`
  to `https://mfdinvoice.co.in`. Links in emails follow.
- [ ] The app takes the address from one line: `site` in `client/src/client/brand.json`. Change it, build and release.
- [ ] Check that emails from `no-reply@mfdinvoice.co.in` still land in the inbox, not spam.

## Let Google in
- [ ] Turn search on: `INDEXING = true` in `site/src/consts.ts`. Deploy.
- [ ] Add the site to Google Search Console and submit `https://mfdinvoice.co.in/sitemap.xml`.

## Visitor numbers
- [ ] Turn on Cloudflare Web Analytics for the domain. It's free and needs no cookie banner. Add one line to the Privacy
  page saying so.

## Before going live
- [ ] Your own end-to-end pass: sign up, trial, pay, receipt, support, delete.
- [ ] Clear the test data out of the live database and the file store, like on 1 Oct 2026.
- [ ] Add the writers (and Anand, if he wants the panel) in Cloudflare Access.
