<script lang="ts">
  /* One month's invoices: filters by registrar and status (with counts), search, a table sortable by any column
     whose totals row follows the filters. A row opens the invoice as a popup (#18). */
  import { app, type Invoice, type Month, type Status } from '../../bridge';
  import { registrarsOf } from '../../logic/details';
  import { checkedLine, n2, regName, regTag } from '../../logic/format';
  import { blankQuery, chipTone, gst, statusesIn, table, total, type SortKey } from '../../logic/month';
  import { runOffOf } from '../../logic/runoff';
  import { store } from '../../state/store.svelte';
  import { ui } from '../../state/ui.svelte';
  import { icons } from '../../ui/icons';

  let { period }: { period: string } = $props();

  let month = $state<Month | null>(null);
  let q = $state(blankQuery());

  // the month is read from the local store, which answers at once; this month follows the snapshot as it changes
  $effect(() => {
    const snapMonth = store.snap?.month;                 // also read again whenever a run has changed what is on disk
    if (snapMonth && snapMonth.period === period) { month = snapMonth; return; }
    app.month(period).then(m => { if (m.period === period) month = m; });
  });

  const rows = $derived(month?.invoices ?? []);
  const list = $derived(table(rows, q));
  const statuses = $derived(statusesIn(rows));
  const count = (k: 'registrar' | 'status', v: string) => rows.filter(x => x[k] === v).length;
  const sumOf = (xs: Invoice[], f: (x: Invoice) => number) => xs.reduce((a, x) => a + f(x), 0);

  function sortBy(k: SortKey) { q = { ...q, dir: q.sort === k ? (q.dir === 1 ? -1 : 1) : 1, sort: k }; }
  function open(x: Invoice) { ui.open({ type: 'invoice', invoice: x, period }); }
  // a status read less than ten minutes ago is shown again, not read again: the run does that, as from Overview
  const runOff = $derived(!!store.snap && runOffOf(store.snap));    // off exactly when Overview's Run and Check now are
  function check() {
    const p = store.snap?.profile;
    if (!p || runOff) return;
    ui.runWith = { registrars: registrarsOf(p), period, what: 'check' };
  }
  async function exportIt() {
    const r = await app.exportMonth(period);
    store.toast(r.ok ? 'Exported' : r.said);
  }
  // nothing is here, and the last look found why: the registrars have not listed the month yet
  const unlisted = $derived(month && !month.listed && month.notListed.length
    ? `${month.notListed.map(regName).join(' and ')} ${month.notListed.length === 1 ? "hasn't" : "haven't"} listed ${month.label.split(' ')[0]}'s invoices yet.`
    : '');
  const th = (k: SortKey) => (q.sort === k ? (q.dir > 0 ? ' ↑' : ' ↓') : '');
  const aria = (k: SortKey) => (q.sort === k ? (q.dir > 0 ? 'ascending' : 'descending') : 'none');
</script>

{#snippet head(k: SortKey, label: string, num = false)}
  <th class="sort" class:num class:on={q.sort === k} tabindex="0" aria-sort={aria(k)} onclick={() => sortBy(k)}
    onkeydown={e => { if (e.key === 'Enter') { e.stopPropagation(); sortBy(k); } }}>{label}{th(k)}</th>
{/snippet}

<div class="page-in fit invpage enter">
  <div class="mhd">
    <div class="tl"><button class="icon-btn back" data-tip="All months" aria-label="All months" onclick={() => { ui.invoicesMonth = null; }}>{@html icons.back}</button>
      <div><h1>{month?.label ?? ''}</h1><p class="sub">{rows.length} invoices · ₹{n2(sumOf(rows, total))}</p></div></div>
    <div class="hdr-r">
      <span class="chkd">{checkedLine(month?.checkedAt ?? '', store.snap?.today ?? '')}</span>
      <button class="btn ghost" disabled={runOff} onclick={check}>{@html icons.sync}Check status</button>
      <button class="btn secondary" onclick={exportIt}>{@html icons.dl}Export</button>
      {#if rows.length}<button class="btn secondary" onclick={() => { ui.booksMonth = period; ui.go('books'); }}>{@html icons.book}Import into your books</button>{/if}
    </div>
  </div>

  <div class="filters">
    <div class="seg" role="group" aria-label="Registrar">
      {#each ['All', 'CAMS', 'KFINTECH'] as const as r (r)}
        <button class:on={q.registrar === r} aria-pressed={q.registrar === r} onclick={() => (q = { ...q, registrar: r })}>
          {r === 'KFINTECH' ? 'KFintech' : r} <span class="n">{r === 'All' ? rows.length : count('registrar', r)}</span></button>
      {/each}
    </div>
    {#if statuses.length > 1}
      <div class="seg" role="group" aria-label="Status">
        <button class:on={q.status === 'All'} aria-pressed={q.status === 'All'} onclick={() => (q = { ...q, status: 'All' })}>Any status</button>
        {#each statuses as st (st)}
          <button class:on={q.status === st} aria-pressed={q.status === st} onclick={() => (q = { ...q, status: st as Status })}>
            {st.replace(' approval', '')} <span class="n">{count('status', st)}</span></button>
        {/each}
      </div>
    {/if}
    <input class="input search" placeholder="Search fund house or invoice" aria-label="Search" bind:value={q.q} data-own-enter />
  </div>

  <div class="invbody">
    <div class="tblwrap scroll"><table class="tbl">
      <thead><tr>{@render head('amc', 'Fund house')}{@render head('number', 'Invoice')}{@render head('taxable', 'Taxable', true)}{@render head('gst', 'GST', true)}{@render head('total', 'Total', true)}{@render head('status', 'Status')}</tr></thead>
      <tbody>
        {#each list as x (x.key)}
          <tr data-i tabindex="0" onclick={() => open(x)} onkeydown={e => { if (e.key === 'Enter') { e.stopPropagation(); open(x); } }}>
            <td>{x.amc} <span class="reg">{regTag(x.registrar)}</span></td><td class="mono">{x.number}</td>
            <td class="num">{n2(x.taxable)}</td><td class="num">{n2(gst(x))}</td><td class="num">{n2(total(x))}</td>
            <td><span class="chip {chipTone(x.status)}" title={x.said ? `${x.registrar === 'CAMS' ? 'CAMS' : 'KFintech'}: ${x.said}` : undefined}>{x.status}</span></td></tr>
        {:else}
          <tr><td colspan="6" class="empty">{rows.length ? 'No invoices match.' : unlisted || 'Nothing fetched for this month yet.'}</td></tr>
        {/each}
      </tbody>
      <tfoot><tr><td colspan="2">{list.length} of {rows.length}</td><td class="num">{n2(sumOf(list, x => x.taxable))}</td><td class="num">{n2(sumOf(list, gst))}</td><td class="num">{n2(sumOf(list, total))}</td><td></td></tr></tfoot>
    </table></div>
  </div>
</div>
