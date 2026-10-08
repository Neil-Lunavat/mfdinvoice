<script lang="ts">
  /* Signature: the photo (or token), seen on the real thing. Where the invoice comes from is asked in Your invoices.
     The controls take the width; the registrars' invoices sit below, side by side. */
  import type { ProfileDraft } from '../../bridge';
  import RegistrarPreview from '../../ui/RegistrarPreview.svelte';
  import Signature from './Signature.svelte';

  let { d = $bindable() }: { d: ProfileDraft } = $props();
</script>

<div class="fcol sigstep">
  <Signature bind:d />
  <p class="line">This is how it goes on each invoice. The layout on a registrar's is theirs; the fund house and the figures here are examples.</p>
  {#if d.signature.way === 'image' && d.signature.image}
    <div class="sigprevs">
      <RegistrarPreview kind="cams" name={d.name} gstin={d.gstin} arn={d.arn} signature={d.signature} />
      {#if d.kfintech.used}<RegistrarPreview kind="kfintech" name={d.name} gstin={d.gstin} arn={d.arn} signature={d.signature} />{/if}
    </div>
  {/if}
</div>

<style>
  .sigstep { container-type: inline-size; }
  .sigprevs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px; align-items: start; }
  @container (max-width: 720px) { .sigprevs { grid-template-columns: minmax(0, 1fr); } }
  .sigprevs :global(.invprev) { flex: none; position: static; min-width: 0; }
  .sigprevs :global(.invprev img) { width: 100%; }
  .sigprevs :global(.invprev-wait) { width: 100%; height: auto; aspect-ratio: 400 / 518; }
</style>
