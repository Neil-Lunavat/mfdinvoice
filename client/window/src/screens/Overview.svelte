<script lang="ts">
  import { NAME } from '../brand';
  /* Overview: one month. This month when it opens; any other from the month picker at the top right, and Run, Check
     now and Download then work on that month (a month that was missed is run the same way). Fits 1376 × 768 with no
     scroll. Problems show only when something is wrong, as a red banner with the fix, and Run turns off. */
  import { app, type Month, type Registrar, type RunKind } from '../bridge';
  import { consentCurrent } from '../logic/consent';
  import { registrarsOf } from '../logic/details';
  import { checkedLine, dayMon, inr, regName } from '../logic/format';
  import { card, registrarCard, rejections } from '../logic/month';
  import { missingOf, runOffOf } from '../logic/runoff';
  import { store } from '../state/store.svelte';
  import { ui } from '../state/ui.svelte';
  import { icons } from '../ui/icons';
  import SurveyToast from '../ui/SurveyToast.svelte';

  let { banner }: { banner: 'down' | 'offline' | null } = $props();

  const MON = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
  const NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const FIRST = 'APR-2026';                     // CAMS's and KFintech's GST invoices began with April 2026

  const s = $derived(store.snap!);
  const p = $derived(s.profile!);
  const now = $derived(s.month!.period);

  // the month on screen: this one, or the one picked
  const period = $derived(ui.month ?? now);
  let other = $state<Month | null>(null);
  $effect(() => {
    void store.snap;                           // a run that just ended changed what is on disk: read it again
    const want = period;
    if (want === now) { other = null; return; }
    app.month(want).then(got => { if (got.period === period) other = got; });
  });
  const m = $derived(period === now ? s.month! : other?.period === period ? other : { ...s.month!, period, label: labelOf(period), kfLabel: labelOf(step(period, -1)), invoices: [], checkedAt: '', lastRun: null, submittedOn: '', listed: false, notListed: [] });

  function step(of: string, by: number): string {
    const [mon, yr] = of.split('-');
    const n = Number(yr) * 12 + MON.indexOf(mon) + by;
    return `${MON[((n % 12) + 12) % 12]}-${Math.floor(n / 12)}`;
  }
  function labelOf(of: string) { const [mon, yr] = of.split('-'); return `${NAMES[MON.indexOf(mon)]} ${yr}`; }
  const index = (of: string) => { const [mon, yr] = of.split('-'); return Number(yr) * 12 + MON.indexOf(mon); };
  // the picker: this month back to April 2026, by name only (a year picker comes when there is a second year)
  const months = $derived(Array.from({ length: Math.max(1, index(now) - index(FIRST) + 1) }, (_, i) => step(now, -i)));
  const nameOf = (of: string) => NAMES[MON.indexOf(of.split('-')[0])];
  function pickMonth(of: string) { ui.menu = ''; ui.month = of === now ? null : of; }

  const c = $derived(card(m));
  const regs = $derived<Registrar[]>(registrarsOf(p));
  const rej = $derived(rejections(m));
  const missing = $derived(missingOf(p));
  function fix(which: 'sig' | 'mb' | 'inv') {
    if (which === 'mb') ui.open({ type: 'edit', which });
    else { ui.go('settings'); ui.goSection('Your invoices'); }     // the signature and the number are both there
  }
  // the plan could not be read just now (never "no plan"), and the authority sentence not yet agreed for this ARN
  const planUnknown = $derived(s.plan?.state === 'unknown');
  const needsConsent = $derived(!consentCurrent(p.consent));
  const runOff = $derived(runOffOf(s));
  let asking = $state(false);
  async function checkPlan() { asking = true; await app.checkPlan(); setTimeout(() => (asking = false), 1500); }
  const monthName = $derived(m.label.split(' ')[0]);

  function open(what: RunKind, only?: Registrar) { ui.menu = ''; ui.runWith = { registrars: only ? [only] : regs, period, what }; }
  function checkNow() {
    if (runOff) return;
    open('check');
  }
  function openRejected() {
    if (rej.length === 1) { ui.go('invoices'); ui.invoicesMonth = m.period; ui.open({ type: 'invoice', invoice: rej[0], period: m.period }); }
    else { ui.go('invoices'); ui.invoicesMonth = m.period; }
  }
  const stageNames = (bad: boolean) => ['Fetched', 'Signed', 'Checked', 'Submitted', bad ? 'Rejected' : 'Approved'];
  // CAMS's email hadn't come when the last run went on with KFintech: Run is CAMS's now; both and KFintech are in the menu
  const camsNext = $derived(!!m.camsWaiting && regs.length > 1);
  const openOf = (r: Registrar) => m.invoices.filter(x => x.registrar === r && !['Waiting approval', 'Approved', 'Submitted'].includes(x.status)).length;
</script>

<div class="page-in fit enter">
  <div class="mhd">
    <div><h1>{m.label}</h1>{#if p.kfintech.used}<p class="sub">KFintech's trail month: {m.kfLabel}</p>{/if}</div>
    <div class="stepper" style="position:relative">
      <button aria-label="The month before" disabled={period === months.at(-1)} onclick={() => pickMonth(step(period, -1))}>{@html icons.prev}</button>
      <button class="val pick" aria-haspopup="menu" aria-expanded={ui.menu === 'month'} aria-label="Pick a month"
        onclick={e => { e.stopPropagation(); ui.menu = ui.menu === 'month' ? '' : 'month'; }}>{nameOf(period)}{@html icons.chevDown}</button>
      <button aria-label="The month after" disabled={period === now} onclick={() => pickMonth(step(period, 1))}>{@html icons.next}</button>
      {#if ui.menu === 'month'}
        <div class="menu months" role="menu">
          {#each months as of (of)}
            <button role="menuitem" class:on={of === period} onclick={e => { e.stopPropagation(); pickMonth(of); }}>{nameOf(of)}<span>{of === now ? 'This month' : ''}</span></button>
          {/each}
        </div>
      {/if}
    </div>
  </div>

  {#if rej.length}
    {@const x = rej[0]}
    <div class="banner bad" role="alert"><div>
      {#if rej.length === 1}<b>{x.amc} rejected {x.number}.</b> {regName(x.registrar)} says: “{x.rejection}”
      {:else}<b>{rej.length} invoices were rejected.</b> {x.amc}: “{x.rejection}”{/if}</div>
      <button class="btn secondary sm" onclick={openRejected}>{rej.length === 1 ? 'Open invoice' : 'See invoices'}</button></div>
  {/if}
  {#if banner === 'offline'}
    <div class="banner bad" role="alert"><div><b>No internet.</b> {NAME} needs it to run. Everything here still opens.</div></div>
  {:else if banner === 'down'}
    <div class="banner bad" role="alert"><div><b>{NAME} is having trouble.</b> Your data is safe here. Runs are paused until it's fixed.</div>
      <button class="btn secondary sm" onclick={() => app.open('status')}>Status</button></div>
  {/if}
  {#if planUnknown && !banner}
    <div class="banner bad" role="alert"><div><b>We couldn't check your plan just now.</b> Try again in a few minutes.</div>
      <button class="btn secondary sm" disabled={asking} onclick={checkPlan}>{asking ? 'Checking…' : 'Try again'}</button></div>
  {/if}
  {#if needsConsent}
    <div class="banner bad" role="alert"><div><b>One thing to confirm for {p.arn}.</b> {NAME} needs your say-so to act on CAMS and KFintech.</div>
      <button class="btn secondary sm" onclick={() => ui.open({ type: 'consent' })}>Confirm</button></div>
  {/if}
  {#if p.camsUsed && !p.camsArn && !p.lastLogin.CAMS}
    <div class="banner wait" role="status"><div><b>CAMS isn't verified.</b> Your run may stop at CAMS.</div>
      <button class="btn secondary sm" onclick={() => ui.open({ type: 'edit', which: 'cams' })}>Verify CAMS</button></div>
  {/if}
  {#each missing as x (x.which)}
    <div class="banner bad" role="alert">{x.text}.<button class="btn secondary sm" onclick={() => fix(x.which)}>{x.fix}</button></div>
  {/each}

  <div class="card month">
    <div class="mc-l">
      {#if c.state === 'first_run'}
        <span class="chip neutral">Not submitted</span>
        <div class="big">Your first run reads what {regs.map(regName).join(' and ')} already {regs.length === 1 ? 'has' : 'have'}.</div>
        <div class="facts">Nothing is submitted without you.</div>
      {:else if c.state === 'stopped'}
        <span class="chip bad">Stopped</span>
        <div class="big">Your last run stopped. Nothing was submitted.</div>
        <div class="facts">{c.lastStopped}{#if m.lastRun?.portal}: “{m.lastRun.portal}”{/if}{#if m.lastRun?.at}<span>·</span>{dayMon(m.lastRun.at)}{/if}</div>
      {:else if c.state === 'not_listed'}
        <span class="chip neutral">Not submitted</span>
        <div class="big">{monthName}'s invoices aren't listed yet.</div>
        <div class="facts">Fund houses usually list them in the first days of the month. Run {monthName} to look again.{#if m.checkedAt}<span>·</span>{checkedLine(m.checkedAt, s.today)}{/if}</div>
      {:else if c.state === 'not_fetched'}
        <span class="chip neutral">Not submitted</span>
        <div class="big">Run {monthName} to get this month's invoices.</div>
        <div class="facts">It reads what {regs.map(regName).join(' and ')} {regs.length === 1 ? 'has' : 'have'}. Nothing is submitted without you.</div>
      {:else if c.state === 'to_do'}
        <span class="chip neutral">Not submitted</span>
        <div class="big">{c.count} invoices to do · {inr(c.total)}</div>
        <div class="facts">{#if c.lastStopped}Last run stopped: {c.lastStopped}<span>·</span>{/if}{regs.map(r => `${regName(r)} ${c.byRegistrar[r]}`).join(' · ')}<span>·</span>{checkedLine(m.checkedAt, s.today)}
          <a href="#check" onclick={e => { e.preventDefault(); checkNow(); }}>Check now</a></div>
      {:else if c.state === 'partly'}
        <span class="chip wait">{c.sent} of {c.count} submitted</span>
        <div class="big">{c.sent} of {c.count} submitted. This run does the other {c.open}.</div>
        <div class="facts">{#if c.lastStopped}Last run stopped: {c.lastStopped}<span>·</span>{/if}{c.open} to do · {inr(c.openTotal)}<span>·</span>{checkedLine(m.checkedAt, s.today)}
          <a href="#check" onclick={e => { e.preventDefault(); checkNow(); }}>Check now</a></div>
      {:else}
        <span class="chip {c.state === 'approved' ? 'good' : 'wait'}">{c.state === 'approved' ? 'Approved' : 'Submitted'}</span>
        <div class="big">{c.approved} approved{c.waiting ? ` · ${c.waiting} waiting` : ''}{c.rejected ? ` · ${c.rejected} rejected` : ''}</div>
        <div class="facts">{#if m.submittedOn}Submitted {dayMon(m.submittedOn)}<span>·</span>{/if}{checkedLine(m.checkedAt, s.today)}
          <a href="#check" onclick={e => { e.preventDefault(); checkNow(); }}>Check now</a></div>
      {/if}
    </div>
    <div class="mc-r">
      {#if c.rerun.keys.length}
        <button class="btn run" id="run" data-primary disabled={runOff} onclick={() => open('run')}>{@html icons.playFill}Run the {c.rerun.keys.length} rejected again</button>
        <span class="about">One run, one sign-in, all of them</span>
      {:else if !c.canRun}
        <button class="btn secondary lg" data-primary onclick={() => { ui.go('invoices'); ui.invoicesMonth = period; }}>See invoices</button>
      {:else}
        <div class="splitrun">
          <button class="btn run" id="run" data-primary disabled={runOff} onclick={() => (camsNext ? open('run', 'CAMS') : open('run'))}>{@html icons.playFill}{camsNext ? 'Run CAMS' : `Run ${monthName}`}</button>
          {#if camsNext || regs.length > 1}
          <button class="btn run caret" aria-label="More ways to run" aria-haspopup="menu" aria-expanded={ui.menu === 'run'} disabled={runOff}
            onclick={e => { e.stopPropagation(); ui.menu = ui.menu === 'run' ? '' : 'run'; }}>{@html icons.caret}</button>
          {/if}
          {#if ui.menu === 'run'}
            <div class="menu" role="menu">
              {#if camsNext}
                <button role="menuitem" onclick={() => open('run')}>Run both <span>CAMS and KFintech</span></button>
                <button role="menuitem" onclick={() => open('run', 'KFINTECH')}>Run KFintech only <span>{m.invoices.length ? `${openOf('KFINTECH')} to do` : ''}</span></button>
              {:else if regs.length > 1}
                {#each regs as r (r)}
                  <button role="menuitem" onclick={() => open('run', r)}>Run {regName(r)} only <span>{m.invoices.length ? `${openOf(r)} to do` : ''}</span></button>
                {/each}
              {/if}
            </div>
          {/if}
        </div>
        {#if banner === 'offline'}<span class="about red">No internet</span>
        {:else if banner === 'down'}<span class="about red">Paused until it's fixed</span>
        {:else if planUnknown}<span class="about red">Plan not checked</span>
        {:else if needsConsent}<span class="about red">Needs your confirmation</span>
        {:else if missing.length}<span class="about red">{missing[0].text}</span>{/if}
      {/if}
    </div>
  </div>

  <div class="grid2" style={regs.length === 1 ? 'grid-template-columns:1fr' : ''}>
    {#each regs as r (r)}
      {@const rc = registrarCard(m, r)}
      <div class="card reg-card">
        <div class="rc-hd"><b>{regName(r)}</b><span class="chip {rc.chip.tone}">{rc.chip.text}</span>
          <button class="icon-btn" data-tip="Open folder" aria-label="Open {regName(r)}'s folder" onclick={() => app.openFolder(r, period)}>{@html icons.folder}</button></div>
        <div class="rc-bd">
          <div class="figs"><div><b>{rc.count || '—'}</b><span>fund houses</span></div><div><b>{rc.count ? inr(rc.total) : '—'}</b><span>with GST</span></div></div>
          <div class="stages">
            {#each stageNames(rc.bad) as t, i (t)}
              {#if i}<i class="bar" class:done={i < rc.on}></i>{/if}
              <span class="st" class:done={i < rc.on} class:bad={rc.bad && i === 4}><i class="d"></i>{t}</span>
            {/each}
          </div>
        </div>
      </div>
    {/each}
  </div>
  <SurveyToast />
</div>
