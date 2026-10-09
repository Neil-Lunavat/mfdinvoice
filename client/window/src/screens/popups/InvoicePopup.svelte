<script lang="ts">
  /* One invoice, as a popup (#18): the invoice itself on the left; details, timeline and actions on the right.
     A rejection shows the registrar's words and "Send to support"; we never guess why.
     There is no per-invoice fix and no single-invoice upload: rejections are sent again together, by Overview's Run,
     in one run and one sign-in. */
  import { app, type Invoice } from '../../bridge';
  import { dayMon, dayMonYear, inr, n2, regName } from '../../logic/format';
  import { gst, total } from '../../logic/month';
  import { store } from '../../state/store.svelte';
  import { ui } from '../../state/ui.svelte';
  import { icons } from '../../ui/icons';
  import MiniInvoice from '../../ui/MiniInvoice.svelte';
  import Modal from '../../ui/Modal.svelte';

  let { invoice, period }: { invoice: Invoice; period: string } = $props();

  // the store may have moved on since the popup opened (an approval, a rejection): show the latest
  const x = $derived(store.snap?.month?.period === period ? store.snap.month.invoices.find(i => i.key === invoice.key) ?? invoice : invoice);
  const reg = $derived(regName(x.registrar));
  const last = $derived(x.timeline.at(-1));

  async function copy(text: string) {
    try { await navigator.clipboard.writeText(text); } catch { /* the toast still says what happened */ }
    store.toast('Copied');
  }
  const tick = (what: string) => (what === 'Rejected' ? 'no' : what === 'Waiting approval' ? 'wt' : '');
</script>

<Modal wide label="{x.amc} invoice" onclose={() => ui.close()}>
  <div class="ip-grid">
    <div class="ip-prev"><MiniInvoice key={x.key} /></div>
    <aside class="drawer in-pop">
      <div class="d-hd"><div><div class="d-s">{x.amc} · <span class="mono">{x.number}</span></div><div class="d-big">{inr(total(x))}</div></div>
        <button class="icon-btn" aria-label="Close" onclick={() => ui.close()}>{@html icons.close}</button></div>
      {#if x.status === 'Rejected'}
        <div class="banner bad sm" role="alert"><div>{reg} says: “{x.rejection}”
          <div style="margin-top:4px"><a href="#support" style="color:inherit;text-decoration:underline"
            onclick={e => { e.preventDefault(); ui.open({ type: 'support', where: `Invoice ${x.number}, rejected by ${reg}` }); }}>Not sure what to do? Send to support</a></div></div></div>
      {/if}
      <div class="kv">
        <span>Taxable</span><b>{n2(x.taxable)}</b>
        <span>{x.igst ? 'IGST 18%' : 'CGST 9% + SGST 9%'}</span><b>{n2(gst(x))}</b>
        <span>Total</span><b>{n2(total(x))}</b>
        <span>Invoice date</span><b>{dayMonYear(x.date)}</b>
        <span>{reg} reference</span><b class="mono ref">{x.key}<button class="icon-btn xs" aria-label="Copy the reference" onclick={() => copy(x.key)}>{@html icons.copy}</button></b>
      </div>
      {#if x.timeline.length}
        <div class="label">Timeline</div>
        <div class="pf">
          {#each x.timeline as t, i (i)}
            {@const own = t === last && !!x.words}
            {@const k = own ? 'wt' : t === last ? tick(t.what) : ''}
            <div class="row"><span class="tick {k}">{#if k === 'no'}!{:else if k === 'wt'}·{:else}{@html icons.tickSm}{/if}</span>
              <span title={t === last && x.said ? `${reg}: ${x.said}` : undefined}>{own ? x.words : t.what}</span>
              <span class="v">{t.when ? dayMon(t.when) : ''}{t.who ? ` · ${t.who}` : ''}</span></div>
          {/each}
        </div>
      {:else}
        <p class="line">Not submitted yet. Run {store.snap?.month?.label.split(' ')[0] ?? 'the month'} to submit it.</p>
      {/if}
      <div class="d-act">
        <button class="btn secondary sm" data-primary onclick={() => app.openPdf(x.key)}>Open PDF</button>
        <button class="btn ghost sm" onclick={() => app.showInFolder(x.key)}>Show in folder</button>
        <button class="btn ghost sm" onclick={() => copy(x.number)}>Copy invoice number</button>
      </div>
    </aside>
  </div>
</Modal>
