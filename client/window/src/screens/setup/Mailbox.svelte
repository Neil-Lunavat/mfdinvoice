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
    picked = p; result = null; said = '';
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

  // forwarding: a carousel. The person names the Gmail (slide 0, the claim), adds our address in Gmail's settings,
  // confirms, sets the filter, and ticks that it is there. Done = claimed + ticked: a Gmail that had our address
  // before sends no new confirmation, so the proof (Gmail's confirmation or the first CAMS mail) is only shown.
  const FILTER = 'from:donotreply@camsonline.com has:attachment';
  const LAST = 11;  // the last slide's picture is 12.png (there is no 11.png)
  const WORDS = [
    '', 'In that Gmail, click the gear at the top right.', 'Click See all settings.', 'Open the Forwarding and POP/IMAP tab.',
    'Click Add a forwarding address.', 'Paste our address and click Next.', 'Click Proceed. Gmail may ask you to verify again.',
    'Click OK.', 'Back here: confirm it.', "In Gmail's search box, type this and click the filter icon at the right of the box.",
    'Tick Forward it to, pick our address, then click Create filter.',
    'Check: Settings › Filters and Blocked Addresses shows it, like this.'];
  let claimed = $state(had.provider === 'forward' && had.connected), proved = $state(had.provider === 'forward' && had.connected);
  let filterOk = $state(had.provider === 'forward' && had.connected);
  let said = $state(''), confirm = $state('');
  let slide = $state(had.provider === 'forward' && had.connected ? LAST : 0);
  const sync = () => { d.mailbox.connected = claimed && filterOk; };
  async function next() {
    busy = true; said = '';
    const r = await app.forwardClaim(d.mailbox.address);
    busy = false;
    if (r.ok) { claimed = true; proved = false; confirm = ''; filterOk = false; sync(); slide = 1; } else said = r.said ?? "It didn't go through.";
  }
  function change() { claimed = false; proved = false; confirm = ''; filterOk = false; said = ''; slide = 0; sync(); }
  // Gmail's confirmation (and the proof) looked for every 5 s once the Gmail is named, until the proof has come
  async function look() {
    const r = await app.forwardState();
    if (r.confirm) confirm = r.confirm;
    if (r.proved !== proved) proved = r.proved;
  }
  $effect(() => {
    if (picked !== 'forward' || !claimed || proved) return;
    void look();
    const t = setInterval(look, 5000);
    return () => clearInterval(t);
  });
  // our own forwarding address typed as the CAMS email
  const ours = (e: string) => /@(mailback\.)?mfdinvoice\.co\.in\s*$/i.test(e);
  function copy(text: string) { void navigator.clipboard?.writeText(text); store.toast('Copied'); }
</script>

<p class="line">{NAME} reads only CAMS's invoice mails. It never sends, moves or deletes anything.</p>
<div class="tiles" role="radiogroup" aria-label="How CAMS's email reaches {NAME}">
  <button class="tile" class:on={picked === 'forward'} role="radio" aria-checked={picked === 'forward'} onclick={() => pick('forward')}>
    {@html icons.mark(14)}<span><b>Forward them to {NAME}</b><br /><span class="line">From Gmail · no password given</span></span></button>
  <button class="tile" class:on={picked === 'gmail'} role="radio" aria-checked={picked === 'gmail'} onclick={() => pick('gmail')}>
    <span class="logo g">G</span><span><b>Gmail app password</b><br /><span class="line">{NAME} reads them in Gmail</span></span></button>
  <button class="tile" class:on={picked === 'folder'} role="radio" aria-checked={picked === 'folder'} onclick={() => pick('folder')}>
    <span class="logo n">…</span><span><b>I'll choose the files</b><br /><span class="line">Each month, by hand</span></span></button>
</div>

{#if picked === 'forward'}
  <div class="sub-part enter">
    <p class="line">Your Gmail sends only CAMS's invoice mails on to {NAME}. Each one is locked so only this PC can open it, and deleted from our side once it's here.</p>
    <div class="car">
      <div class="words">
      <p class="cw">{slide === 0 ? 'Which Gmail do you want to use to forward CAMS mailbacks to us?' : WORDS[slide]}</p>
      {#if slide === 5}
        <div class="testrow"><span class="mono">{FORWARD}</span><button class="btn ghost sm" onclick={() => copy(FORWARD)}>{@html icons.copy}Copy</button></div>
      {:else if slide === 8}
        {#if confirm.startsWith('https://')}
          <div class="testrow"><span class="hint">Gmail asks you to confirm</span><button class="btn secondary sm" onclick={() => app.forwardConfirm()}>Confirm</button></div>
        {:else if confirm}
          <span class="hint">Gmail asks you to confirm. Type this code in Gmail's Forwarding settings › Verify.</span>
          <div class="testrow"><b class="mono">{confirm}</b><button class="btn ghost sm" onclick={() => copy(confirm)}>{@html icons.copy}Copy</button></div>
        {:else}
          <span class="hint"><span class="spin"></span> Waiting for Gmail's confirmation… (Not here after a minute? In Gmail's Forwarding tab, click Re-send email.)</span>
        {/if}
        <span class="hint">Already added our address in this Gmail before? Go on.</span>
      {:else if slide === 9}
        <div class="testrow"><span class="mono">{FILTER}</span><button class="btn ghost sm" onclick={() => copy(FILTER)}>{@html icons.copy}Copy</button></div>
      {:else if slide === LAST}
        <label style="display:flex;gap:8px;align-items:center"><input type="checkbox" bind:checked={filterOk} onchange={sync} />It's there</label>
        <span class="hint">{proved ? "Gmail confirmed: CAMS's mailbacks will reach " + NAME + '.' : NAME + " takes it as yours when Gmail's confirmation or the first CAMS mail arrives."}</span>
      {/if}
      </div>
      <div class="frame">
      {#if slide === 0}
        <div class="field">
          <input id="fa" class="input" aria-label="Gmail" bind:value={d.mailbox.address} disabled={claimed} />
          <div class="testrow">
            {#if !claimed}
              <button class="btn secondary" disabled={busy || !emailOk(d.mailbox.address) || ours(d.mailbox.address)} onclick={next}>Next</button>
              {#if busy}<span class="spin"></span>{/if}
            {:else}
              <button class="btn secondary" onclick={() => (slide = 1)}>Next</button>
              <button class="btn ghost sm" onclick={change}>Change</button>
            {/if}
          </div>
          {#if ours(d.mailbox.address)}<span class="err">That's {NAME}'s address. Type the Gmail that will forward to it.</span>{/if}
          {#if said}<span class="err">{said}</span>{/if}
        </div>
      {:else}
        <img src="forward/{String(slide === LAST ? 12 : slide).padStart(2, '0')}.png" alt="" />
      {/if}
      </div>
      <div class="nav">
        <button class="btn secondary sm" disabled={slide === 0} onclick={() => (slide -= 1)}>Back</button>
        <span class="dots">{#each WORDS as _, i}<span class="dot" class:on={i === slide}></span>{/each}</span>
        <button class="btn secondary sm" style:visibility={slide === 0 ? "hidden" : "visible"} disabled={slide === LAST} onclick={() => (slide += 1)}>Next</button>
      </div>
    </div>
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
  .car { display: flex; flex-direction: column; gap: 10px; }
  .cw { margin: 0; font-size: 15px; font-weight: 500; color: var(--ink); }
  /* every slide has the same height: words area and picture frame are fixed, so Back/Next never move.
     The frame is as tall as the window allows (the step above it is about 560px) */
  .words { height: 96px; display: flex; flex-direction: column; gap: 6px; overflow: hidden; }
  .frame { height: clamp(180px, calc(100vh - 560px), 340px); box-sizing: border-box; border: 1px solid var(--line); border-radius: 10px; background: #fff; overflow: hidden; padding: 10px; }
  .frame img { display: block; width: 100%; height: 100%; object-fit: contain; }
  .words > :global(*), .nav { max-width: none; }
  :global(#parts:has(.car)) { max-width: none; }
  :global(#parts:has(.car) .part-hd), :global(#parts:has(.car) .part > :not(.sub-part)), .sub-part > :not(.car) { max-width: 560px; }
  .cw { max-width: 760px; }
  .nav { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
  .dots { display: flex; gap: 6px; }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--line); }
  .dot.on { background: var(--blue); }
</style>
