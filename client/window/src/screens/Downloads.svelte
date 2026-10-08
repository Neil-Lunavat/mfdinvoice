<script lang="ts">
  /* Downloads: any months' invoices onto this PC, with every figure, in one go; nothing is signed or submitted.
     Overview runs one month; this is where invoices come in by the batch (and, later, from other places too).
     One sign-in per portal for all of them; CAMS emails each month, and Skip CAMS in the run window goes on without
     waiting (each email is read when it comes, unless the mailbox is by hand). */
  import type { Registrar } from '../bridge';
  import { registrarsOf } from '../logic/details';
  import { inr, regName } from '../logic/format';
  import { store } from '../state/store.svelte';
  import { ui } from '../state/ui.svelte';
  import { icons } from '../ui/icons';

  const MON = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
  const NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const FIRST = 'APR-2026';                     // CAMS's and KFintech's GST invoices began with April 2026

  const s = $derived(store.snap!);
  const p = $derived(s.profile!);
  const index = (of: string) => { const [mon, yr] = of.split('-'); return Number(yr) * 12 + MON.indexOf(mon); };
  const at = (n: number) => `${MON[n % 12]}-${Math.floor(n / 12)}`;
  // April 2026 to this month, newest first
  const months = $derived(Array.from({ length: Math.max(1, index(s.month!.period) - index(FIRST) + 1) }, (_, i) => at(index(s.month!.period) - i)));
  const row = (of: string) => s.year.find(r => r.period === of);
  const nameOf = (of: string) => NAMES[MON.indexOf(of.split('-')[0])];

  let picked = $state<string[]>([]);
  let regs = $state<Registrar[]>([]);
  $effect(() => { if (!regs.length) regs = registrarsOf(p); });
  const all = $derived(picked.length === months.length);

  function toggle(of: string) { picked = picked.includes(of) ? picked.filter(x => x !== of) : [...picked, of]; }
  function toggleReg(r: Registrar) { regs = regs.includes(r) ? regs.filter(x => x !== r) : [...regs, r]; }
  function camsFiles() {
    ui.open({ type: 'cams_files', done: added => {
      const here = added.filter(a => months.includes(a));
      if (here.length) picked = [...picked, ...here.filter(a => !picked.includes(a))];
      if (added.length && !regs.includes('CAMS')) regs = [...regs, 'CAMS'];
    } });
  }
  function go() {
    if (!picked.length || !regs.length) return;
    const periods = [...picked].sort((a, b) => index(a) - index(b));          // the oldest first
    ui.runWith = { registrars: regs, period: periods[0], what: 'download', periods };
  }
</script>

<div class="page-in enter dlpage">
  <div class="mhd"><div><h1>Downloads</h1>
    <p class="sub">Any months' invoices onto this PC, with every figure. Nothing is signed or submitted.</p></div></div>

  <div class="tblwrap"><table class="tbl">
    <thead><tr>
      <th style="width:36px"><input type="checkbox" aria-label="All months" checked={all} onchange={() => (picked = all ? [] : [...months])} /></th>
      <th>Month</th><th>On this PC</th><th class="num">Total</th><th>Status</th></tr></thead>
    <tbody>
      {#each months as of (of)}
        {@const r = row(of)}
        <tr class="pick" class:on={picked.includes(of)} onclick={() => toggle(of)}>
          <td><input type="checkbox" aria-label={nameOf(of)} checked={picked.includes(of)} onclick={e => e.stopPropagation()} onchange={() => toggle(of)} /></td>
          <td>{nameOf(of)}{of === s.month!.period ? ' · this month' : ''}</td>
          <td>{r?.count ? `${r.count} ${r.count === 1 ? 'invoice' : 'invoices'}` : '—'}</td>
          <td class="num">{r?.count ? inr(r.total) : ''}</td>
          <td>{r?.count ? r.status : ''}</td>
        </tr>
      {/each}
    </tbody>
  </table></div>

  <div class="dl-foot">
    {#if registrarsOf(p).length > 1}
      {#each registrarsOf(p) as r (r)}
        <label class="check"><input type="checkbox" checked={regs.includes(r)} onchange={() => toggleReg(r)} /> {regName(r)}</label>
      {/each}
    {/if}
    <span class="line">{regs.includes('CAMS') && p.mailbox.provider !== 'folder' ? 'You can Skip CAMS and continue without waiting; the email is automatically read whenever it arrives.' : ''}</span>
    {#if registrarsOf(p).includes('CAMS')}<button class="btn camsbtn" onclick={camsFiles}>Add CAMS's files</button>{/if}
    <button class="btn primary" data-primary disabled={!picked.length || !regs.length} onclick={go}>{@html icons.dl}
      {picked.length ? `Download ${picked.length} ${picked.length === 1 ? 'month' : 'months'}` : 'Pick months'}</button>
  </div>
</div>

<style>
  .dlpage { max-width: 1000px; }
  tr.pick { cursor: pointer; }
  tr.pick.on td { background: var(--blue-wash); }
  .dl-foot { display: flex; align-items: center; gap: 16px; padding: 14px 0; position: sticky; bottom: 0; background: var(--canvas); }
  .dl-foot .btn.primary { display: inline-flex; gap: 8px; align-items: center; }
  .dl-foot .line { flex: 1; font-size: 12.5px; color: var(--muted); }
</style>
