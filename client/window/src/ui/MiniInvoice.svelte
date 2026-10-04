<script lang="ts">
  /* A small drawing of one invoice with the signature stamped on it, for Your check and the invoice popup.
     When the app can show the signed PDF itself (`preview`), that is shown instead. */
  import { app } from '../bridge';
  import { n2 } from '../logic/format';
  import { store } from '../state/store.svelte';

  /* `drawn`: the number the signed PDF was drawn with. At Your check the number can move as the person unticks, and
     the PDF is only redrawn after Submit, so a PDF printing another number than the one that will be used is not
     shown: the drawing below, with the number that will be used, is. */
  let { key, amc, number, taxable, gst, igst = false, total, drawn }: {
    key: string; amc: string; number: string; taxable: number; gst: number; igst?: boolean; total: number; drawn?: string;
  } = $props();

  let pdf = $state('');
  $effect(() => { const k = key; pdf = ''; app.preview(k).then(u => { if (k === key) pdf = u; }); });

  const p = $derived(store.snap?.profile);
  const month = $derived(store.snap?.month?.kfLabel ?? '');
</script>

{#if pdf && (drawn ?? number) === number}
  <img class="page small full" src={pdf} alt="The signed invoice" />
{:else}
  <div class="page small full" aria-label="The signed invoice">
    <div class="pt-title">Tax Invoice</div>
    <div class="ph"><div><b>{p?.name}</b><span>GSTIN {p?.gstin}</span></div><div class="no"><span>Invoice No.</span><b class="mono">{number}</b></div></div>
    <div class="buyer"><span>Buyer (Bill to)</span><b>{amc}</b></div>
    <div class="items">
      <div><span>Commission for {month}</span><span></span><b>{n2(taxable)}</b></div>
      <div class="tx"><span>{igst ? 'IGST 18%' : 'CGST 9% · SGST 9%'}</span><span></span><b>{n2(gst)}</b></div>
      <div class="tot"><span>Total</span><span></span><b>₹{n2(total)}</b></div>
    </div>
    <div class="pf2"><span></span><div class="sigspot">
      {#if p?.signature.present}<img class="sigimg" src={p.signature.image} alt="" />{/if}
      <span>for {p?.name}<br />Authorised signatory</span></div></div>
  </div>
{/if}
