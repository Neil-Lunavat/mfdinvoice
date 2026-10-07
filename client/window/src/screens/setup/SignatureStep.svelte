<script lang="ts">
  /* Signature: the photo (or token), seen on the real thing. Where the invoice comes from is asked in Your invoices. */
  import type { ProfileDraft } from '../../bridge';
  import RegistrarPreview from '../../ui/RegistrarPreview.svelte';
  import Signature from './Signature.svelte';

  let { d = $bindable() }: { d: ProfileDraft } = $props();
</script>

<div class="row2 top">
  <div class="fcol">
    <Signature bind:d />
    <p class="line">This is how it goes on each invoice. The layout on a registrar's is theirs; the fund house and the figures here are examples.</p>
  </div>
  {#if d.signature.way === 'image' && d.signature.image}
    <div class="regprev">
      <RegistrarPreview kind="cams" name={d.name} gstin={d.gstin} arn={d.arn} signature={d.signature} />
      {#if d.kfintech.used}<RegistrarPreview kind="kfintech" name={d.name} gstin={d.gstin} arn={d.arn} signature={d.signature} />{/if}
    </div>
  {/if}
</div>
