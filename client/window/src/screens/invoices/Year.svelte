<script lang="ts">
  /* Invoices opens on the financial year's months (#17): count, total, status. A month opens on click. */
  import { inr } from '../../logic/format';
  import { store } from '../../state/store.svelte';
  import { ui } from '../../state/ui.svelte';
  import { icons } from '../../ui/icons';

  const s = $derived(store.snap!);
  const rows = $derived(s.year);
  const total = $derived(rows.reduce((a, r) => a + r.total, 0));
  const count = $derived(rows.reduce((a, r) => a + r.count, 0));
  const chip = (r: (typeof rows)[number]) =>
    r.status === 'Rejected' ? ['bad', `${r.rejected} rejected`] : r.status === 'Approved' ? ['good', 'Approved']
      : r.status === 'Submitted' ? ['wait', 'Waiting approval'] : ['neutral', 'Not submitted'];
  const openMonth = (p: string) => { ui.invoicesMonth = p; };
</script>

<div class="page-in fit enter">
  <div class="mhd"><div><h1>Invoices</h1><p class="sub">Financial year {s.fy}{rows.length ? ` · ${rows.at(-1)!.label.split(' ')[0]} to ${rows[0].label.split(' ')[0]}` : ''}</p></div>
    <div class="stepper"><button aria-label="Earlier year" disabled>{@html icons.prev}</button><span class="val">FY {s.fy}</span><button aria-label="Later year" disabled>{@html icons.next}</button></div></div>

  {#if !rows.length}
    <div class="empty-state"><b>Nothing here yet.</b>Your first run reads what CAMS and KFintech already have.</div>
  {:else}
    <div class="tblwrap"><table class="tbl months">
      <thead><tr><th>Month</th><th>Invoices</th><th class="num">Total</th><th>Status</th><th><span class="visually-hidden">Open</span></th></tr></thead>
      <tbody>
        {#each rows as r (r.period)}
          {@const c = chip(r)}
          <tr tabindex="0" onclick={() => openMonth(r.period)} onkeydown={e => { if (e.key === 'Enter') { e.stopPropagation(); openMonth(r.period); } }}>
            <td><b>{r.label}</b></td><td>{r.count} invoices</td><td class="num">{inr(r.total)}</td>
            <td><span class="chip {c[0]}">{c[1]}</span></td><td class="chev">{@html icons.chev}</td></tr>
        {/each}
      </tbody>
      <tfoot><tr><td>{rows.length} months</td><td>{count} invoices</td><td class="num">{inr(total)}</td><td colspan="2"></td></tr></tfoot>
    </table></div>
  {/if}
</div>
