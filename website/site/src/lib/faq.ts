/* The FAQ: four groups, each question with its answer (HTML allowed). /faq renders it and its FAQPage schema. */
import { NAME, PRICE, SALES, TRIAL } from "../consts";
import { word } from "./format";

export const FAQ: { id: string; title: string; items: [string, string][] }[] = [
    {
        id: "before-you-buy",
        title: "Before you buy",
        items: [
            [
                "Do I really never open CAMS or KFintech again?",
                "For this job, you really don't. Once a month you press Run, check one screen and say yes.",
            ],
            [
                "How is this different from GST invoice software?",
                "It doesn’t just make invoices: it gets them from CAMS and KFintech, signs them, uploads them and follows them to approval.",
            ],
            [
                "Is there a free trial?",
                `Yes: ${TRIAL.days} days, once per email, on one ARN. It starts when you add your ARN in the software.`,
            ],
            [
                "What do I need?",
                "A Windows 11 PC, your ARN and GSTIN, your CAMS email and your KFintech login. With Gmail, the software picks up CAMS’s invoice mails by itself. With any other mailbox, you add CAMS’s two files each month.",
            ],
            ["Does it work on a Mac?", "No. It’s Windows only."],
            [
                "My staff does this today. Will they be able to use it?",
                "Yes. You follow an effortless onboarding process and once the software is setup, the whole monthly job is one button and one confirmation.",
            ],
            [
                "Does it run fully automatically?",
                "Yes, except for one step: before anything is uploaded, you check one screen with every fund house and the total, and say yes. Nothing is submitted without it.",
            ],
            [
                "Is the CAPTCHA automated too?",
                "No. KFintech asks for it to know a person is signing in, so you type it. The software keeps you signed in while it’s open, so you’ll see it rarely: on the first run after opening it, or after it’s been left alone for 20 minutes.",
            ],
            [
                "Are you part of CAMS or KFintech?",
                `No. CAMS and KFintech are not part of ${NAME}, and we have no arrangement with either.`,
            ],
        ],
    },
    {
        id: "every-month",
        title: "Every month",
        items: [
            [
                "What if I miss the payout cut-off?",
                "You can still submit. The payout comes the following month instead. Before the cut-off, it usually arrives by about the 25th.",
            ],
            [
                "What if an invoice is rejected?",
                "You see the fund house’s own words, and you can send it again. There’s no limit and no penalty for sending again.",
            ],
            [
                "Can I send only part of the month?",
                "Yes. Untick any fund house at the check, and it stays open for your next run.",
            ],
            [
                "What if some invoices are already submitted?",
                "The software reads the current status of every invoice before every run. Invoices already submitted, by you or by it, aren’t sent again.",
            ],
            [
                "Does the software update itself?",
                "Yes. Changes for CAMS and KFintech reach it by themselves. When a new version of the software is out, it shows Update now, and runs again once you’ve updated.",
            ],
            [
                "What if CAMS or KFintech change their workflow?",
                "We adapt fast, so the service keeps working.",
            ],
            [
                "Does it put the invoices in Tally or Zoho Books?",
                "Yes, into either. The month goes in as sales entries matching exactly what was submitted.",
            ],
            [
                "Do I still need a CA?",
                "Yes. This does the invoicing and the upload. Your CA still files your returns, and their job gets easier because your invoices and your books already match.",
            ],
        ],
    },
    {
        id: "your-data",
        title: "Your data",
        items: [
            [
                "Where does my data live?",
                'Your passwords, your signature, your mailbox and your invoice files stay on your PC. A record of how each run went reaches us, so we can fix a portal change fast. <a href="/security">See how</a>.',
            ],
            [
                "Can I get a copy of my data?",
                'Yes. Submit <a href="/support?about=data">this form</a> and we’ll email you everything we hold about you.',
            ],
            [
                "Do you read my email?",
                "The software opens only the registrar’s invoice mails. It never sends, moves or deletes anything.",
            ],
            ["Can you see my passwords?", "No. Passwords and other sensitive information never leave your PC."],
            [
                "Do you sell my data or show ads?",
                "No. We don’t sell your data, show you ads, or track you across other websites.",
            ],
        ],
    },
    {
        id: "account-and-billing",
        title: "Account and billing",
        items: [
            [
                "Can one account have more than one ARN?",
                SALES.moreArns
                    ? `Yes, up to ${word(PRICE.maxArns)}. Each ARN runs with its own details, and you switch between them in the software.`
                    : "Not yet: one ARN per email for now. More ARNs per email are coming soon.",
            ],
            [
                "How is my ARN tied to my account?",
                "When you add an ARN in the software, it’s tied to your account for as long as your plan or free trial runs, and no other account can add it. The software also checks it’s the ARN CAMS and KFintech show for your logins. Once your plan has ended, another account that adds the same ARN takes it over, and we email you if that happens.",
            ],
            ...(SALES.moreArns
                ? ([["Can I add an ARN partway through the year?", "Yes, it costs only the months left on your plan, and it ends with your plan."]] as [string, string][])
                : []),
            [
                "How can I move my plan to another ARN?",
                'Write to <a href="/support?about=arn">support</a>. We may refuse if a plan keeps moving between ARNs.',
            ],
            [
                "Do I get a GST invoice?",
                SALES.gst
                    ? 'Yes. Checkout asks for your GSTIN, and the tax invoice is emailed to you. Past invoices are in your <a href="/account">account</a>.'
                    : 'Not yet. For now you get a receipt by email, and it’s in your <a href="/account">account</a>. GST invoices start once our company’s registration is complete.',
            ],
            [
                "What if I pay during my free trial?",
                "If you pay during your free trial, the year starts when the trial ends.",
            ],
            [
                "What if it isn’t for me?",
                `Try it completely for free, no catch, for ${TRIAL.days} days before you pay. Once you’ve paid, there are no refunds: see the <a href="/refunds">refund policy</a>.`,
            ],
            ["What if I pay twice?", "We return the extra payment."],
            ["What if I paid and my plan never started?", "We return that payment."],
            ["How long does a refund take?", "5 days."],
            [
                "What happens when I delete my account?",
                'The software stops working. What we keep afterwards is in the <a href="/privacy">Privacy policy</a>.',
            ],
        ],
    },
];
