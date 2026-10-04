# MFDInvoice

A Windows app that does a mutual fund distributor's monthly GST commission invoices on **CAMS** and **KFintech**: gets
the invoices, signs them, uploads them, submits them, and tracks approval. Set up once, then one button a month.

Everything runs on the person's PC: the window, a hidden browser the app owns, the files, the mailbox and the
passwords. Two servers, kept apart: the website (accounts, plans, the free trial, which ARNs an account has) and the
software's own server (the current portal steps, signed, and what the app sends to support).

## Where the code is

| | |
|---|---|
| `client/src/client/hands/` | the app: its launcher (`shell.py`), the window's Python side (`window.py`), the website's API (`site.py`), the browser, files, mailbox and signing |
| `client/src/client/automation/` | the portal steps and the month's run. Not part of the installed app: fetched from the software's server, checked against our signature, and run on the PC |
| `client/window/` | the window (Svelte) |
| `client/packaging/` | the installer |
| `website/` | the website: pages, payments, accounts, the admin panel, and the app's API (`website/site/API.md`) |
| `server/` | the software's own server (a Cloudflare Worker): the signed steps, and what is sent to support |
| `ops/` | signing and publishing the steps (`automation.py`), reading what was sent to support (`reports.py`), switching the old cloud server off and on (`stop-cloud.sh`) |
| `labs/` | experiments. **Not in git** |

## Running things

```
cd client/window && bun install && bun run build    # the window, into client/window/dist/
cd client        && uv run app                       # the app, on the website in client/src/client/brand.json
cd client/window && bun run dev                      # the window alone in a browser, on made-up data
cd client/window && bun run check                    # the window's types
cd website/site  && bun run deploy                   # the website
cd server        && bun run first                    # the software's server, the first time (database, bucket, key, deploy)
uv run --project client python ops/automation.py publish && cd server && bun run deploy    # new portal steps, live
```

In a checkout a run does everything and stops just before pressing Submit. To let it press: `[dev]` `submit = true` in
`client/config.toml`.
