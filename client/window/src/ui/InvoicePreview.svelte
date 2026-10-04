<script lang="ts">
  import { NAME } from '../brand';
  /* The person's own invoice, live: laid out and drawn on this PC exactly as a run draws it, with their signature
     where it goes, and shown as its first page. It follows the fields, the signature and its size as they change, a
     moment after the change stops. */
  import { untrack } from 'svelte';
  import { app, type InvoiceSettings, type Signature } from '../bridge';

  let { settings, number, name, gstin, signature = null }: { settings: InvoiceSettings; number: string; name: string; gstin: string; signature?: Signature | null } = $props();

  let big = $state(false);
  let image = $state('');
  let phase = $state<'loading' | 'shown' | 'none'>('loading');
  let seq = 0;

  $effect(() => {
    void signature?.image;                                 // a new photo, or a turned one, is drawn afresh
    const ask = { ...$state.snapshot(settings), name, gstin, signatureSize: signature?.size ?? 100 }, n = number, mine = ++seq;
    phase = untrack(() => image) ? 'shown' : 'loading';
    const t = setTimeout(async () => {
      const got = await app.previewInvoice(ask, n);
      if (mine !== seq) return;
      image = got;
      phase = got ? 'shown' : 'none';
    }, 600);
    return () => clearTimeout(t);
  });
</script>

<div class="invprev" aria-live="polite">
  <div class="label">Preview · an example fund house</div>
  {#if image}
    <div class="pv">
      <button type="button" class="pv-open" aria-label="Full screen" onclick={() => (big = true)}>
        <img src={image} alt="Your invoice, as it will be drawn" class:dim={phase === 'loading'} /></button>
      <button type="button" class="pv-fs" title="Full screen" aria-label="Full screen" onclick={() => (big = true)}>
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/></svg></button>
    </div>
  {:else if phase === 'none'}
    <p class="line">{NAME} couldn't draw the preview. Send this to support.</p>
  {:else}
    <div class="invprev-wait"><span class="spin"></span></div>
  {/if}
</div>

<svelte:window onkeydown={e => { if (big && e.key === 'Escape') { e.stopPropagation(); big = false; } }} />
{#if big && image}
  <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
  <div class="fs" onclick={() => (big = false)}>
    <button class="btn secondary" style="position:fixed;top:16px;right:20px" onclick={() => (big = false)}>Close</button>
    <img src={image} alt="Your invoice, full screen" />
  </div>
{/if}

<style>
  .pv { position: relative; display: inline-block; max-width: 100%; }
  .pv-open { display: block; padding: 0; border: 0; background: none; cursor: zoom-in; }
  .pv-open img { display: block; max-width: 100%; }
  .pv-fs { position: absolute; top: 10px; right: 10px; width: 36px; height: 36px; display: grid; place-items: center; border-radius: 9px;
    border: 1px solid var(--line); background: var(--surface); color: var(--blue); box-shadow: 0 2px 8px rgba(15, 23, 42, .14); cursor: pointer; }
  .pv-fs:hover { background: var(--blue); color: #fff; border-color: var(--blue); }
  .fs { position: fixed; inset: 0; z-index: 1000; background: rgba(20, 22, 30, 0.82); overflow: auto; display: flex; justify-content: center; padding: 56px 24px 24px; }
  .fs img { height: fit-content; width: min(900px, 100%); background: #fff; box-shadow: 0 8px 40px rgba(0, 0, 0, 0.4); }
</style>
