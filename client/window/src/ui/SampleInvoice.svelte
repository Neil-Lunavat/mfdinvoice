<script lang="ts">
  /* The signature in the signatory spot of a sample invoice, CAMS's or KFintech's layout: the person's image, or a
     USB token's mark (`mark`: the name on the certificate). */
  let { kind, name, gstin, image, size = 100, mark = '' }: { kind: 'CAMS' | 'KFINTECH'; name: string; gstin: string; image: string; size?: number; mark?: string } = $props();
  const cams = $derived(kind === 'CAMS');
</script>

<div class="page">
  <div class="ph"><div><b>{cams ? 'TAX INVOICE' : 'Tax Invoice cum Bill of Supply'}</b><span>{name || 'Your name'} · GSTIN {gstin || '—'}</span></div>
    <span class="mono">{cams ? 'BM/26-27/E/5' : '128260801030896'}</span></div>
  <div class="lines"><i style="width:62%"></i><i style="width:48%"></i><i style="width:55%"></i></div>
  <div class="rows">{#each [0, 1, 2] as r (r)}<div><i style="width:40%"></i><i style="width:14%"></i><i style="width:14%"></i></div>{/each}</div>
  <div class="pf2"><div class="lines grow"><i style="width:70%"></i><i style="width:50%"></i></div>
    <div class="sigspot">
      {#if mark}<span class="dscmark">Digitally signed by<br />{mark}<br />Date: when it is signed</span>
      {:else if image}<img class="sigimg" src={image} alt="Your signature" style="transform:scale({size / 100})" />{/if}
      <span>For {name || 'you'}<br />Authorised signatory</span>
    </div></div>
</div>

<style>
  .lines { display: flex; flex-direction: column; gap: 5px; }
  .lines.grow { flex: 1; }
  .lines i, .rows i { display: block; height: 5px; border-radius: 3px; background: var(--line-2); }
  .rows { display: flex; flex-direction: column; gap: 7px; border-top: 1px solid var(--line-2); border-bottom: 1px solid var(--line-2); padding: 8px 0; }
  .rows div { display: flex; justify-content: space-between; }
  .dscmark { display: block; text-align: left; font-size: 8px; line-height: 1.3; color: var(--ink); margin-bottom: 4px; }
</style>
