<script lang="ts">
  /* DEVELOPMENT ONLY. The fake app's switches, so every state can be reached by hand. App.svelte loads this file
     behind `import.meta.env.DEV`, so the shipped build does not contain it (rule §12: never a developer menu). */
  import { app } from '../bridge';
  import type { DevFakeApp } from './devFake';
  import type { MonthState } from '../bridge/fake/data';
  import { STEP } from '../logic/details';
  import { timing } from '../state/timing';
  import { ui } from '../state/ui.svelte';
  import { signature } from '../bridge/fake/images';

  const fake = app as DevFakeApp;
  let sc = $state({ ...fake.scenario });
  let open = $state(true);
  let fast = $state(false);

  function set<K extends keyof typeof sc>(k: K, v: (typeof sc)[K]) {
    sc[k] = v;
    fake.set({ [k]: v });
  }
  function preset(which: 'first' | 'ready') {
    const s = which === 'first'
      ? { signedIn: false, hasArn: false, condition: 'normal' as const, update: false, month: 'to_do' as MonthState, plan: 'none' as const }
      : { signedIn: true, hasArn: true, condition: 'normal' as const, update: false, plan: 'paid' as const };
    Object.assign(sc, s);
    fake.set(s);
    ui.popups = [];
    ui.runWith = null;
    if (which === 'first') ui.go('signin'); else ui.go('overview');
  }
  function fill() {
    const d = ui.draft;
    const a = ui.adding
      ? { arn: 'ARN-121904', gstin: '27AAKPM5678K1ZY', name: 'A. R. Mehta', camsEmail: 'armehta.mfd@gmail.com', camsUsed: true }
      : { arn: 'ARN-104512', gstin: '27ABCPM1234F1Z3', name: 'R. K. Mehta', camsEmail: 'rkmehta@gmail.com', camsUsed: true };
    Object.assign(d, a);
    if (ui.step >= STEP.kfintech) d.camsArn = a.arn;
    if (ui.step >= STEP.name) d.kfintech = { used: true, username: 'rkmehta_dss', loggedInAs: 'R K MEHTA', arn: a.arn };
    if (ui.step >= STEP.tally) d.signature = { way: 'image', present: true, image: signature(0), size: 100, cert: null };
    if (ui.step >= STEP.invoices) d.tally = { company: 'Lunavat & Co', guid: 'g1', gstin: a.gstin, same: true, sure: false };
    if (ui.step >= STEP.mailbox) d.mailbox = { provider: 'gmail', address: a.camsEmail, connected: true };
  }
  $effect(() => {
    timing.captchaPauseMs = fast ? 8_000 : 3 * 60_000;
  });
  const MONTHS: MonthState[] = ['first_run', 'stopped', 'not_listed', 'not_fetched', 'to_do', 'partly', 'submitted', 'rejected', 'approved'];
</script>

<div class="devbar" class:shut={!open}>
  <button class="dv" onclick={() => (open = !open)} title="Development only">{open ? 'Dev ▾' : 'Dev ▸'}</button>
  {#if open}
    <button class="dv" onclick={() => preset('first')}>First launch</button>
    <button class="dv" onclick={() => preset('ready')}>Set up</button>
    <button class="dv" onclick={fill}>Fill setup</button>
    <label>In <input type="checkbox" checked={sc.signedIn} onchange={e => set('signedIn', e.currentTarget.checked)} /></label>
    <label>ARN <input type="checkbox" checked={sc.hasArn} onchange={e => set('hasArn', e.currentTarget.checked)} /></label>
    <label>2 ARNs <input type="checkbox" checked={sc.secondArn} onchange={e => set('secondArn', e.currentTarget.checked)} /></label>
    <select value={sc.condition} onchange={e => set('condition', e.currentTarget.value as typeof sc.condition)} title="A hard day">
      <option value="normal">Today: normal</option><option value="offline">No internet</option><option value="down">Our service down</option></select>
    <label>Update <input type="checkbox" checked={sc.update} onchange={e => set('update', e.currentTarget.checked)} /></label>
    <label>Survey <input type="checkbox" checked={sc.survey} onchange={e => set('survey', e.currentTarget.checked)} /></label>
    <select value={sc.plan} onchange={e => set('plan', e.currentTarget.value as typeof sc.plan)} title="The plan">
      {#each ['paid', 'trial', 'none', 'used', 'ended', 'unknown'] as k (k)}<option value={k}>Plan: {k}</option>{/each}</select>
    <select value={sc.month} onchange={e => set('month', e.currentTarget.value as MonthState)} title="The month">
      {#each MONTHS as m (m)}<option value={m}>Month: {m.replace('_', ' ')}</option>{/each}</select>
    <select value={sc.stop} onchange={e => set('stop', e.currentTarget.value)} title="The next run">
      <option value="">Next run: goes through</option>
      {#each ['arn_mismatch', 'account_locked', 'refused', 'not_listed', 'nothing_to_do', 'mailbox', 'mailback_late', 'wrong_files', 'mismatch', 'portal_validation', 'unknown_submit', 'not_submitting', 'ours', 'arn_unbound', 'unreachable'] as k (k)}<option value={k}>Stops: {k}</option>{/each}</select>
    <label>No books <input type="checkbox" checked={sc.booksOff} onchange={e => set('booksOff', e.currentTarget.checked)} /></label>
    <label>Tally shut <input type="checkbox" checked={sc.tallyDown} onchange={e => set('tallyDown', e.currentTarget.checked)} /></label>
    <label>Renumber <input type="checkbox" checked={sc.renumber} onchange={e => set('renumber', e.currentTarget.checked)} /></label>
    <label>New year <input type="checkbox" checked={sc.newYear} onchange={e => set('newYear', e.currentTarget.checked)} /></label>
    <label>Tally asks <input type="checkbox" checked={sc.booksAsk} onchange={e => set('booksAsk', e.currentTarget.checked)} /></label>
    <label>Slow email <input type="checkbox" checked={sc.slowEmail} onchange={e => set('slowEmail', e.currentTarget.checked)} /></label>
    <label>Files by hand <input type="checkbox" checked={sc.byHand} onchange={e => set('byHand', e.currentTarget.checked)} /></label>
    <label>Short waits <input type="checkbox" bind:checked={fast} /></label>
    <button class="dv" onclick={() => fake.approvalsArrive()}>Approvals arrive</button>
    <button class="dv" onclick={() => fake.rejectionArrives()}>Rejection arrives</button>
    <button class="dv" onclick={() => fake.pressClose()}>Press ✕</button>
  {/if}
</div>

<style>
  .devbar { position: fixed; left: 50%; bottom: 8px; transform: translateX(-50%); z-index: 1000; display: flex; flex-wrap: wrap; justify-content: center;
    align-items: center; gap: 4px; max-width: calc(100vw - 16px); padding: 5px; border-radius: 10px; background: rgba(15, 23, 42, .9); color: #e2e8f0; font: 11.5px system-ui, sans-serif; }
  .devbar.shut { left: auto; right: 8px; transform: none; }
  .dv, select { height: 24px; padding: 0 8px; border-radius: 6px; border: 0; background: rgba(255, 255, 255, .1); color: #fff; font: inherit; }
  .dv:hover { background: rgba(255, 255, 255, .2); }
  select option { color: #0f172a; }
  label { display: inline-flex; align-items: center; gap: 3px; padding: 0 4px; }
</style>
