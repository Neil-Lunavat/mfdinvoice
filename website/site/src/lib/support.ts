/* Support's topics: the website and your plan. Problems inside the software are reported from the software (Send to support).
   Shared by the page and the server. arn: 0 none, 1 optional, 2 required.
   owner: also copied to the owner's own inbox: what he can fix from his phone, in the admin panel (an ARN slot, an
   email, a payment, a receipt). The rest (the software, setting up, the website) goes to support@ only. */
export type Topic = { label: string; arn: 0 | 1 | 2; ph?: string; arnLabel?: string; noMsg?: boolean; newEmail?: boolean; owner?: boolean;
  mine?: boolean;                           /* the ARN is picked from the account's own (checked on the server) */
  note?: string;                            /* shown under the topic when it's chosen (HTML) */
};

export const TOPICS: Record<string, Topic> = {
  download: { label: 'Downloading the software', arn: 0, ph: 'What happened when you pressed Download.' },
  install:  { label: 'Installing or updating the software', arn: 0, ph: 'Where it stopped, and any message on screen.' },
  setup:    { label: 'Setting up', arn: 2, ph: 'Which step you were on, and what it said.' },
  arn:      { label: 'Change an ARN on my plan', arn: 2, mine: true, arnLabel: 'Which ARN', ph: 'Why, and the ARN you’d like instead.', owner: true,
              note: 'Once we free the slot, add the new ARN in the software.' },
  newemail: { label: 'Change my account’s email', arn: 0, newEmail: true, ph: 'Anything we should know (optional).', owner: true },
  payment:  { label: 'A payment I made', arn: 0, ph: 'Which payment, and what happened.', owner: true },
  plan:     { label: 'My plan or receipts', arn: 0, ph: 'What you need.', owner: true,
              note: 'Wrong name or address on a receipt? Change your billing details on your <a class="tlink" href="/account">Account</a> page first, then write to us and we’ll send it again.' },
  data:     { label: 'A copy of my data', arn: 0, noMsg: true },
  site:     { label: 'Something else on the website', arn: 0, ph: 'Which page, and what went wrong.' },
};

export const SHOT_TYPES: Record<string, string> = { 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp' };
export const SHOT_MAX = 8 * 1024 * 1024, SHOTS = 3;
