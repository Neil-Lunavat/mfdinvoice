<script lang="ts">
  import { NAME } from '../../brand';
  /* Mailbox: Gmail, with a passed test; or no mailbox at all, and the person chooses CAMS's two files each month. */
  import { app, type MailProvider, type ProfileDraft } from '../../bridge';
  import { appPasswordLetters, appPasswordShown, emailOk } from '../../logic/validate';
  import { icons } from '../../ui/icons';
  import Help from './Help.svelte';

  let { d = $bindable() }: { d: ProfileDraft } = $props();
  const had = d.mailbox;
  let picked = $state<MailProvider | 'other' | ''>(had.address || had.connected ? (had.provider === 'folder' ? 'other' : had.provider) : '');
  let pw = $state('');
  let busy = $state(false);
  let result = $state<{ ok: boolean; text: string } | null>(had.connected && had.provider === 'gmail' ? { ok: true, text: 'Connected' } : null);

  function pick(p: MailProvider | 'other') {
    if (p === picked) return;
    picked = p; result = null;
    d.mailbox = { provider: p === 'other' ? 'folder' : p, address: p === 'gmail' ? d.camsEmail : '', connected: false };
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
</script>

<p class="line">{NAME} reads only CAMS's invoice mails. It never sends, moves or deletes anything.</p>
<div class="tiles" role="radiogroup" aria-label="Your mailbox">
  <button class="tile" class:on={picked === 'gmail'} role="radio" aria-checked={picked === 'gmail'} onclick={() => pick('gmail')}><span class="logo g">G</span>Gmail</button>
  <button class="tile" class:on={picked === 'other'} role="radio" aria-checked={picked === 'other'} onclick={() => pick('other')}><span class="logo n">…</span>Mine isn't Gmail</button>
</div>

{#if picked === 'gmail'}
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
{:else if picked === 'other'}
  <div class="sub-part enter">
    <button class="opt" onclick={() => { pick('gmail'); app.open('help'); }}><b>Forward CAMS's mails to a Gmail, and connect that</b><span>Set a forward in your mailbox once. Video: 2 min.</span></button>
    <button class="opt" class:on={d.mailbox.connected} onclick={() => { d.mailbox = { provider: 'folder', address: '', connected: true }; }}>
      <b>I'll choose the files myself</b><span>Each month, download CAMS's invoice zip and Excel, then open them when the run asks.</span></button>
  </div>
{/if}
