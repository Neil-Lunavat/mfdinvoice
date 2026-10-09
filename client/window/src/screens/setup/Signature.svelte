<script lang="ts">
  /* The signature's controls: a photo of the handwritten signature, cleaned on this PC, with Rotate 90° because
     photos arrive sideways, and its size. What it looks like is shown by whoever uses this, on the real invoice
     beside it (Your invoices). Or a USB signing token: its certificate found on this PC, picked, and a test
     signature made, for which the token's own software asks for its PIN. Each way's setup is kept when the other
     is picked. */
  import { app, type Cert, type ProfileDraft } from '../../bridge';
  import { dayMonYear } from '../../logic/format';
  import { store } from '../../state/store.svelte';
  import { icons } from '../../ui/icons';
  import RegistrarPreview from '../../ui/RegistrarPreview.svelte';

  /* The USB token way is offered (Neil, 7 Oct: the proof of concept signed with a real token). Its first real use is a
     distributor's; what goes wrong comes back as an "ours" report. */
  const DSC_OFFERED = true;

  let { d = $bindable() }: { d: ProfileDraft } = $props();
  let tab = $state<'CAMS' | 'KFINTECH'>('CAMS');
  let cleaning = $state(false);
  let over = $state(false);
  let said = $state('');
  let file: HTMLInputElement;

  function pick(way: 'image' | 'dsc') {
    d.signature.way = way;
    d.signature.present = way === 'dsc' ? !!d.signature.cert?.tested : !!d.signature.image;
  }

  async function take(f: File | undefined) {
    if (!f) return;
    cleaning = true; said = '';
    const bytes = await new Promise<string>(res => { const r = new FileReader(); r.onload = () => res(String(r.result).split(',')[1] ?? ''); r.readAsDataURL(f); });
    const r = await app.prepareSignature({ bytes });
    cleaning = false;
    if (r.ok) d.signature = { ...d.signature, way: 'image', present: true, image: r.image, size: 100 };
    else said = r.said;
  }
  async function rotate() { const r = await app.rotateSignature(); d.signature.image = r.image; }

  // --- a USB token ---
  let certs = $state<Cert[] | null>(null);
  let looking = $state(false);
  let testing = $state(false);
  let tokenSaid = $state('');
  let other = $state(false);              // it did not sign through Windows; its PIN typed here may work
  async function look() {
    looking = true; tokenSaid = ''; other = false;
    const r = await app.findCertificates();
    looking = false;
    certs = r.certs;
    if (r.certs.length === 1 && d.signature.cert?.thumbprint !== r.certs[0].thumbprint) choose(r.certs[0]);
  }
  function choose(c: Cert) {
    d.signature.cert = { ...c, tested: false };
    d.signature.present = false;
    tokenSaid = ''; other = false;
  }
  async function test(route: Cert['route']) {
    const c = d.signature.cert;
    if (!c) return;
    testing = true; tokenSaid = '';
    const r = await app.testCertificate({ thumbprint: c.thumbprint, route });
    testing = false;
    store.setupPin = null;
    if (r.ok) { d.signature.cert = { ...c, route, tested: true }; d.signature.present = true; other = false; }
    else { tokenSaid = r.said; other = r.other; }
  }
  let pin = $state('');
  function answerPin(value: string | null) {
    const q = store.setupPin;
    if (!q) return;
    store.setupPin = null;
    app.answer(q.id, { type: 'pin', value });
    pin = '';
  }
</script>

{#if DSC_OFFERED || d.signature.way === 'dsc'}
<div class="tiles2" role="radiogroup" aria-label="How you sign">
  <button class="tile" class:on={d.signature.way === 'image'} role="radio" aria-checked={d.signature.way === 'image'} onclick={() => pick('image')}>
    {@html icons.image}<span><b>A photo of your signature</b><br /><span class="line">Signed on paper, photographed</span></span></button>
  <button class="tile" class:on={d.signature.way === 'dsc'} role="radio" aria-checked={d.signature.way === 'dsc'} onclick={() => pick('dsc')}>
    {@html icons.lock}<span><b>A USB signing token (DSC)</b><br /><span class="line">Your digital signature certificate</span></span></button>
</div>
{/if}

<input bind:this={file} type="file" accept="image/*" hidden onchange={() => take(file.files?.[0])} />
{#if d.signature.way === 'image'}
  {#if !d.signature.image}
    <div class="drop" class:over role="group" aria-label="Signature photo"
      ondragover={e => { e.preventDefault(); over = true; }} ondragleave={() => (over = false)}
      ondrop={e => { e.preventDefault(); over = false; take(e.dataTransfer?.files[0]); }}>
      {#if cleaning}
        <span class="spin"></span><b>Cleaning the photo</b><span>Removing the paper behind the ink.</span>
      {:else}
        {@html icons.image}<b>Drop a photo of your signature here</b><span>Sign on plain white paper and take the photo in daylight.</span>
        <button class="btn secondary" onclick={() => file.click()}>Choose a photo</button>
        {#if said}<span class="err">{said}</span>{/if}
      {/if}
    </div>
  {:else}
    <div class="sigwrap enter">
      <div class="sigctl">
        <label class="sz">Size <input type="range" min="60" max="140" bind:value={d.signature.size} /></label>
        <button class="btn secondary sm" onclick={rotate}>{@html icons.rot}Rotate 90°</button>
        <button class="btn ghost sm" onclick={() => { d.signature = { ...d.signature, present: false, image: '', size: 100 }; }}>Choose another</button>
      </div>
    </div>
  {/if}
{:else}
  <div class="sigwrap enter">
    {#if d.signature.cert}
      <div class="certrow"><div><b>{d.signature.cert.name}</b>
        <span class="line">{d.signature.cert.issuer}{d.signature.cert.expires ? ` · valid till ${dayMonYear(d.signature.cert.expires)}` : ''}</span></div>
        {#if d.signature.cert.tested}<span class="okl">{@html icons.tickSm}Signed a test</span>{/if}</div>
    {/if}
    {#if certs && certs.length > 1}
      <div class="certs" role="radiogroup" aria-label="Your certificates">
        {#each certs as c (c.thumbprint)}
          <label class="check"><input type="radio" name="cert" checked={d.signature.cert?.thumbprint === c.thumbprint} onchange={() => choose(c)} />
            {c.name} <span class="line">· {c.issuer} · valid till {dayMonYear(c.expires)}</span></label>
        {/each}
      </div>
    {:else if certs && !certs.length}
      <p class="err">No signing certificate was found. Plug in your token, make sure its own software is installed (it usually comes on the token itself), and look again.</p>
    {/if}
    <div class="testrow">
      <button class="btn secondary" disabled={looking || testing} onclick={look}>{d.signature.cert || certs ? 'Look again' : 'Find my token'}</button>
      {#if d.signature.cert && !d.signature.cert.tested}
        <button class="btn primary" disabled={testing} onclick={() => test(d.signature.cert?.route ?? 'windows')}>Sign a test</button>
      {/if}
      {#if looking || (testing && !store.setupPin)}<span class="spin"></span>{/if}
      {#if tokenSaid}<span class="err">{tokenSaid}</span>{/if}
    </div>
    {#if other && !testing}
      <p class="line">Your token's own PIN box didn't sign. <a href="#pin" onclick={e => { e.preventDefault(); test('pin'); }}>Try with the PIN typed here instead</a></p>
    {/if}
    {#if store.setupPin}
      <div class="capbox enter">
        <b>Type your token's PIN.</b>
        {#if store.setupPin.said}<span class="err" style="font-size:12.5px">{store.setupPin.said}</span>{/if}
        <div class="caprow">
          <input type="password" class="input" style="max-width:200px" bind:value={pin} autocomplete="off" aria-label="Token PIN" data-own-enter
            onkeydown={e => { if (e.key === 'Enter' && pin) { e.preventDefault(); e.stopPropagation(); answerPin(pin); } }} />
          <button class="btn primary" disabled={!pin} onclick={() => answerPin(pin)}>Sign</button>
          <button class="btn ghost" onclick={() => answerPin(null)}>Cancel</button>
        </div>
        <span class="hint" style="font-size:12.5px">It goes to your token only. It is never saved.</span>
      </div>
    {:else}
      <p class="line">Signing a test is when your token asks for its PIN. Each run asks once, before your invoices are signed.</p>
    {/if}
    {#if d.signature.cert}
      <div class="seg" role="tablist">
        <button role="tab" aria-selected={tab === 'CAMS'} class:on={tab === 'CAMS'} onclick={() => (tab = 'CAMS')}>CAMS invoice</button>
        <button role="tab" aria-selected={tab === 'KFINTECH'} class:on={tab === 'KFINTECH'} onclick={() => (tab = 'KFINTECH')}>KFintech invoice</button>
      </div>
      {#if tab === 'CAMS'}<RegistrarPreview kind="cams" name={d.name} gstin={d.gstin} arn={d.arn} signature={d.signature} way="dsc" certName={d.signature.cert.name} />
      {:else}<RegistrarPreview kind="kfintech" name={d.name} gstin={d.gstin} arn={d.arn} signature={d.signature} way="dsc" certName={d.signature.cert.name} />{/if}
    {/if}
  </div>
{/if}
<p class="line" style="display:flex;gap:6px;align-items:center">{@html icons.lock}Stays on this PC.</p>

<style>
  .tiles2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .tiles2 .tile { flex-direction: row; align-items: center; gap: 12px; }
  .certrow { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 14px; border: 1px solid var(--line); border-radius: var(--r-card); background: var(--surface); }
  .certrow div { display: flex; flex-direction: column; gap: 2px; }
  .certs { display: flex; flex-direction: column; gap: 6px; }
</style>
