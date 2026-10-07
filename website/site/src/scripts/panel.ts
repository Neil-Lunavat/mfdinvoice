/* The admin panel's and the editor's own script: what each API error means to the owner, and the dialog that says it.
   The rest (find, escape, POST, the dialog itself) is scripts/client.ts. */
import { ask as askAny, type Ask } from './client';

const ERR: Record<string, string> = {
  offline: 'Couldn’t reach the server.',
  no_title: 'Give the survey a title.', no_questions: 'Add at least one question.', too_many_questions: 'Twenty questions at most.',
  empty_question: 'A question is empty.', few_options: 'A choice question needs at least two options.', not_draft: 'It has gone live, so it can’t be changed. Reload.', wrong_state: 'It changed meanwhile. Reload.',
  no_arn: 'That ARN isn’t on this account.', email_taken: 'Another account has that email.', same_email: 'That’s the email it has already.',
  bad_email: 'That email doesn’t look right.', bad_arn: 'That ARN doesn’t look right.', not_in_review: 'It isn’t waiting any more. Reload.', not_blocked: 'They can pay already. Reload.', no_accounts: 'Pick at least one account.', has_plan: 'They already have a running plan. Approving would start another.', no_account: 'That account was deleted.',
  already_paid: 'It’s approved already.', not_waiting: 'That gift isn’t waiting any more.', no_receipt: 'No such receipt.',
  slug_taken: 'Another post uses that address, now or before.', no_search_title: 'Add the search title.', no_description: 'Add the description.', no_text: 'Add some text.', bad_time: 'Pick a time in the future.',
  no_subject: 'Add a subject.', no_message: 'Write the message.', too_big: 'The photos are too big together (4 MB at most).', not_an_image: 'Photos only: JPG, PNG or WebP.',
  too_many_files: 'Three photos at most.', not_sent: 'The email didn’t go out. Try again.', no_request: 'That request no longer exists.',
  had_plan: 'Gifts are only for someone who has never had a paid or gifted plan.', no_title: 'Add the heading.', no_slug: 'Add the address.', too_many_requests: 'Too many at once. Try again soon.',
};
export const errText = (r: any) => ERR[r?.error] ?? `That didn’t work (${r?.error ?? r?.status ?? 'error'}).`;

export const ask = (a: Ask) => askAny({ error: errText, ...a });

/* Click a column's header to sort the table by it; again to reverse. A column of categories (data-sort="cat") puts
   each category first in turn instead. data-sort: "text", "num" or "cat"; a cell sorts by its data-v, else its text. */
export function sortable(table: HTMLTableElement | null) {
  if (!table) return;
  const body = table.tBodies[0], ths = [...table.tHead!.rows[0].cells];
  const val = (r: HTMLTableRowElement, i: number) => r.cells[i]?.dataset.v ?? r.cells[i]?.textContent?.trim() ?? '';
  let col = -1, step = 0;
  ths.forEach((th, i) => {
    const kind = th.dataset.sort;
    if (!kind) return;
    th.tabIndex = 0;
    const go = () => {
      step = col === i ? step + 1 : 0; col = i;
      ths.forEach(h => delete h.dataset.on);
      const rows = [...body.rows];
      if (kind === 'cat') {
        const cats = [...new Set(rows.map(r => val(r, i)))];
        const first = cats.sort()[step % cats.length];
        rows.sort((a, b) => +(val(a, i) !== first) - +(val(b, i) !== first));
        th.dataset.on = `· ${first}`;
      } else {
        const dir = step % 2 ? -1 : 1;
        rows.sort((a, b) => dir * (kind === 'num' ? Number(val(a, i)) - Number(val(b, i)) : val(a, i).localeCompare(val(b, i))));
        th.dataset.on = dir === 1 ? '↑' : '↓';
      }
      rows.forEach(r => body.appendChild(r));
    };
    th.onclick = go;
    th.onkeydown = (e: KeyboardEvent) => { if (e.key === 'Enter') go(); };
  });
}
