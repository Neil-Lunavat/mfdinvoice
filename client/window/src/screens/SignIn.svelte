<script lang="ts">
  import { NAME } from '../brand';
  /* Sign in, with the website: email, then a 6-digit code on the same screen (#2). This PC stays signed in.
     There is no "Create account": an account is made on the website only, and this signs in to one (`no_account`
     otherwise). Every answer the website gives is said in its own words. */
  import { onDestroy, onMount } from 'svelte';
  import { app, type CodeRefusal, type VerifyRefusal } from '../bridge';
  import { ago, dayMonYear, hhmm, maskEmail } from '../logic/format';
  import { emailOk } from '../logic/validate';
  import { store } from '../state/store.svelte';
  import { ui } from '../state/ui.svelte';
  import { icons } from '../ui/icons';

  let { banner = null }: { banner?: 'down' | 'offline' | null } = $props();

  const HINT = 'Six digits, from the email.';
  let email = $state('');
  let emailErr = $state('');
  let noAccount = $state(false);                 // the app never makes an account: that is the website's
  let sentTo = $state('');
  let busy = $state(false);
  let digits = $state(['', '', '', '', '', '']);
  let hint = $state({ text: HINT, bad: false });
  let locked = $state(false);
  // pending_deletion: when the account goes. From the website's answer to a code, or from the app when it found
  // this PC's sign-in ended by the deletion (Snapshot.deleting).
  let deleting = $state(store.snap?.deleting ?? '');
  $effect(() => { if (store.snap?.deleting) deleting = store.snap.deleting; });
  // other_pc: the account is signed in on another PC; the code is still good and is sent again if the person agrees.
  let other = $state<{ device: string; lastSeen: string } | null>(null);
  // this PC was signed out because the account signed in on another (Snapshot.elsewhere): that PC's name.
  let elsewhere = $state(store.snap?.elsewhere ?? '');
  $effect(() => { if (store.snap?.elsewhere) elsewhere = store.snap.elsewhere; });
  let shake = $state(false);
  let resendIn = $state(45);
  let boxes: HTMLInputElement[] = $state([]);
  let emailField: HTMLInputElement | undefined = $state();
  let timer: ReturnType<typeof setInterval> | undefined;

  const code = $derived(digits.join(''));
  const canSend = $derived(emailOk(email) && !busy && banner !== 'offline');
  const canSignIn = $derived(code.length === 6 && !busy && !locked);

  onMount(() => setTimeout(() => emailField?.focus(), 300));
  onDestroy(() => clearInterval(timer));

  const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

  function countdown(from = 45) {
    resendIn = from;
    clearInterval(timer);
    timer = setInterval(() => { if (resendIn > 0) resendIn--; else clearInterval(timer); }, 1000);
  }

  const SEND_SAID: Record<Exclude<CodeRefusal, 'wait' | 'locked'>, string> = {
    bad_email: "That email doesn't look right.",
    no_account: "There's no account for this email. Sign up on the website first.",
    too_many_codes: 'Too many codes were sent to this email in the last hour. Try again later.',
    send_failed: "The email with your code couldn't be sent. Try again.",
    unreachable: `${NAME} can't reach its website right now. Try again in a minute.`
  };

  async function send() {
    if (!canSend) return;
    busy = true;
    const to = email.trim();
    const r = await app.sendCode(to);
    busy = false;
    if (!r.ok && r.reason === 'no_account') { noAccount = true; return; }
    if (!r.ok && r.reason !== 'wait' && r.reason !== 'locked') { emailErr = SEND_SAID[r.reason]; return; }
    sentTo = to;
    digits = ['', '', '', '', '', ''];
    locked = false; deleting = ''; other = null; elsewhere = '';
    if (r.ok) { hint = { text: HINT, bad: false }; countdown(); }
    else if (r.reason === 'wait') { hint = { text: `A code was sent a moment ago and still works. ${HINT}`, bad: false }; countdown(r.wait); }
    else { locked = true; hint = { text: `The last code had three wrong tries. You can send a new one in ${clock(r.wait)}.`, bad: true }; countdown(r.wait); }
    setTimeout(() => boxes[0]?.focus(), 300);
  }

  function verifySaid(reason: VerifyRefusal, left: number): string {
    switch (reason) {
      case 'wrong': return `That code isn't right. ${left} ${left === 1 ? 'try' : 'tries'} left.`;
      case 'locked': return 'Three wrong tries. Send a new code.';
      case 'expired': return 'That code has run out, or a newer one was sent. Send a new code.';
      case 'bad_code': return HINT;
      case 'bad_email': return "That email doesn't look right.";
      case 'unreachable': return `${NAME} can't reach its website right now. Try again in a minute.`;
      case 'pending_deletion': case 'other_pc': return '';
    }
  }

  async function signIn(replace = false) {
    if (!replace && !canSignIn) return;
    busy = true;
    const r = await app.verifyCode(sentTo, code, replace);
    busy = false;
    if (r.ok) {
      other = null;
      const s = store.snap;
      if (s?.arns.length) ui.go('overview'); else void ui.resumeSetup();
      return;
    }
    if (r.reason === 'pending_deletion') { deleting = r.deleteAfter; return; }
    if (r.reason === 'other_pc') { other = { device: r.device || 'another PC', lastSeen: r.lastSeen ?? '' }; return; }
    shake = true; setTimeout(() => (shake = false), 320);
    if (r.reason !== 'unreachable') digits = ['', '', '', '', '', ''];
    locked = r.reason === 'locked' || r.reason === 'expired';
    if (locked) resendIn = 0;
    hint = { text: verifySaid(r.reason, r.left), bad: true };
    if (!locked) setTimeout(() => boxes[0]?.focus());
  }

  function typed(i: number, e: Event) {
    const t = e.currentTarget as HTMLInputElement;
    const v = t.value.replace(/\D/g, '').slice(-1);
    t.value = v; digits[i] = v;
    if (!locked) hint = { text: HINT, bad: false };
    if (v && boxes[i + 1]) boxes[i + 1].focus();
  }
  function key(i: number, e: KeyboardEvent) {
    if (e.key === 'Backspace' && !digits[i] && boxes[i - 1]) boxes[i - 1].focus();
  }
  function paste(e: ClipboardEvent) {
    const t = (e.clipboardData?.getData('text') ?? '').replace(/\D/g, '').slice(0, 6);
    if (!t) return;
    e.preventDefault();
    digits = [...t.padEnd(6, ' ')].map(c => c.trim());
    (boxes[t.length] ?? boxes[5]).focus();
  }
  function different() {
    sentTo = ''; digits = ['', '', '', '', '', '']; locked = false; deleting = ''; other = null; hint = { text: HINT, bad: false };
    setTimeout(() => emailField?.focus());
  }
  async function resend() {
    const r = await app.sendCode(sentTo);
    if (r.ok) { locked = false; hint = { text: HINT, bad: false }; store.toast('Code sent again.'); countdown(); return; }
    if (r.reason === 'wait' || r.reason === 'locked') { countdown(r.wait); return; }
    hint = { text: SEND_SAID[r.reason], bad: true };
  }
</script>

<div class="view signin" data-layer="page">
  <div class="col enter">
    <div class="name"><span class="mark">{@html icons.mark(22)}</span>{NAME}</div>
    <div><h1>Sign in</h1><p class="sub">New here? <a href="#signup" class="ul" onclick={e => { e.preventDefault(); app.open('signup'); }}>Sign up</a></p></div>
    {#if deleting}
      <div class="banner bad" role="alert"><div><b>Your account is set to be deleted on {dayMonYear(deleting)}</b> (at {hhmm(deleting)}).
        Sign in on the website before then to keep it.</div>
        <button class="btn secondary sm" onclick={() => app.open('billing')}>Open the website</button></div>
    {/if}
    {#if elsewhere && !sentTo}
      <div class="banner bad" role="alert"><div><b>Signed out:</b> this account signed in on {elsewhere}.</div></div>
    {/if}
    {#if other}
      <div class="enter">
        <h2>This account is signed in on {other.device}</h2>
        {#if other.lastSeen}<p class="sub">Last used {ago(other.lastSeen)}</p>{/if}
      </div>
      <button class="btn primary lg" data-primary disabled={busy} onclick={() => signIn(true)}>
        {#if busy}<span class="spin" style="border-color:rgba(255,255,255,.35);border-top-color:#fff"></span>Signing in{:else}Sign it out and sign in here{/if}</button>
      <button class="btn secondary lg" disabled={busy} onclick={different}>Keep it there</button>
    {:else if !sentTo}
      <div class="field">
        <label for="email">Email</label>
        <input id="email" bind:this={emailField} class="input" type="email" autocomplete="off" placeholder="you@example.com" class:bad={!!emailErr || noAccount}
          bind:value={email} oninput={() => { emailErr = ''; noAccount = false; }} />
        {#if noAccount}<span class="err">There's no account for this email. <a href="#signup" class="ul" onclick={e => { e.preventDefault(); app.open('signup'); }}>Sign up on the website</a> to use {NAME}.</span>
        {:else if emailErr}<span class="err">{emailErr}</span>{/if}
      </div>
    {:else}
      <div class="field enter"><span class="label" style="text-transform:none;letter-spacing:0;font-size:13px;color:var(--ink);font-weight:500">Email</span>
        <div class="sentline">Code sent to <b>{maskEmail(sentTo)}</b>.<a href="#different" onclick={e => { e.preventDefault(); different(); }}>Use a different email</a></div>
        <span class="hint">Not in your inbox? Look in Spam, and mark it Not spam.</span></div>
      <div class="enter">
        <div class="field"><span id="codelabel" style="font-size:13px;font-weight:500">Code</span>
          <div class="otp" class:shake role="group" aria-labelledby="codelabel">
            {#each digits as dgt, i (i)}
              <input bind:this={boxes[i]} maxlength="1" inputmode="numeric" aria-label="Digit {i + 1}" value={dgt} disabled={locked}
                class:filled={!!dgt} class:bad={hint.bad} oninput={e => typed(i, e)} onkeydown={e => key(i, e)} onpaste={paste} />
            {/each}
          </div>
          <span class={hint.bad ? 'err' : 'hint'}>{hint.text}</span></div>
        <p class="resend">{#if resendIn > 0}Resend code in <span class="mono">{clock(resendIn)}</span>{:else}<a href="#resend" onclick={e => { e.preventDefault(); resend(); }}>Resend code</a>{/if}</p>
      </div>
    {/if}
    {#if other}{:else if !sentTo}
      <button class="btn primary lg" data-primary disabled={!canSend} onclick={send}>
        {#if busy}<span class="spin" style="border-color:rgba(255,255,255,.35);border-top-color:#fff"></span>Sending{:else}Send code{/if}</button>
    {:else}
      <button class="btn primary lg" data-primary disabled={!canSignIn} onclick={() => signIn()}>
        {#if busy}<span class="spin" style="border-color:rgba(255,255,255,.35);border-top-color:#fff"></span>Signing in{:else}Sign in{/if}</button>
    {/if}
  </div>
</div>
