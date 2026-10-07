<script lang="ts">
  /* The run window: a run of the month, a check of what the registrars have, or a download of the month's invoices.
     Header, bar and footer stay put; only the middle scrolls. Esc never closes it. Everything it shows comes from what
     the app pushes: the steps, and one question at a time. A run that ends is over: nothing here carries one on. */
  import { onDestroy, onMount } from 'svelte';
  import type { Registrar, RunKind } from '../../bridge';
  import { clock, inr, regName } from '../../logic/format';
  import { stepsView } from '../../logic/steps';
  import { store } from '../../state/store.svelte';
  import { ui } from '../../state/ui.svelte';
  import { icons } from '../../ui/icons';
  import BeforeRun from './BeforeRun.svelte';
  import BooksAsk from './BooksAsk.svelte';
  import Entered from './Entered.svelte';
  import PickFiles from './PickFiles.svelte';
  import PinAsk from './PinAsk.svelte';
  import SignatureCheck from './SignatureCheck.svelte';
  import StopScreen from './StopScreen.svelte';
  import Working from './Working.svelte';
  import YourCheck from './YourCheck.svelte';

  let { registrars, period, what, periods }: { registrars: Registrar[]; period: string; what: RunKind; periods?: string[] } = $props();

  const run = $derived(store.run);
  const MON = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
  const NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const nameOf = (of: string) => `${NAMES[MON.indexOf(of.split('-')[0])] ?? ''} ${of.split('-')[1] ?? ''}`.trim();
  // a download of several months says which one it is on
  const month = $derived(periods && periods.length > 1
    ? (run?.month ? `${nameOf(run.month.period)} (${run.month.index + 1} of ${periods.length})` : `${periods.length} months`) : nameOf(period));
  const all = $derived((store.snap?.profile ? [store.snap.profile.camsUsed && 'CAMS', store.snap.profile.kfintech.used && 'KFINTECH'].filter(Boolean).length : 2));
  const title = $derived(what === 'check' ? 'Check status' : what === 'download' ? 'Download invoices' : 'Run');
  const asked = $derived(run?.ask?.type === 'captcha' || run?.ask?.type === 'pick_files' || run?.ask?.type === 'your_check' || run?.ask?.type === 'signature' || run?.ask?.type === 'books_ask');
  const v = $derived(stepsView(run?.steps ?? [], asked));

  // a stop is the run's last word: it stays on screen until the person closes it
  const stop = $derived(run?.stop ?? null);

  // the clock: seconds since the run began, stopped when it ends
  let now = $state(Date.now());
  let endedAt = $state(0);
  const t = setInterval(() => (now = Date.now()), 1000);
  onDestroy(() => clearInterval(t));
  $effect(() => { if (run?.ended && !endedAt) endedAt = Date.now(); });
  const elapsed = $derived(run ? Math.max(0, Math.floor(((endedAt || now) - run.startedAt) / 1000)) : 0);

  const wide = $derived(run?.ask?.type === 'your_check');

  function close() {
    store.endRun();
    ui.runWith = null;
  }
  function again() {
    const same = { registrars, period, what, periods };
    close();
    setTimeout(() => (ui.runWith = same), 0);
  }
  function notNow() {
    store.answerRun({ type: 'your_check', confirmed: false, included: [] });
    store.toast('Nothing was submitted. Run again any time: the invoices are already on this PC.');
    close();
  }

  // focus moves into the run window, and Tab stays inside it while it is open
  let box: HTMLDivElement;
  onMount(() => box.focus());
  function trap(e: KeyboardEvent) {
    if (e.key !== 'Tab') return;
    const all = [...box.querySelectorAll<HTMLElement>('a[href],button:not([disabled]),input:not([disabled]),textarea,select,[tabindex="0"]')];
    if (!all.length) return;
    const first = all[0], last = all[all.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === box)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  // a check that read the status says so and closes; a run the person stopped just closes
  $effect(() => {
    if (!run?.ended || run.ask || stop) return;
    if (run.ended === 'done' && run.what === 'check') { store.toast(run.summary || 'Checked.'); close(); }
    else if (run.ended !== 'done') close();
  });
  const sent = $derived((run?.submitted.CAMS ?? 0) + (run?.submitted.KFINTECH ?? 0));
</script>

<div class="runov" data-layer="run">
  <div class="rm" class:wide role="dialog" aria-modal="true" aria-label={title} tabindex="-1" bind:this={box} onkeydown={trap}>
    <div class="rm-hd"><div class="t">{title} <span>· {month}{registrars.length < all ? ` · ${registrars.map(regName).join(' and ')} only` : ''}</span></div></div>
    <div class="prog" aria-hidden="true">
      {#each (v.bars.length ? v.bars : ['waiting', 'waiting', 'waiting']) as b, i (i)}
        <i class:done={b === 'done'} class:need={b === 'need'} class:bad={b === 'bad'} style="--p:{b === 'running' ? '55%' : '0%'}"></i>
      {/each}
    </div>
    <div class="prog-meta"><span>{run ? v.meta : 'Before it starts'}</span><span class="mono">{clock(elapsed)}</span></div>

    {#if !run}
      <BeforeRun {registrars} {period} {what} {periods} onclose={close} />
    {:else if stop}
      <StopScreen {stop} enter={run?.enter ?? []} left={run?.left ?? []} onclose={close} onagain={again} />
    {:else if run.ended === 'done'}
      <div class="rm-stage">
        {#if run.what === 'run'}
          <div class="done-hd"><span class="stamp play">SUBMITTED</span>
            <div class="big">{sent} {sent === 1 ? 'invoice' : 'invoices'} submitted</div>
            <div class="sub">{[run.submitted.CAMS && `CAMS ${run.submitted.CAMS}`, run.submitted.KFINTECH && `KFintech ${run.submitted.KFINTECH}`].filter(Boolean).join(' · ')}{run.total ? ` · ${inr(run.total)}` : ''}</div>
            {#if run.used}<p class="sub mono">{run.used}</p>{/if}
            <p class="sub">{run.summary}</p></div>
          <Entered enter={run.enter} left={run.left} />
        {:else}
          <div class="done-hd"><span class="tick big ok">{@html icons.tickSm}</span>
            <div class="big">{run.summary}</div>
            <p class="sub">They are on this PC, with every figure. Nothing was signed or submitted.</p></div>
        {/if}
      </div>
      <div class="rm-foot">
        <button class="btn secondary" onclick={() => { ui.go('invoices'); ui.invoicesMonth = periods && periods.length > 1 ? null : period; close(); }}>See invoices</button>
        <button class="btn secondary" onclick={() => { ui.tallyMonth = period; ui.go('tally'); close(); }}>Import into Tally</button>
        <button class="btn primary" data-primary style="margin-left:auto" onclick={() => { close(); ui.go('overview'); }}>Close</button>
      </div>
    {:else if run.ask?.type === 'your_check'}
      {#key run.ask.id}<YourCheck ask={run.ask} {registrars} {month} onnotnow={notNow} />{/key}
    {:else if run.ask?.type === 'books_ask'}
      {#key run.ask.id}<BooksAsk ask={run.ask} />{/key}
    {:else if run.ask?.type === 'signature'}
      {#key run.ask.id}<SignatureCheck ask={run.ask} />{/key}
    {:else if run.ask?.type === 'pick_files'}
      {#key run.ask.id}<PickFiles ask={run.ask} />{/key}
    {:else if run.ask?.type === 'pin'}
      {#key run.ask.id}<PinAsk ask={run.ask} />{/key}
    {:else}
      <Working {run} captcha={run.ask?.type === 'captcha' ? run.ask : null} onclose={close} />
    {/if}
  </div>
</div>
