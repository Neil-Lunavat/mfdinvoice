<script lang="ts">
  /* A step at work: its line and a spinner, then its tick and one-line result dropping into the list. The lines are
     the app's own. KFintech's captcha is asked in place; CAMS's email is waited for in place. Stop ends the run. */
  import { onDestroy } from 'svelte';
  import type { Ask } from '../../bridge';
  import { hhmm } from '../../logic/format';
  import { stepsView } from '../../logic/steps';
  import { store, type RunLive } from '../../state/store.svelte';
  import { timing } from '../../state/timing';
  import { waitingLine, waitingSub } from '../../logic/books';
  import Captcha from '../../ui/Captcha.svelte';
  import { icons } from '../../ui/icons';
  import { app } from '../../bridge';

  let { run, captcha, onclose }: { run: RunLive; captcha: Extract<Ask, { type: 'captcha' }> | null; onclose: () => void } = $props();

  const v = $derived(stepsView(run.steps, !!captcha));

  // a captcha left alone for 3 minutes is stale: KFintech's image has changed, so a fresh one is asked for
  let now = $state(Date.now());
  let askedAt = $state(0);
  const tick = setInterval(() => (now = Date.now()), 1000);
  onDestroy(() => clearInterval(tick));
  $effect(() => { if (captcha) askedAt = Date.now(); });
  const paused = $derived(!!captcha && askedAt > 0 && now - askedAt > timing.captchaPauseMs);

  function answer(text: string, refresh: boolean) {
    store.answerRun({ type: 'captcha', text, refresh });
  }
  let stoppedAt = $state(0);
  let skipping = $state(false);
  let refreshing = $state(false);
  function refreshBooks() { refreshing = true; app.refreshBooks(run.id); setTimeout(() => (refreshing = false), 1500); }
  function stopNow() { stoppedAt = Date.now(); if (store.run) store.run.stopAsked = true; app.stopRun(run.id); }
  // Stop is at once, except while a Submit's answer is being read. If nothing has happened after 6 seconds, the
  // person can close this window.
  const stuck = $derived(run.stopAsked && stoppedAt > 0 && now - stoppedAt > 6000);
  const listed = (m: string[]) => m.length < 2 ? m.join('') : `${m.slice(0, -1).join(', ')} and ${m[m.length - 1]}`;
</script>

<div class="rm-stage">
  <div class="work-hd"><div><h3>{run.waitingEmail?.months?.length ? "Waiting for CAMS's emails" : v.line || 'Starting'}</h3></div>{#if !captcha && !run.waitingEmail && !run.waitingBooks}<span class="spin big"></span>{/if}</div>
  {#if captcha}
    {#if paused}
      <div class="banner wait nospin"><div><b>Waiting for the characters.</b><p>KFintech's image may have changed. Continue for a fresh one.</p></div>
        <div class="bact"><button class="btn primary sm" data-primary onclick={() => answer('', true)}>Continue</button></div></div>
    {:else}
      {#key captcha.id}<Captcha image={captcha.image} message={captcha.message} onanswer={answer} />{/key}
    {/if}
  {:else if run.waitingEmail?.months?.length}
    <!-- several months downloaded: every month's email was asked for first, and they are waited for together -->
    <div class="banner wait"><span class="spin amber"></span>
      <div><b>CAMS was asked for {listed(run.waitingEmail.months)}</b><p>CAMS takes a few minutes to send them. Each is read in as it comes. Or stop waiting: they're read in when they come, while the software is open.</p></div>
      <div class="bact"><button class="btn secondary sm" disabled={skipping} onclick={() => { skipping = true; app.skipCams(run.id); }}>{skipping ? 'Stopping…' : "Don't wait"}</button></div></div>
  {:else if run.waitingEmail}
    <div class="banner wait"><span class="spin amber"></span>
      <div><b>CAMS was asked at {hhmm(run.waitingEmail.since)}{run.waitingEmail.ref ? ` · ref ${run.waitingEmail.ref}` : ''}</b><p>CAMS takes a few minutes to send it. The run carries on by itself when it comes.{run.waitingEmail.skip ? " Or skip CAMS: KFintech goes on, and CAMS's email is read when it comes." : ''}</p></div>
      {#if run.waitingEmail.skip}<div class="bact"><button class="btn secondary sm" disabled={skipping} onclick={() => { skipping = true; app.skipCams(run.id); }}>{skipping ? 'Skipping…' : 'Skip CAMS'}</button></div>{/if}</div>
  {/if}
  {#if run.waitingBooks}
    <div class="banner bad" role="alert"><div><b>{waitingLine(run.waitingBooks.kind, run.waitingBooks.company, run.waitingBooks.said)}</b><p>{waitingSub(run.waitingBooks.kind, run.waitingBooks.said)}</p></div>
      <div class="bact"><button class="btn secondary sm" disabled={refreshing} onclick={refreshBooks}>{#if refreshing}<span class="spin"></span>{:else}{@html icons.sync}{/if}Refresh</button></div></div>
  {/if}
  {#if v.done.length}
    <div class="donelist">
      {#each v.done as d (d.name)}<div class="row">{@html icons.drawn}<span>{d.name}</span><span class="f">{d.result}</span></div>{/each}
    </div>
  {/if}
</div>
<div class="rm-foot">
  <button class="btn ghost" disabled={run.stopAsked} onclick={stopNow}>{run.stopAsked ? 'Stopping…' : 'Stop'}</button>
  {#if stuck}<button class="btn secondary" style="margin-left:auto" onclick={onclose}>Close this window</button>{/if}
</div>
