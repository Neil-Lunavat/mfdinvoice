<script lang="ts">
  import { FORWARD, NAME } from '../../brand';
  /* How CAMS's email reaches the software, three ways, in this order (Neil, 7 Oct):
       forward  the person's Gmail forwards CAMS's mailbacks, by a filter, to our address; each is locked for this PC
                (hands/forward.py, server/src/forward.ts). For people who won't give an app password.
       gmail    Gmail with an app password, read here, with a passed test
       folder   by hand: the person chooses CAMS's two files each month
     Whatever fails falls back to by hand: the run asks for the files. */
  import { app, type MailProvider, type ProfileDraft } from '../../bridge';
  import { appPasswordLetters, appPasswordShown, emailOk } from '../../logic/validate';
  import { store } from '../../state/store.svelte';
  import { icons } from '../../ui/icons';
  import Help from './Help.svelte';

  let { d = $bindable() }: { d: ProfileDraft } = $props();
  const had = d.mailbox;
  let picked = $state<MailProvider | ''>(had.address || had.connected ? had.provider : '');
  let pw = $state('');
  let busy = $state(false);
  let result = $state<{ ok: boolean; text: string } | null>(had.connected && had.provider === 'gmail' ? { ok: true, text: 'Connected' } : null);

  function pick(p: MailProvider) {
    if (p === picked) return;
    picked = p; result = null; said = ''; sent = false;
    d.mailbox = { provider: p, address: p === 'folder' ? '' : d.camsEmail, connected: p === 'folder' };
  }
  const edited = () => { d.mailbox.connected = false; result = null; };
  const ready = $derived(emailOk(d.mailbox.address) && appPasswordLetters(pw).length === 16);

  async function test() {
    busy = true; result = null;
    const r = await app.testMailbox({ provider: 'gmail', address: d.mailbox.address, appPassword: appPasswordLetters(pw) });
    busy = false;
    d.mailbox.connected = r.ok;
    result = r.ok ? { ok: true, text: `Connected · ${r.found} CAMS invoice mails in the last 30 days` } : { ok: false, text: r.said };
  }

  // forwarding: a code to the CAMS email proves it is theirs; then Gmail's own confirmation code shows here
  let sent = $state(false), code = $state(''), said = $state(''), gmailCode = $state('');
  async function sendCode() {
    busy = true; said = '';
    const r = await app.forwardStart(d.mailbox.address);
    busy = false;
    if (r.ok) sent = true; else said = r.said ?? "It didn't send.";
  }
  async function checkCode() {
    busy = true; said = '';
    const r = await app.forwardVerify(d.mailbox.address, code.replace(/\D/g, ''));
    busy = false;
    if (r.ok) d.mailbox.connected = true; else said = r.said ?? "That code isn't right.";
  }
  // Gmail's confirmation code: looked for every few seconds once the email is proved, until it comes
  $effect(() => {
    if (picked !== 'forward' || !d.mailbox.connected || gmailCode) return;
    let alive = true;
    const look = async () => { const c = await app.forwardGmailCode(); if (alive && c) gmailCode = c; };
    void look();
    const t = setInterval(look, 5000);
    return () => { alive = false; clearInterval(t); };
  });
  function copy(text: string) { void navigator.clipboard?.writeText(text); store.toast('Copied'); }
</script>

<p class="line">{NAME} reads only CAMS's invoice mails. It never sends, moves or deletes anything.</p>
<div class="tiles" role="radiogroup" aria-label="How CAMS's email reaches {NAME}">
  <button class="tile" class:on={picked === 'forward'} role="radio" aria-checked={picked === 'forward'} onclick={() => pick('forward')}>
    {@html icons.mark(14)}<span><b>Forward them to {NAME}</b><br /><span class="line">No password given</span></span></button>
  <button class="tile" class:on={picked === 'gmail'} role="radio" aria-checked={picked === 'gmail'} onclick={() => pick('gmail')}>
    <span class="logo g">G</span><span><b>Gmail app password</b><br /><span class="line">{NAME} reads them in Gmail</span></span></button>
  <button class="tile" class:on={picked === 'folder'} role="radio" aria-checked={picked === 'folder'} onclick={() => pick('folder')}>
    <span class="logo n">…</span><span><b>I'll choose the files</b><br /><span class="line">Each month, by hand</span></span></button>
</div>

{#if picked === 'forward'}
  <div class="sub-part enter">
    <p class="line">Your Gmail sends only CAMS's invoice mails on to {NAME}. Each one is locked so only this PC can open it, and deleted from our side once it's here.</p>
    <div class="field"><label for="fa">1. Your CAMS email</label>
      <input id="fa" class="input" bind:value={d.mailbox.address} disabled={d.mailbox.connected} oninput={() => { sent = false; }} />
      <span class="hint">A code goes to it, to show it's yours.</span></div>
    {#if !d.mailbox.connected}
      {#if !sent}
        <div class="testrow"><button class="btn secondary" disabled={busy || !emailOk(d.mailbox.address)} onclick={sendCode}>Send me a code</button>
          {#if busy}<span class="spin"></span>{/if}</div>
      {:else}
        <div class="field"><label for="fc">The code from that email</label>
          <input id="fc" class="input mono" style="max-width:160px" inputmode="numeric" maxlength="6" bind:value={code} /></div>
        <div class="testrow"><button class="btn secondary" disabled={busy || code.replace(/\D/g, '').length !== 6} onclick={checkCode}>Verify</button>
          <button class="btn ghost sm" disabled={busy} onclick={sendCode}>Send again</button>{#if busy}<span class="spin"></span>{/if}</div>
      {/if}
      {#if said}<span class="err">{said}</span>{/if}
    {:else}
      <div class="testrow"><span class="okl">{@html icons.tickSm}{d.mailbox.address} is yours</span></div>
      <div class="field"><span class="flabel">2. In Gmail: Settings › See all settings › Forwarding and POP/IMAP › Add a forwarding address</span>
        <div class="testrow"><span class="mono">{FORWARD}</span><button class="btn ghost sm" onclick={() => copy(FORWARD)}>{@html icons.copy}Copy</button></div>
        {#if gmailCode}
          <div class="testrow"><span>Gmail's code to type there: <b class="mono">{gmailCode}</b></span><button class="btn ghost sm" onclick={() => copy(gmailCode)}>{@html icons.copy}Copy</button></div>
        {:else}<span class="hint"><span class="spin"></span> Gmail's code shows here once you've added the address.</span>{/if}</div>
      <div class="field"><span class="flabel">3. Then the filter, so only CAMS's mails come</span>
        <span class="hint">In Gmail's search box: <span class="mono">from:donotreply@camsonline.com</span> › the filter icon › Create filter › tick "Forward it to" ({FORWARD}) and "Never send it to Spam" › Create filter.</span></div>
    {/if}
  </div>
{:else if picked === 'gmail'}
  <div class="sub-part enter">
    <button class="btn secondary sm" style="align-self:flex-start" onclick={() => app.open('help')}>{@html icons.play}Create an app password · 2 min</button>
    <div class="field"><label for="ga">Gmail address</label>
      <input id="ga" class="input" bind:value={d.mailbox.address} oninput={edited} /><span class="hint">Where CAMS sends your invoice mails</span></div>
    <div class="field"><label for="gp">App password <Help text="Google Account › Security › App passwords: a 16-letter code" /></label>
      <div class="secret"><input id="gp" class="input mono pw" autocomplete="off" spellcheck="false" style="max-width:260px" class:bad={result && !result.ok}
        value={pw} oninput={e => { const t = e.currentTarget; t.value = appPasswordShown(t.value); pw = t.value; edited(); }} />
        <span class="lock">{@html icons.lock}This PC only</span></div>
      <span class="hint">16 letters, from Google. Not your Gmail password.</span></div>
    <div class="testrow"><button class="btn secondary" disabled={!ready || busy} onclick={test}>Verify connection</button>
      {#if busy}<span class="spin"></span>{:else if result}<span class={result.ok ? 'okl' : 'err'}>{#if result.ok}{@html icons.tickSm}{/if}{result.text}</span>{/if}</div>
  </div>
{:else if picked === 'folder'}
  <div class="sub-part enter">
    <p class="line">Each month, download CAMS's invoice zip and Excel from its email, then open them when the run asks.</p>
  </div>
{/if}

<style>
  .tile { flex-direction: row; align-items: center; gap: 10px; }
  .tile :global(svg) { flex-shrink: 0; }
  .flabel { font-size: 13px; font-weight: 500; color: var(--ink-2); }
</style>
