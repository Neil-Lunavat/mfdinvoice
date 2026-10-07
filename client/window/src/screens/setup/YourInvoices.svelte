<script lang="ts">
  import { NAME } from '../../brand';
  /* Your invoices: which invoice is uploaded, and everything that goes on it, the signature included, seen on the
     real thing beside the fields.

       the registrar's own, signed   the signature, on an example of CAMS's invoice and of KFintech's
       the distributor's own         the template, the last number they issued (exactly as printed, with the part that
                                     goes up by 1 tapped), the signature, and their address and the rest, on their
                                     own invoice as a run draws it

     `choiceOnly`: just the two options (Settings' Change). `settingsOnly`: everything but the two options (Settings'
     own page, where Change is beside it). Setup shows both, and `noSignature`: the signature has its own step there. */
  import { app, type ProfileDraft } from '../../bridge';
  import { continuesLine, continuesLineNoNext } from '../../logic/books';
  import { booked, nextInvoice } from '../../logic/details';
  import { counterOf, parts, rule46 } from '../../logic/numbering';
  import InvoicePreview from '../../ui/InvoicePreview.svelte';
  import RegistrarPreview from '../../ui/RegistrarPreview.svelte';
  import Signature from './Signature.svelte';

  let { d = $bindable(), settingsOnly = false, choiceOnly = false, noSignature = false }: { d: ProfileDraft; settingsOnly?: boolean; choiceOnly?: boolean; noSignature?: boolean } = $props();

  const s = $derived(d.invoices.settings);
  const segs = $derived(parts(d.invoices.last));
  const at = $derived(counterOf(d.invoices.last, d.invoices.at));
  const refused = $derived(rule46(d.invoices.last));
  const next = $derived(nextInvoice(d.invoices));
  let addressText = $state(d.invoices.settings.address.join('\n'));
  // with Tally connected: where the invoice numbers continue from, read from Tally (nothing is written to it)
  let continues = $state('');
  $effect(() => {
    const company = d.tally?.company;
    continues = '';
    if (!company || d.invoices.source !== 'own') return;
    void app.booksNext(company, d.arn).then(r => { if (d.tally?.company === company && r.state === 'ready') continues = r.next; });
  });

  function choose(source: 'registrar' | 'own') { d.invoices.source = source; }
  function typed(v: string) { d.invoices.last = v; d.invoices.at = counterOf(v, -1); }
  function lines(v: string) { addressText = v; d.invoices.settings.address = v.split('\n').map(x => x.trim()).filter(Boolean).slice(0, 8); }
</script>

{#if !settingsOnly}
  <div class="choice" role="radiogroup" aria-label="Which invoice is uploaded">
    <button class="opt" class:on={d.invoices.source === 'registrar'} role="radio" aria-checked={d.invoices.source === 'registrar'}
      onclick={() => choose('registrar')}><b>The registrar's invoice, signed</b>
      <span>CAMS and KFintech make the invoice. {NAME} signs it. Quicker, nothing to set up.</span></button>
    <button class="opt" class:on={d.invoices.source === 'own'} role="radio" aria-checked={d.invoices.source === 'own'}
      onclick={() => choose('own')}><b>My own invoice, in my number series</b>
      <span>{NAME} makes yours, like Tally, with the registrar's figures. For anyone already numbering their own this year.</span></button>
  </div>
{/if}

{#if !choiceOnly && d.invoices.source === 'registrar' && !noSignature}
  <div class="row2 top sub-part enter">
    <div class="fcol">
      <div class="field"><span class="label">Your signature</span></div>
      <Signature bind:d />
      <p class="line">This is how it goes on each registrar's invoice. The layout is theirs; the fund house and the figures here are examples.</p>
    </div>
    {#if d.signature.way === 'image' && d.signature.image}
      <div class="regprev">
        <RegistrarPreview kind="cams" name={d.name} gstin={d.gstin} arn={d.arn} signature={d.signature} />
        {#if d.kfintech.used}<RegistrarPreview kind="kfintech" name={d.name} gstin={d.gstin} arn={d.arn} signature={d.signature} />{/if}
      </div>
    {/if}
  </div>
{/if}

{#if !choiceOnly && d.invoices.source === 'own'}
  <div class="row2 top sub-part enter">
    <div class="fcol">
      <div class="field"><label for="tpl">Template</label>
        <select id="tpl" class="input" style="max-width:300px" bind:value={d.invoices.settings.template}>
          <option value="tally">Tally standard print</option></select></div>
      {#if booked(d)}
        <p class="line">{continues ? continuesLine(continues) : continuesLineNoNext(d.tally!.company)}</p>
      {:else}
      <div class="field">
        <label for="last">Your last invoice number, exactly as printed</label>
        <input id="last" class="input mono" style="max-width:300px" placeholder="RKM/26-27/073" value={d.invoices.last}
          oninput={e => typed(e.currentTarget.value)} />
        {#if segs.some(p => p.digits)}
          <div class="segs"><span class="hint">Which part goes up by 1?</span>
            <div class="segrow">
              {#each segs as p (p.start)}
                {#if p.digits}<button type="button" class="seg-t" class:on={p.start === at} onclick={() => (d.invoices.at = p.start)}>{p.text}</button>
                {:else}<span class="seg-f">{p.text}</span>{/if}
              {/each}
            </div></div>
        {/if}
        {#if refused}<span class="err" role="alert">{refused}</span>{/if}
        {#if next}<div class="derived"><span>Your next invoice <b>{next}</b></span></div>{/if}
      </div>
      {/if}
      {#if !noSignature}
        <div class="field"><span class="label">Your signature</span></div>
        <Signature bind:d />
      {/if}
      <div class="field">
        <label for="addr">Your address, as it is on your invoices</label>
        <textarea id="addr" class="input ta" rows="3" placeholder="One line each" value={addressText} oninput={e => lines(e.currentTarget.value)}></textarea>
      </div>
      <div class="row2">
        <div class="field"><label for="ph">Phone</label><input id="ph" class="input" bind:value={d.invoices.settings.phone} /></div>
        <div class="field"><label for="ml">Email</label><input id="ml" class="input" bind:value={d.invoices.settings.email} /></div>
      </div>
      {#if settingsOnly}
        <div class="field"><label for="web">Website <span class="hint">(if you print one)</span></label><input id="web" class="input" bind:value={d.invoices.settings.website} /></div>
        <div class="field"><label for="part">Particulars</label>
          <input id="part" class="input" bind:value={d.invoices.settings.particulars} />
          <label class="check"><input type="checkbox" bind:checked={d.invoices.settings.particularsAmc} /> Put the fund house's name in front</label></div>
        <div class="field"><label for="rem">Remarks <span class="hint">(if you use a remarks line)</span></label><input id="rem" class="input" bind:value={d.invoices.settings.remarks} /></div>
      {/if}
      <p class="line">Each fund house's name, GSTIN and address come from the registrar's invoice for it, every month. The figures and dates are always the registrar's.</p>
    </div>
    <InvoicePreview settings={s} number={continues || next || d.invoices.last || '1'} name={d.name} gstin={d.gstin} signature={d.signature} />
  </div>
{/if}
