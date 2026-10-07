<script lang="ts">
  /* Tally: a month's invoices into the person's books, in the TallyPrime open on this PC. The look says what will
     happen to each invoice before anything is written, and one yes puts them in. Nothing here can be undone (an
     invoice deleted in Tally leaves a gap in its numbers for good), so the look is the check. */
  import { onMount } from 'svelte';
  import { app, type TallyLook, type TallyRow } from '../bridge';
  import { n2, regTag } from '../logic/format';
  import { store } from '../state/store.svelte';
  import { ui } from '../state/ui.svelte';
  import { icons } from '../ui/icons';

  const s = $derived(store.snap!);
  // the months that have invoices on this PC, newest first
  const months = $derived(s.year.filter(m => m.count > 0));
  let period = $state('');
  let look = $state<TallyLook | null>(null);
  let busy = $state<'' | 'look' | 'import'>('');
  let which = $state<'submitted' | 'all'>('submitted');
  let company = $state('');
  let last = $state('');
  let answers = $state<Record<string, string>>({});
  let adopt = $state<Record<string, boolean>>({});
  let checked = $state(false);                      // the person's yes to what is listed, asked again after every look

  const rows = $derived(look?.state === 'ready' ? look.rows : []);
  const going = $derived(rows.filter(r => r.action === 'import'));
  const adopting = $derived(rows.filter(r => r.action === 'by_hand' && adopt[r.key]));
  const waiting = $derived((look?.asks?.length ?? 0) > 0);
  const needsLast = $derived(!!look?.askLast && !last.trim());
  const count = $derived(going.length + adopting.length);
  const done = $derived(look?.done ?? null);
  // the sales ledger asked per fund house: one card, with one choice for all of them
  const salesAsks = $derived((look?.asks ?? []).filter(a => a.id.startsWith('sales:')));
  const otherAsks = $derived((look?.asks ?? []).filter(a => !a.id.startsWith('sales:')));
  const salesOptions = $derived([...new Set(salesAsks.flatMap(a => a.options))]);
  const amcOf = (q: string) => q.match(/does (.+?)'s commission/)?.[1] ?? q;
  const parties = $derived((look?.creates ?? []).filter(c => c.kind === 'party').map(c => c.name));
  const taxes = $derived((look?.creates ?? []).filter(c => c.kind !== 'party').map(c => c.name));

  async function read(keep = false) {
    if (busy || !period) return;
    busy = 'look';
    const was = keep ? look?.done : undefined;
    checked = false;
    const r = await app.tallyLook({ period, company, which, last: last.trim(), answers: $state.snapshot(answers) });
    look = was ? { ...r, done: was } : r;
    if (r.state === 'ready') {
      company = r.company;
      if (r.askLast && !last) last = r.last;
    }
    busy = '';
  }
  function pick(p: string) { period = p; ui.tallyMonth = p; adopt = {}; look = null; void read(); }
  function choose(c: string) { company = c; answers = {}; adopt = {}; void read(); }
  function only(w: 'submitted' | 'all') { if (which === w) return; which = w; void read(); }
  function answer(id: string, v: string) { if (!v) return; answers = { ...answers, [id]: v }; void read(); }
  function answerAll(v: string) {
    if (!v) return;
    answers = { ...answers, ...Object.fromEntries(salesAsks.filter(a => a.options.includes(v)).map(a => [a.id, v])) };
    void read();
  }

  async function bringIn() {
    if (busy || !count || waiting || needsLast || !checked || look?.state !== 'ready') return;
    busy = 'import';
    look = await app.tallyImport({ period, company, which, last: last.trim(), answers: $state.snapshot(answers),
      adopt: adopting.map(r => r.key) });
    adopt = {};
    checked = false;
    busy = '';
    const d = look.done;
    const went = (d?.imported.length ?? 0) + (d?.adopted.length ?? 0);
    store.toast(went ? `${went} ${went === 1 ? 'invoice is' : 'invoices are'} in Tally` : look.said || 'Nothing went in.');
  }

  onMount(() => {
    period = (ui.tallyMonth && months.some(m => m.period === ui.tallyMonth) ? ui.tallyMonth : months[0]?.period) ?? s.month!.period;
    void read();
  });

  const CHIP: Record<TallyRow['action'], [string, string]> = {
    import: ['neutral', 'Will go in'], in_books: ['good', 'In your books'], by_hand: ['wait', 'Typed by hand?'],
    ask: ['wait', 'Needs your answer'], stop: ['bad', "Can't go in"], later: ['neutral', 'Not submitted'],
    run: ['neutral', 'Goes in at its run'], past: ['neutral', 'Already sent']
  };
  const numberOf = (r: TallyRow) => r.number || (r.action === 'import' ? r.will : '');
  const span = (xs: string[]) => (xs.length > 1 ? `${xs[0]} to ${xs.at(-1)}` : xs[0] ?? '');
</script>

<div class="page-in fit tlpage enter">
  <div class="mhd">
    <div><h1>Tally</h1>
      <p class="sub">{#if look?.state === 'ready'}{look.company}{look.last ? ` · last invoice ${look.last}` : ''} · {look.tallyNumbers ? 'Tally numbers the invoices' : 'your numbers are kept'}{:else}Each month's invoices into your books, in the TallyPrime open on this PC.{/if}</p></div>
    <div class="hdr-r">
      {#if months.length}
        <select class="input" style="width:auto" aria-label="Month" value={period} onchange={e => pick(e.currentTarget.value)}>
          {#each months as m (m.period)}<option value={m.period}>{m.label}</option>{/each}
        </select>
      {/if}
      <button class="btn ghost" disabled={!!busy} onclick={() => read()}>{#if busy === 'look'}<span class="spin"></span>{:else}{@html icons.sync}{/if}Refresh</button>
    </div>
  </div>

  {#if !months.length}
    <div class="empty-state"><b>Nothing to import yet.</b>A month shows here once its invoices are on this PC: after a run, or Download invoices.</div>
  {:else if !look}
    <div class="empty-state"><span class="spin big"></span></div>
  {:else if look.state === 'off' || look.state === 'closed'}
    <div class="empty-state">
      <b>{look.state === 'closed' ? 'No company is open in TallyPrime.' : look.said || "TallyPrime isn't answering on this PC."}</b>
      {#if look.state === 'closed'}Open your company in TallyPrime, then press Refresh.
      {:else if !look.said}Open TallyPrime and your company, then press Refresh.
        <p class="line tl-help">The first time: in TallyPrime press F1 (Help) › Settings › Connectivity › Client/Server configuration. Set "TallyPrime acts as" to Both and the port to 9000, then close TallyPrime and open it again.</p>{/if}
    </div>
  {:else if look.state === 'pick'}
    <div class="empty-state"><b>Which company do these invoices go into?</b>
      {look.said || `${look.companies.length} companies are open in TallyPrime.`} It's remembered for this ARN.
      <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin-top:14px">
        {#each look.companies as c (c)}<button class="btn secondary" onclick={() => choose(c)}>{c}</button>{/each}
      </div></div>
  {:else}
    <div class="filters">
      <div class="seg" role="group" aria-label="Which invoices">
        <button class:on={which === 'submitted'} aria-pressed={which === 'submitted'} onclick={() => only('submitted')}>Submitted only <span class="n">{look.counts.submitted}</span></button>
        <button class:on={which === 'all'} aria-pressed={which === 'all'} onclick={() => only('all')}>All <span class="n">{look.counts.all}</span></button>
      </div>
      {#if look.askLast}
        <label class="tl-last">Your last invoice number in Tally
          <input class="input mono" style="width:150px" bind:value={last} onchange={() => read()} data-own-enter /></label>
      {/if}
      {#if look.companies.length > 1}
        <select class="input" style="width:auto;margin-left:auto" aria-label="Company" value={look.company} onchange={e => choose(e.currentTarget.value)}>
          {#each look.companies as c (c)}<option value={c}>{c}</option>{/each}
        </select>
      {/if}
    </div>

    <div class="tl-notes">
      {#if done}
        <div class="banner {done.refused.length || done.stoppedAt ? 'wait nospin' : 'info'}" role="status"><div>
          <b>{done.imported.length + done.adopted.length} in Tally{done.numbers.length ? `: ${span(done.numbers)}` : ''}{done.adopted.length ? ` · ${done.adopted.length} changed to the registrar's figures` : ''}</b>
          {#if done.stoppedAt}<p>{done.stoppedAt}</p>{/if}
          {#each done.refused as x (x.key)}<p>{x.amc}: {x.said}</p>{/each}
        </div></div>
      {/if}
      {#each look.warn as w (w)}<div class="banner wait sm"><div>{w}</div></div>{/each}
      {#if look.own}
        <div class="banner info sm"><div>Your own invoices go into Tally when you run them, and are numbered then. This page shows what is there.</div></div>
      {/if}
      {#if parties.length || taxes.length}
        <div class="banner info sm"><div>
          {#if parties.length}<b>{parties.length} new {parties.length === 1 ? 'ledger' : 'ledgers'} will be made in Tally</b>, under Sundry Debtors with {parties.length === 1 ? 'its' : 'their'} GSTIN: {parties.join(', ')}.{/if}
          {#if taxes.length}<p>{taxes.length === 1 ? 'A tax ledger' : 'Tax ledgers'} will be made too: {taxes.join(', ')}.</p>{/if}
        </div></div>
      {/if}
      {#if salesAsks.length}
        <div class="tl-ask">
          <div class="tl-ask-hd"><div><b>Which sales ledger does the commission go under?</b>
            <p>If a fund house needs a ledger of its own, make it in Tally first, then press Refresh.</p></div>
            {#if salesAsks.length > 1}
              <select class="input" aria-label="The same ledger for all" onchange={e => answerAll(e.currentTarget.value)}>
                <option value="">Same for all…</option>{#each salesOptions as o (o)}<option value={o}>{o}</option>{/each}
              </select>
            {/if}</div>
          <div class="tl-ask-grid">
            {#each salesAsks as a (a.id)}
              <label><span>{amcOf(a.question)}</span>
                <select class="input" aria-label={a.question} onchange={e => answer(a.id, e.currentTarget.value)}>
                  <option value="">Choose a ledger</option>{#each a.options as o (o)}<option value={o}>{o}</option>{/each}
                </select></label>
            {/each}
          </div>
        </div>
      {/if}
      {#each otherAsks as a (a.id)}
        {#if a.id === 'gstin'}
        <div class="banner wait sm" role="alert"><div><b>{a.question}</b>
          <p>Import waits for your answer.{look.companies.length > 1 ? ' Or choose another company at the top.' : ''}</p></div>
          <button class="btn secondary sm" onclick={() => answer('gstin', 'yes')}>This is the right company</button></div>
        {:else}
        <div class="banner wait sm"><div><b>{a.question}</b>
          {#if a.id.startsWith('sales:')}<p>If it needs a ledger of its own, make it in Tally first, then press Refresh.</p>{/if}</div>
          <select class="input" style="width:auto;max-width:300px" aria-label={a.question} onchange={e => answer(a.id, e.currentTarget.value)}>
            <option value="">{a.id === 'vtype' ? 'Choose one' : 'Choose a ledger'}</option>{#each a.options as o (o)}<option value={o}>{o}</option>{/each}
          </select></div>
        {/if}
      {/each}
    </div>

    <div>
      <div class="tblwrap"><table class="tbl">
        <thead><tr><th>Fund house</th><th>Invoice</th><th>Number in Tally</th><th class="num">Total</th><th>In Tally</th></tr></thead>
        <tbody>
          {#each rows as r (r.key)}
            {@const c = CHIP[r.action]}
            <tr class:dim={r.action === 'later'}>
              <td>{r.amc} <span class="reg">{regTag(r.registrar)}</span>{#if r.party && r.action !== 'later'}<div class="line">{r.partyNew ? 'New ledger: ' : ''}{r.party}{r.sales ? ` · ${r.sales}` : ''}</div>{/if}</td>
              <td class="mono">{r.key}</td>
              <td class="mono">{numberOf(r) || '—'}</td>
              <td class="num">{n2(r.total)}</td>
              <td><span class="chip {c[0]}">{c[1]}</span>
                {#if r.refused}<div class="line bad">{r.refused}</div>{:else if r.note && r.action !== 'in_books' && r.action !== 'later'}<div class="line">{r.note}</div>{/if}
                {#if r.action === 'by_hand'}
                  <label class="tl-adopt"><input type="checkbox" checked={!!adopt[r.key]} onchange={e => (adopt = { ...adopt, [r.key]: e.currentTarget.checked })} />
                    Change it to the registrar's figures, keeping {r.number || 'its number'}</label>{/if}
              </td></tr>
          {:else}
            <tr><td colspan="5" class="empty">Nothing is on this PC for {look.label} yet.</td></tr>
          {/each}
        </tbody>
        <tfoot><tr><td colspan="3">{look.counts.inBooks} of {rows.length} in your books</td><td class="num">{n2(rows.reduce((a, r) => a + r.total, 0))}</td><td></td></tr></tfoot>
      </table></div>
    </div>

    <div class="tl-foot">
      {#if waiting}<span class="line">Answer the {look.asks.length === 1 ? 'question' : 'questions'} above in order to import without errors.</span>
      {:else if count && !needsLast}
        <label class="tl-yes"><input type="checkbox" bind:checked />
          <span>I've checked these {count} {count === 1 ? 'invoice' : 'invoices'}{adopting.length ? `, ${adopting.length} of them to be changed` : ''}. Tally can't undo an import.</span></label>
      {:else}<span class="line">{look.counts.inBooks && look.counts.inBooks === rows.length ? `All of ${look.label} is in your books.` : count ? '' : 'Nothing to import.'}</span>{/if}
      <button class="btn primary" data-primary disabled={!!busy || !count || waiting || needsLast || !checked} onclick={bringIn}>
        {#if busy === 'import'}<span class="spin"></span>Importing{:else}Import {count || ''} into Tally{/if}</button>
    </div>
  {/if}
</div>

<style>
  .tl-notes { display: flex; flex-direction: column; gap: 8px; }
  .tl-notes > :global(:last-child) { margin-bottom: 10px; }
  .tl-notes .banner p { margin: 2px 0 0; }
  .tl-last { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--muted); }
  .tl-adopt { display: flex; align-items: center; gap: 6px; margin-top: 6px; font-size: 12.5px; color: var(--ink-2); }
  .tlpage { max-width: 1100px; }
  .tl-foot { display: flex; align-items: center; gap: 12px; padding: 12px 0; position: sticky; bottom: 0; background: var(--canvas); border-top: 1px solid var(--line-2); }
  .tl-yes { display: flex; align-items: center; gap: 8px; font-size: 13.5px; color: var(--ink); cursor: pointer; }
  .tl-yes input { width: 16px; height: 16px; }
  .tl-help { margin: 14px auto 0; max-width: 520px; text-align: center; }
  .tl-ask { border: 1px solid var(--line); border-radius: var(--r-card); background: var(--surface); padding: 14px 16px; }
  .tl-ask-hd { display: flex; align-items: flex-start; gap: 12px; }
  .tl-ask-hd p { margin: 2px 0 0; font-size: 12.5px; color: var(--muted); }
  .tl-ask-hd select { margin-left: auto; width: auto; }
  .tl-ask-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 8px 20px; margin-top: 12px; }
  .tl-ask-grid label { display: flex; align-items: center; gap: 10px; font-size: 13.5px; }
  .tl-ask-grid label span { flex: 1; min-width: 0; }
  .tl-ask-grid select { width: 170px; }
  .tl-foot .btn { margin-left: auto; }
  tr.dim td { opacity: .55; }
  .line.bad { color: var(--red); }
  td .line { white-space: normal; font-family: var(--sans, inherit); font-size: 12px; color: var(--muted); margin-top: 2px; }
</style>
