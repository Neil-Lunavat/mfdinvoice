<script lang="ts">
  /* This app must update: a full screen before anything else (#25). It shows only once no run is going on this PC.
     [Update now] downloads, checks and installs; the app closes and the new version opens where the person was. */
  import { app, type UpdateFailure } from '../bridge';
  import { NAME } from '../brand';
  import { store } from '../state/store.svelte';
  import { icons } from '../ui/icons';

  const why = $derived(store.snap?.update?.why ?? '');
  const failed = $derived(!!store.snap?.update?.failed);

  const WORDS: Record<UpdateFailure, string> = {
    unreachable: "The update couldn't be downloaded. Check your internet connection, then try again.",
    missing: "The update isn't ready to download just yet. Try again in a few minutes.",
    mismatch: "The download didn't arrive whole, so it wasn't used. Try again.",
    no_plan: 'Your plan has ended. Renew it on the website, then update.',
    signed_out: `You've been signed out. Close ${NAME}, open it and sign in again, then update.`,
    not_installed: `This copy of ${NAME} wasn't installed with its installer, so it can't update itself.`,
    failed: "The update couldn't start. Try again."
  };

  function update() { store.updateError = null; store.updatePct = 0; app.updateNow(); }
</script>

<div class="view signin" data-layer="page">
  <div class="col enter" style="text-align:center;align-items:center">
    <span class="mark">{@html icons.mark(22)}</span>
    <div><h1>A required update is ready</h1><p class="sub">{why} About 1 min.</p></div>
    <div style="width:100%">
      {#if store.updatePct === null}
        <button class="btn primary lg" data-primary style="width:100%" onclick={update}>{store.updateError ? 'Try again' : 'Update now'}</button>
        {#if store.updateError}
          <p class="line" style="margin-top:8px">{WORDS[store.updateError]}</p>
        {:else if failed}
          <p class="line" style="margin-top:8px">The last update didn't start, so {NAME} went back to this version.</p>
        {/if}
      {:else}
        <div class="updbar" role="progressbar" aria-valuenow={store.updatePct} aria-valuemin={0} aria-valuemax={100} aria-label="Updating"><i style="width:{store.updatePct}%"></i></div>
        <p class="line" style="margin-top:8px">{store.updatePct < 100 ? 'Downloading' : `Installing. ${NAME} will close and open again.`}</p>
      {/if}
    </div>
    <p class="foot">Your data and settings stay as they are.</p>
  </div>
</div>
