"""The portal steps, and everything about a month that can change without the app changing.

This package is not part of the installed app. The app fetches the current one from the software's own server, checks
our signature on it, and runs it on this PC (`client.hands.loader`). In a checkout it is run straight from here.

What the app calls, and nothing else:

    run(host, period, registrars)        the month's run
    check(host, period, registrars)      what the registrars have now
    download(host, period, registrars)   the month's invoices onto this PC
    pickup(host, period)                 CAMS's email for a month that went on without it, read in when it comes
    mailbacks(host)                      every CAMS mailback in the mailbox that is this ARN's, read in whoever asked
    cams.arn_of, kfin.arn_of             setup's two verifications
    cams.name_of, kfin.profile_of        the name and GSTIN each registrar shows, for setup
    layout, registrar, sample            the invoice previews in setup and Settings
    books.open, books.keep, books.forget, books.setup_look, books.books_next, books.kept
                                         the person's books, Tally or Zoho Books, on this PC
    tally, zoho                          the two halves of `books`
    page.Refused, page.Changed, kfin.Cancelled

What these steps are given is `host` (`client.hands.host.Host`): the browser's tabs, the person, the files, the
signature and the mailbox. That is the boundary: anything on this side of it reaches every PC within minutes;
anything on the other side needs an update of the app.
"""

from client.automation import books, cams, kfin, page, tally, zoho
from client.automation.flow import check, download, mailbacks, pickup, run
from client.automation.invoices import layout, registrar
from client.automation.invoices.sample import sample

__all__ = ["books", "cams", "check", "download", "kfin", "layout", "mailbacks", "page", "pickup", "registrar", "run", "sample", "tally", "zoho"]
