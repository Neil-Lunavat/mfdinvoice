<script lang="ts">
  /* Setup, per ARN: eight steps, one per screen (the books are optional). Back never erases; Continue unlocks only when the step is valid.
     From Check everything, Change opens a step whose button becomes Save and comes straight back. Finish setup needs
     every step to hold and a portal's sign-in to have shown the ARN: finishing binds the ARN to the account. */
  import { onMount } from 'svelte';
  import { app } from '../../bridge';
  import { arnProven, bookKind, consentOf, booksLine, invoicesLine, kfintechLine, mailboxLine, provenBy, signatureLine, STEP, STEP_TITLES, stepValid } from '../../logic/details';
  import { store } from '../../state/store.svelte';
  import { ui } from '../../state/ui.svelte';
  import { icons } from '../../ui/icons';
  import CamsEmail from './CamsEmail.svelte';
  import Kfintech from './Kfintech.svelte';
  import Mailbox from './Mailbox.svelte';
  import NameGstin from './NameGstin.svelte';
  import SignatureStep from './SignatureStep.svelte';
  import BooksStep from './BooksStep.svelte';
  import YourInvoices from './YourInvoices.svelte';

  const LAST = STEP_TITLES.length - 1;
  const email = $derived(store.snap?.account?.email ?? '');
  // an ARN read that this software already has cannot be set up again
  const already = $derived(!!ui.draft.arn && !!store.snap?.arns.some(a => a.arn.replace(/\D/g, '') === ui.draft.arn.replace(/\D/g, '')));
  const valid = $derived(stepValid[ui.step](ui.draft) && !already);
  const current = $derived(store.snap?.arns.find(a => a.arn === store.snap?.arn));
  const used = $derived(store.snap?.arns.length ?? 0);
  let saving = $state(false);

  function to(i: number) {
    ui.step = Math.max(0, Math.min(i, LAST));
    ui.reached = Math.max(ui.reached, ui.step);
    setTimeout(() => document.querySelector<HTMLElement>('.pane-in input:not([disabled]), .pane-in .tile')?.focus(), 60);
  }
  async function next() {
    if (!valid || saving) return;
    if (ui.step === LAST) {
      saving = true;
      const r = await app.finishSetup({ ...$state.snapshot(ui.draft), consent: consentOf($state.snapshot(ui.draft)) }, ui.adding);
      saving = false;
      if (r.ok) { ui.adding = false; ui.go('overview'); }   // the app has dropped the kept setup
      else store.toast(r.said);
      return;
    }
    if (ui.returnTo !== null) { const back = ui.returnTo; ui.returnTo = null; to(back); return; }
    to(ui.step + 1);
  }
  function change(i: number) { ui.returnTo = LAST; to(i); }
  function cancelAdd() { void app.dropSetup(); ui.adding = false; ui.go('overview'); }

  // setup is kept on the PC as it goes (debounced), so closing the software resumes it; leaving the screen cancels a pending save
  $effect(() => {
    const state = ui.setupState();
    const t = setTimeout(() => { void app.saveSetup(state).catch(() => {}); }, 400);
    return () => clearTimeout(t);
  });

  // a restored photo lives in the draft: only a setup without one forgets the app's unkept photo
  onMount(() => { if (!ui.draft.signature.image) void app.dropSignatureDraft(); to(ui.step); });
</script>

<div class="view setup" data-layer="page">
  <aside class="rail">
    <div class="rail-hd"><span class="mark" style="width:26px;height:26px;border-radius:7px">{@html icons.mark(14)}</span>
      <b>{ui.adding ? `Add an ARN · ${used + 1} of ${store.snap?.account?.maxArns ?? 6}` : 'Set up your ARN'}</b></div>
    <ol class="steps">
      {#each STEP_TITLES as t, i (t)}
        {@const done = i !== ui.step && i < ui.reached}
        <li class:now={i === ui.step} class:done aria-current={i === ui.step ? 'step' : undefined}>
          <i>{#if done}{@html icons.tickSm}{:else}{i + 1}{/if}</i>{t}</li>
      {/each}
    </ol>
    <div class="rail-ft"><span class="who2">{email}</span>
      <button class="btn ghost sm" onclick={() => ui.open({ type: 'support', where: `Setup, step ${ui.step + 1}` })}>{@html icons.help}Send to support</button></div>
    {#if ui.adding && current}
      <button class="btn ghost sm" style="margin:0 0 8px" onclick={cancelAdd}>Cancel · back to {current.name}</button>
    {/if}
  </aside>

  <section class="pane">
    {#key ui.step}
      <div class="pane-in enter">
        <div class="label">Step {ui.step + 1} of {STEP_TITLES.length}</div>
        <div id="parts"><div class="part">
          <div class="part-hd"><h2 class="step-h">{STEP_TITLES[ui.step]}</h2>
            {#if ui.step < LAST}<button class="btn ghost sm vid" onclick={() => app.open('help')}>{@html icons.play}How to · {ui.step === STEP.mailbox ? '2 min' : '1 min'}</button>{/if}</div>
          {#if ui.step === STEP.cams}<CamsEmail bind:d={ui.draft} signInEmail={email} />
          {:else if ui.step === STEP.kfintech}<Kfintech bind:d={ui.draft} />
          {:else if ui.step === STEP.name}<NameGstin bind:d={ui.draft} />
          {:else if ui.step === STEP.signature}<SignatureStep bind:d={ui.draft} />
          {:else if ui.step === STEP.books}<BooksStep bind:d={ui.draft} />
          {:else if ui.step === STEP.invoices}<YourInvoices bind:d={ui.draft} noSignature />
          {:else if ui.step === STEP.mailbox}
            {#if ui.draft.camsUsed}<Mailbox bind:d={ui.draft} />
            {:else}<p class="line">The mailbox is only for CAMS's invoice mails, and this ARN doesn't use CAMS. Nothing to connect.</p>{/if}
          {:else}
            {@const d = ui.draft}
            <div class="cklist">
              {#each [
                ['ARN', d.arn, STEP.cams, true], ['GSTIN', `${d.gstin} · ${d.name}`, STEP.name, true], ['CAMS email', d.camsUsed ? d.camsEmail : 'Not used', STEP.cams, false],
                ['KFintech', kfintechLine(d.kfintech), STEP.kfintech, false],
                ...(d.camsUsed ? [['Mailbox', mailboxLine(d.mailbox).replace(/ · not connected$/, ''), STEP.mailbox, false]] : [])
              ] as [k, v, step, mono] (k)}
                <div class="ck"><span class="k">{k}</span><span class="v" class:mono>{v}</span>
                  {#if !stepValid[step as number](d)}<span class="err">Needs a change</span>{/if}
                  <a href="#change" onclick={e => { e.preventDefault(); change(step as number); }}>Change</a></div>
              {/each}
              <div class="ck"><span class="k">Signature</span>{#if d.signature.way === 'dsc'}<span class="v">{signatureLine(d.signature)}</span>
                {:else}<span class="v sigmini"><img class="sigimg" src={d.signature.image} alt="Your signature" /></span>{/if}
                <a href="#change" onclick={e => { e.preventDefault(); change(STEP.signature); }}>Change</a></div>
              <div class="ck"><span class="k">Books</span><span class="v">{booksLine(d)}</span>
                {#if !stepValid[STEP.books](d)}<span class="err">Needs a change</span>{/if}
                <a href="#change" onclick={e => { e.preventDefault(); change(STEP.books); }}>Change</a></div>
              <div class="ck"><span class="k">Invoices</span><span class="v">{invoicesLine(d.invoices, bookKind(d))}</span>
                {#if !stepValid[STEP.invoices](d)}<span class="err">Needs a change</span>{/if}
                <a href="#change" onclick={e => { e.preventDefault(); change(STEP.invoices); }}>Change</a></div>
            </div>
            {#if !arnProven(d)}
              <div class="banner bad" role="alert"><div><b>Your ARN isn't confirmed yet.</b> {d.kfintech.used ? 'Verify your KFintech login' : 'Verify your CAMS email'}: it shows whose ARN this is.</div>
                <button class="btn secondary sm" onclick={() => change(d.kfintech.used ? STEP.kfintech : STEP.cams)}>{d.kfintech.used ? 'Verify KFintech' : 'Verify CAMS'}</button></div>
            {:else}
              <p class="line">{d.arn} is confirmed by {provenBy(d)}.</p>
            {/if}
          {/if}
        </div></div>
      </div>
    {/key}
    <div class="pane-ft">
      {#if ui.step > 0}<button class="btn ghost" id="back" onclick={() => to(ui.step - 1)}>Back</button>{/if}
      <button class="btn primary" data-primary disabled={!valid || saving} onclick={next}>
        {ui.step === LAST ? 'Finish setup' : ui.returnTo !== null ? 'Save' : 'Continue'}</button>
    </div>
  </section>
</div>
