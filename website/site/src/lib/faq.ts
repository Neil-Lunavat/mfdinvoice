/* The FAQ: four groups, each question with its answer (HTML allowed). /faq renders it and its FAQPage schema. */
import { PRICE, SALES, TRIAL } from '../consts';
import { word } from './format';

export const FAQ: { id: string; title: string; items: [string, string][] }[] = [
  { id: "before-you-buy", title: "Before you buy", items: [
    ["Do I really never open CAMS or KFintech again?", "For this job, no. Once a month you press Run, check one screen and say yes."],
    ["How is this different from GST invoice software?", "Our software offers end-to-end solutions so that you never have to open portals yourself."],
    ["Is there a free trial?", `Yes, for ${TRIAL.days} days. It starts when you add your ARN in the app.`],
    ["What do I need?", "A Windows 11 PC, your ARN and GSTIN, your CAMS email and your KFintech login. With Gmail, the app picks up CAMS’s invoice mails by itself. With any other mailbox, you add CAMS’s two files each month."],
    ["Does it work on a Mac?", "No. It’s Windows only."],
    ["My staff does this today. Can they use it?", "Yes. The whole monthly job is one button and one confirmation."],
  ] },
  { id: "every-month", title: "Every month", items: [
    ["What if I miss the payout cut-off?", "You can still submit. The payout comes the following month instead. Before the cut-off, it usually arrives by about the 25th."],
    ["What if an invoice is rejected?", "You see the fund house’s own words, and you can send it again. There’s no limit and no penalty for sending again."],
    ["Can I send only part of the month?", "Yes. Untick any fund house at the check, and it stays open for your next run."],
    ["What if CAMS or KFintech change their workflow?", "We adapt fast, so the service keeps working."],
    ["Does it put the invoices in Tally or Zoho Books?", "Tally, yes: the month goes in as sales entries matching exactly what was submitted. Zoho Books is coming."],
    ["Do I still need a CA?", "Yes. This does the invoicing and the upload. Your CA still files your returns, and their job gets easier because your invoices and your books already match."],
  ] },
  { id: "your-data", title: "Your data", items: [
    ["Where does my data live?", "Your passwords, your signature, your mailbox and your invoice files stay on your PC. A record of how each run went reaches us, so we can fix a portal change fast. <a href=\"/security\">See how</a>."],
    ["Can I get a copy of my data?", "Yes. Submit <a href=\"/support?about=data\">this form</a> and we’ll email you everything we hold about you."],
    ["Do you read my email?", "The app opens only the registrar’s invoice mails. It never sends, moves or deletes anything."],
  ] },
  { id: "account-and-billing", title: "Account and billing", items: [
    ["Can one account have more than one ARN?", SALES.moreArns
      ? `Yes, up to ${word(PRICE.maxArns)}. Each ARN runs with its own details, and you switch between them in the app.`
      : "Not yet: one ARN per email for now. More ARNs per email are coming soon."],
    ["Do I get a GST invoice?", SALES.gst
      ? "Yes. Checkout asks for your GSTIN, and the tax invoice is emailed to you. Past invoices are in your <a href=\"/account\">account</a>."
      : "Not yet. For now you get a receipt by email, and it’s in your <a href=\"/account\">account</a>. GST invoices start once our company’s registration is complete."],
    ["What if it isn’t for me?", `Try it free for ${TRIAL.days} days before you pay. Once you’ve paid, there are no refunds: see the <a href="/refunds">refund policy</a>.`],
  ] },
];
