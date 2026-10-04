<script lang="ts">
  /* Your check: every invoice the registrars do not have yet, with the registrar's own figures, to be compared with
     the person's bank statement. Anything that does not match is unticked and left out: it stays open, and starts
     unticked next time. Nothing is editable, on purpose: the portal checks against the registrar's own records to the
     paisa, so a "corrected" invoice would only be rejected. The only decision is in or out, and this is the one yes:
     what stays ticked is prepared, checked by the registrar and submitted, with nothing asked again.
     On the person's own invoices each row shows its number, re-flowing as they untick. A row the run cannot send
     says why and cannot be ticked. */
  import { untrack } from 'svelte';
  import type { Ask, Registrar } from '../../bridge';
  import { canSubmit, groups, included, initialTicks, numbersFor, rowTotal, sums, toggle } from '../../logic/check';
  import { n2, regName } from '../../logic/format';
  import { store } from '../../state/store.svelte';
  import MiniInvoice from '../../ui/MiniInvoice.svelte';

  let { ask, registrars, month, onnotnow }: {
    ask: Extract<Ask, { type: 'your_check' }>; registrars: Registrar[]; month: string; onnotnow: () => void;
  } = $props();

  // keyed on the question's id by the run window, so these are the rows for the life of this screen
  const rows = untrack(() => ask.rows);
  let ticked = $state(initialTicks(rows));
  let agreed = $state(false);
  let sel = $state(rows[0]);

  const s = $derived(sums(rows, ticked));
  const numbers = $derived(numbersFor(rows, ticked));
  const who = $derived([...new Set(rows.map(r => r.registrar))].map(regName).join(' and '));
  const one = $derived(registrars.length === 1 ? regName(registrars[0]) : '');
  const own = $derived(store.snap?.profile?.invoices.source === 'own');
  const cols = $derived(own ? 6 : 5);

  function flip(x: (typeof rows)[number]) { ticked = toggle(ticked, x); agreed = false; }
  function submit() {
    if (!canSubmit(s, agreed)) return;
    store.answerRun({ type: 'your_check', confirmed: true, included: included(rows, ticked) });
  }
</script>

<div class="rm-stage">
  <div class="work-hd"><div><h3>Check {month}{one ? ` on ${one}` : ''} against your bank statement</h3>
    <div class="sub">These are {who}'s own figures, the ones the portals check. Untick anything that doesn't match what reached your bank: it stays open, for you to raise with the registrar.</div></div></div>
  {#each ask.notes as n (n)}<p class="line">{n}</p>{/each}
  <div class="chk-grid">
    <div class="tblwrap"><table class="tbl">
      <thead><tr><th><span class="visually-hidden">Include</span></th><th>Fund house</th>{#if own}<th>Your number</th>{/if}<th class="num">Taxable</th><th class="num">GST</th><th class="num">Total</th></tr></thead>
      <tbody>
        {#each groups(rows) as g (g.registrar)}
          <tr class="grp"><td colspan={cols}>{regName(g.registrar)} · {g.rows.length}</td></tr>
          {#each g.rows as x (x.key)}
            <tr data-i class:sel={x === sel} class:out={!ticked.has(x.key)} onclick={e => { if (!(e.target as HTMLElement).closest('.cb')) sel = x; }}>
              <td class="cb"><label class="check"><input type="checkbox" checked={ticked.has(x.key)} disabled={!!x.blocked} aria-label="Include {x.amc}" onchange={() => flip(x)} /></label></td>
              <td>{x.amc}{#if x.blocked}<span class="rowsay">{x.blocked}</span>{:else if x.rejection}<span class="rowsay bad">Rejected before: “{x.rejection}”</span>{/if}</td>{#if own}<td class="mono">{numbers[x.key] ?? ''}</td>{/if}<td class="num">{n2(x.taxable)}</td><td class="num">{n2(x.gst)}</td><td class="num">{n2(rowTotal(x))}</td></tr>
          {/each}
        {/each}
      </tbody>
      <tfoot><tr><td></td><td colspan={own ? 2 : 1}>{s.count} {s.count === 1 ? 'invoice' : 'invoices'}</td><td class="num">{n2(s.taxable)}</td><td class="num">{n2(s.gst)}</td><td class="num">{n2(s.total)}</td></tr></tfoot>
    </table></div>
    <div class="chk-prev"><div class="label">{sel.amc}</div>
      <!-- the person's own invoice is drawn after this check, with the number it ends up with -->
      <MiniInvoice key={own ? '' : sel.key} amc={sel.amc} number={numbers[sel.key] ?? ''} taxable={sel.taxable} gst={sel.gst} igst={sel.igst} total={rowTotal(sel)} /></div>
  </div>
  {#if rows.some(r => r.registrar === 'KFINTECH')}<p class="fine">KFintech's three declarations are ticked in your name.</p>{/if}
</div>
<div class="rm-foot">
  <button class="btn ghost" onclick={onnotnow}>Not now</button>
  <label class="check" style="margin-left:auto"><input type="checkbox" bind:checked={agreed} /> These {s.count} match my bank statement</label>
  <button class="btn primary" data-primary disabled={!canSubmit(s, agreed)} onclick={submit}>Submit {s.count} {s.count === 1 ? 'invoice' : 'invoices'}</button>
</div>
