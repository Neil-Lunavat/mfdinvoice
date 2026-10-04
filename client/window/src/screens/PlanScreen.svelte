<script lang="ts">
  import { NAME } from '../brand';
  /* In place of the month on Overview, when this ARN has no plan to run on:
       activate  the account has never had a plan: Activate free trial, for the ARN on screen
       ended     the plain plan screen: what the plan was, when it ended, one button to the website
       unbound   the plan is running, but this ARN is not on it: add it to a free slot, or get one on the website
     Nothing is sold or priced here. Invoices and Settings stay open in the sidebar. */
  import { app } from '../bridge';
  import { dayMonYear } from '../logic/format';
  import { store } from '../state/store.svelte';
  import { ui } from '../state/ui.svelte';

  let { kind }: { kind: 'activate' | 'ended' | 'unbound' } = $props();

  const s = $derived(store.snap!);
  const plan = $derived(s.plan!);
  let busy = $state(false);

  async function activate() {
    const trial = kind === 'activate';                 // the screen changes once it is done
    busy = true;
    const r = await app.activateTrial();
    busy = false;
    if (r.ok && trial) ui.open({ type: 'trial_started' });
    else store.toast(r.ok ? 'Added to your plan' : r.said);
  }
</script>

<div class="page-in fit enter">
  <div class="mhd"><div><h1>{kind === 'activate' ? 'Your free trial' : 'Your plan'}</h1><p class="sub">{s.arn} · {s.profile?.name}</p></div></div>
  <div class="card month">
    {#if kind === 'activate'}
      <div class="mc-l">
        <span class="chip neutral">Not started</span>
        <div class="big">{NAME} is yours, free, for 15 days.</div>
        <div class="facts">Everything is unlocked for {s.arn}: CAMS and KFintech, every fund house, every invoice. Nothing held back, nothing to pay, no card.
          {#if s.profile?.bindOnRun}The 15 days start with your first run, once CAMS's email for {s.arn} has been read: that shows the ARN is yours.{/if}</div>
      </div>
      <div class="mc-r">
        <button class="btn run" data-primary disabled={busy || s.condition !== 'normal'} onclick={activate}>{busy ? 'Activating…' : 'Activate free trial'}</button>
        <span class="about">Nothing to pay</span>
      </div>
    {:else if kind === 'unbound'}
      <div class="mc-l">
        <span class="chip neutral">Not on your plan</span>
        <div class="big">{s.arn} isn't on your plan yet.</div>
        <div class="facts">Your plan has {plan.slots} ARN {plan.slots === 1 ? 'slot' : 'slots'}, {plan.arns.length} in use. More are added on the website.</div>
      </div>
      <div class="mc-r">
        {#if plan.arns.length < plan.slots}
          <button class="btn run" data-primary disabled={busy || s.condition !== 'normal'} onclick={activate}>{busy ? 'Adding…' : 'Add it to your plan'}</button>
        {:else}
          <button class="btn run" data-primary onclick={() => app.open('billing')}>Open your account on the website</button>
        {/if}
      </div>
    {:else}
      <div class="mc-l">
        <span class="chip neutral">Ended</span>
        <div class="big">Your {plan.source === 'trial' ? 'free trial' : 'plan'} ended on {dayMonYear(plan.until)}.</div>
        <div class="facts">Runs are off until a plan is running again. Everything already on this PC still opens.</div>
      </div>
      <div class="mc-r">
        <button class="btn run" data-primary onclick={() => app.open('billing')}>Open your account on the website</button>
      </div>
    {/if}
  </div>
</div>
