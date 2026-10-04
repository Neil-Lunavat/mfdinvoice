<script lang="ts">
  import type { ProfileDraft } from '../../bridge';
  import { consentNow, consentText } from '../../logic/consent';
  import { arnInput, arnOk, gstinError, gstinInput, gstinOk, panOf, stateOf } from '../../logic/validate';
  import Help from './Help.svelte';

  let { d = $bindable(), editing = false, arnLocked = false }: { d: ProfileDraft; editing?: boolean; arnLocked?: boolean } = $props();

  // an error shows only once they have typed a few characters, or left the field
  let touched = $state({ arn: false, gst: false, nm: false });
  const typed = (k: keyof typeof touched, v: string) => { if (v.trim().length > 3) touched[k] = true; };
  const arnBad = $derived(touched.arn && !!d.arn && !arnOk(d.arn));
  const gstBad = $derived(touched.gst && !!d.gstin && !gstinOk(d.gstin));
  const nmBad = $derived(touched.nm && !!d.name && d.name.trim().length < 3);
  // the sentence names the ARN: ticked, then the ARN changed, it is the new ARN's sentence that is agreed to
  $effect(() => { if (!editing && d.consent && d.consent.text !== consentText(d.arn)) d.consent = consentNow(d.arn); });
</script>

{#if !editing}
  <div class="need"><b>About 10 minutes.</b> Keep these handy: your ARN and GSTIN, your Gmail, your KFintech login, and a photo of your signature on white paper.</div>
{/if}
<div class="field">
  <label for="arn">ARN <Help text="AMFI certificate, top right: “ARN-104512”" /></label>
  <input id="arn" class="input mono" placeholder="ARN-" style="max-width:220px" disabled={arnLocked} class:bad={arnBad}
    value={d.arn} oninput={e => { const t = e.currentTarget; t.value = arnInput(t.value); d.arn = t.value; typed('arn', t.value); }}
    onblur={() => { if (d.arn) touched.arn = true; }} />
  {#if arnBad}<span class="err">ARN is "ARN-" and then its digits</span>
  {:else}<span class="hint">{arnLocked ? 'Confirmed by your portal login. Wrong? Send it to support.' : 'As on your AMFI certificate'}</span>{/if}
</div>
<div class="field">
  <label for="gst">GSTIN <Help text="GST registration certificate, first line: “Registration Number”" /></label>
  <input id="gst" class="input mono" maxlength="15" style="max-width:260px" class:bad={gstBad}
    value={d.gstin} oninput={e => { const t = e.currentTarget; t.value = gstinInput(t.value); d.gstin = t.value; typed('gst', t.value); }}
    onblur={() => { if (d.gstin) touched.gst = true; }} />
  {#if gstBad}<span class="err">{gstinError(d.gstin)}</span>
  {:else}<span class="hint">15 characters, from your GST certificate</span>{/if}
  {#if gstinOk(d.gstin)}<div class="derived"><span>PAN <b>{panOf(d.gstin)}</b></span><span>State <b>{stateOf(d.gstin)}</b></span></div>{/if}
</div>
<div class="field">
  <label for="nm">Name on invoices</label>
  <input id="nm" class="input" placeholder="As registered for GST" bind:value={d.name} class:bad={nmBad}
    oninput={() => typed('nm', d.name)} onblur={() => { if (d.name) touched.nm = true; }} />
  {#if nmBad}<span class="err">Too short</span>{:else}<span class="hint">As registered for GST</span>{/if}
</div>
{#if !editing}
  <label class="check consent"><input type="checkbox" checked={!!d.consent}
    onchange={e => (d.consent = e.currentTarget.checked ? consentNow(d.arn) : null)} /> {consentText(d.arn)}</label>
  <p class="line">The next steps confirm this ARN with your CAMS and KFintech logins.</p>
{/if}
