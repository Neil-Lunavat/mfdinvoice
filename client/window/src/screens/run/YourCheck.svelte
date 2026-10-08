<script lang="ts">
  /* Your check: every invoice the registrars do not have yet, with the registrar's own figures, to be compared with
     the person's bank statement. Anything that does not match is unticked and left out: it stays open, and starts
     unticked next time. Nothing is editable, on purpose: the portal checks against the registrar's own records to the
     paisa, so a "corrected" invoice would only be rejected. The only decision is in or out, and this is the one yes:
     what stays ticked is prepared, checked by the registrar and submitted, with nothing asked again.
     On the person's own invoices each row shows its number, re-flowing as they untick. A row the run cannot send
     says why and cannot be ticked.
     With books connected (Tally) the books give the invoice numbers after this check, so there is no number column;
     the row says when the invoice is in Tally already; a new financial year asks for its first invoice number; and an
     invoice Tally would renumber the ones after for is put aside, or dated the day it is sent: the person chooses. */
  import { untrack } from 'svelte';
  import type { Ask, Registrar } from '../../bridge';
  import { afterLine, booksName, ASIDE, CANT_GO, firstLabel, TODAY, whyRenumber } from '../../logic/books';
  import { canSubmit, groups, included, initialTicks, numbersFor, rowTotal, sums, toggle } from '../../logic/check';
  import { n2, regName } from '../../logic/format';
  import { rule46 } from '../../logic/numbering';
  import { store } from '../../state/store.svelte';

  let { ask, registrars, month, onnotnow }: {
    ask: Extract<Ask, { type: 'your_check' }>; registrars: Registrar[]; month: string; onnotnow: () => void;
  } = $props();

  // keyed on the question's id by the run window, so these are the rows for the life of this screen
  const rows = untrack(() => ask.rows);
  let ticked = $state(initialTicks(rows));
  let agreed = $state(false);
  const books = untrack(() => ask.books ?? null);
  let dated = $state(new Set<string>());                    // the invoices to date the day they are sent
  let why = $state(new Set<string>());                      // the rows whose "Why?" is open
  let first = $state(untrack(() => ask.books?.first?.proposed ?? ''));

  const s = $derived(sums(rows, ticked));
  const numbers = $derived(numbersFor(rows, ticked));
  const who = $derived([...new Set(rows.map(r => r.registrar))].map(regName).join(' and '));
  const one = $derived(registrars.length === 1 ? regName(registrars[0]) : '');
  const own = $derived(store.snap?.profile?.invoices.source === 'own');
  const numbered = $derived(own && !books);                 // without books the number is shown here
  const cols = $derived(numbered ? 6 : 5);
  // a new financial year with nothing in Tally yet: the first invoice number is needed when any ticked invoice goes in new
  const needsFirst = $derived(!!books?.first && rows.some(r => ticked.has(r.key) && !r.note && !r.blocked));
  const firstWhy = $derived(needsFirst ? (!first.trim() ? 'Type the first invoice number.' : rule46(first)) : '');

  function flip(x: (typeof rows)[number]) { if (x.renumber) return; ticked = toggle(ticked, x); agreed = false; }
  function choose(x: (typeof rows)[number], today: boolean) {
    const t = new Set(ticked), d = new Set(dated);
    if (today) { t.add(x.key); d.add(x.key); } else { t.delete(x.key); d.delete(x.key); }
    ticked = t; dated = d; agreed = false;
  }
  function toggleWhy(key: string) { const w = new Set(why); if (w.has(key)) w.delete(key); else w.add(key); why = w; }
  function submit() {
    if (!canSubmit(s, agreed) || firstWhy) return;
    store.answerRun({ type: 'your_check', confirmed: true, included: included(rows, ticked),
      ...(needsFirst ? { first: first.trim() } : {}), dated: [...dated].filter(k => ticked.has(k)) });
  }
</script>

<div class="rm-stage">
  <div class="work-hd"><div><h3>Check {month}{one ? ` on ${one}` : ''} against your bank statement</h3>
    <div class="sub">These are {who}'s own figures, the ones the portals check. Untick anything that doesn't match what reached your bank: it stays open, for you to raise with the registrar.</div></div></div>
  {#each ask.notes as n (n)}<p class="line">{n}</p>{/each}
  {#if books}
    <p class="line">Once you submit, the ticked invoices go into {booksName(books.kind)}{books.company ? ` (${books.company})` : ''} first, where each gets its invoice number; then they are signed and sent.</p>
    {#if books.creates?.length}<p class="line">New in {booksName(books.kind)}: {books.creates.map(c => c.name).join(', ')}.</p>{/if}
  {/if}
  {#if books?.after}<p class="line">{afterLine(books.after)}</p>{/if}
  {#if books?.first}
    <div class="field"><label for="firstno">{firstLabel(books.first.fy)}</label>
      <input id="firstno" class="input mono" style="max-width:240px" bind:value={first} />
      {#if firstWhy && first.trim()}<span class="err" role="alert">{firstWhy}</span>{/if}</div>
  {/if}
  <div>
    <div class="tblwrap"><table class="tbl">
      <thead><tr><th><span class="visually-hidden">Include</span></th><th>Fund house</th>{#if numbered}<th>Your number</th>{/if}<th class="num">Taxable</th><th class="num">GST</th><th class="num">Total</th></tr></thead>
      <tbody>
        {#each groups(rows) as g (g.registrar)}
          <tr class="grp"><td colspan={cols}>{regName(g.registrar)} · {g.rows.length}</td></tr>
          {#each g.rows as x (x.key)}
            <tr class:out={!ticked.has(x.key)}>
              <td class="cb"><label class="check"><input type="checkbox" checked={ticked.has(x.key)} disabled={!!x.blocked || !!x.renumber} aria-label="Include {x.amc}" onchange={() => flip(x)} /></label></td>
              <td class="fh"><span class="amc">{x.amc}</span>{#if x.blocked}<span class="rowsay bad">{x.blocked}</span>{:else if x.rejection}<span class="rowsay bad">Rejected before: “{x.rejection}”</span>{/if}
                {#if x.note}<span class="rowsay">{x.note}</span>{/if}
                {#if x.renumber}
                  <span class="rowsay">{CANT_GO} <a href="#why" onclick={e => { e.preventDefault(); toggleWhy(x.key); }}>Why?</a></span>
                  <span class="seg" role="radiogroup" aria-label="What to do with {x.amc}'s invoice" style="margin-top:6px">
                    <button type="button" role="radio" aria-checked={!dated.has(x.key)} class:on={!dated.has(x.key)} onclick={() => choose(x, false)}>{ASIDE}</button>
                    <button type="button" role="radio" aria-checked={dated.has(x.key)} class:on={dated.has(x.key)} onclick={() => choose(x, true)}>{TODAY}</button></span>
                  {#if why.has(x.key)}<span class="rowsay">{whyRenumber(x.renumber.date)}</span>{/if}
                {/if}</td>{#if numbered}<td class="mono">{numbers[x.key] ?? ''}</td>{/if}<td class="num">{n2(x.taxable)}</td><td class="num">{n2(x.gst)}</td><td class="num">{n2(rowTotal(x))}</td></tr>
          {/each}
        {/each}
      </tbody>
      <tfoot><tr><td></td><td colspan={numbered ? 2 : 1}>{s.count} {s.count === 1 ? 'invoice' : 'invoices'}</td><td class="num">{n2(s.taxable)}</td><td class="num">{n2(s.gst)}</td><td class="num">{n2(s.total)}</td></tr></tfoot>
    </table></div>
  </div>
  {#if rows.some(r => r.registrar === 'KFINTECH')}<p class="fine">KFintech's three declarations are ticked in your name.</p>{/if}
</div>
<div class="rm-foot">
  <button class="btn ghost" onclick={onnotnow}>Cancel</button>
  <label class="check" style="margin-left:auto"><input type="checkbox" bind:checked={agreed} /> These {s.count} match my bank statement</label>
  <button class="btn primary" data-primary disabled={!canSubmit(s, agreed) || !!firstWhy} onclick={submit}>Submit {s.count} {s.count === 1 ? 'invoice' : 'invoices'}</button>
</div>
