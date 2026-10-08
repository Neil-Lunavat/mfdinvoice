<script lang="ts">
  /* Your ARN, name and GSTIN: the ARN the logins showed (never typed), and what the portals showed at Verify
     (KFintech's name and GSTIN first, else CAMS's name), offered for the person to confirm; name and GSTIN stay
     typeable. No CAMS page shows the GSTIN, so without KFintech it is typed. In Settings (`editing`) the ARN is
     the ARN's own and does not change. */
  import type { ProfileDraft } from '../../bridge';
  import { provenBy } from '../../logic/details';
  import { gstinError, gstinInput, gstinOk, panOf, stateOf } from '../../logic/validate';
  import { ui } from '../../state/ui.svelte';
  import Help from './Help.svelte';

  let { d = $bindable(), editing = false }: { d: ProfileDraft; editing?: boolean } = $props();

  // an error shows only once they have typed a few characters, or left the field
  let touched = $state({ gst: false, nm: false });
  const typed = (k: keyof typeof touched, v: string) => { if (v.trim().length > 3) touched[k] = true; };
  const gstBad = $derived(touched.gst && !!d.gstin && !gstinOk(d.gstin));
  const nmBad = $derived(touched.nm && !!d.name && d.name.trim().length < 3);

  // each reading from a portal is taken once: what the person typed over it is not put back
  $effect.pre(() => {
    if (editing || ui.read.taken === ui.read.version) return;
    ui.read.taken = ui.read.version;
    d.name = ui.read.kf || ui.read.cams || d.name;
    d.gstin = ui.read.gstin || d.gstin;
  });
  const note = $derived(
    ui.read.kf && ui.read.gstin ? 'Read from KFintech.'
    : ui.read.kf ? "Name read from KFintech. It didn't show a GSTIN: type it."
    : ui.read.cams ? "Name read from CAMS. CAMS doesn't show a GSTIN: type it."
    : 'Type them as on your GST certificate.');
</script>

{#if !editing}<p class="line">{note} Is this correct?</p>{/if}
<div class="field">
  <label for="arn">ARN</label>
  <input id="arn" class="input mono" style="max-width:220px" disabled value={d.arn} />
  <span class="hint">{editing ? 'An ARN never changes. Wrong? Send it to support.' : `Read from ${provenBy(d) || 'your logins'}.`}</span>
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
