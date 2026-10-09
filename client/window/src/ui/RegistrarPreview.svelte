<script lang="ts">
  import { NAME } from '../brand';
  /* An example of a registrar's own invoice, made out to this person, with their signature where a run puts it. The
     layout is the registrar's real one; the fund house's figures are made up. It follows the signature and its size
     as they change, a moment after the change stops. */
  import { untrack } from 'svelte';
  import { app, type Signature } from '../bridge';

  let { kind, name, gstin, arn, signature, way = '', certName = '' }: { kind: 'cams' | 'kfintech'; name: string; gstin: string; arn: string; signature: Signature; way?: string; certName?: string } = $props();

  let big = $state(false);
  let image = $state('');
  let phase = $state<'loading' | 'shown' | 'none'>('loading');
  let seq = 0;

  $effect(() => {
    void signature.image;                                  // a new photo, or a turned one, is drawn afresh
    // the way on screen: a USB token's mark is drawn where a run stamps it, never signed
    const ask = { kind, name, gstin, arn, signatureSize: signature.size, way: way || signature.way, certName: certName || signature.cert?.name || '' }, mine = ++seq;
    phase = untrack(() => image) ? 'shown' : 'loading';
    const t = setTimeout(async () => {
      const got = await app.previewRegistrar(ask);
      if (mine !== seq) return;
      image = got;
      phase = got ? 'shown' : 'none';
    }, 500);
    return () => clearTimeout(t);
  });
</script>

<div class="invprev" aria-live="polite">
  <div class="label">{kind === 'cams' ? "CAMS's invoice" : "KFintech's invoice"} · an example{#if image}<button class="btn ghost sm" style="float:right" onclick={() => (big = true)}>Full screen</button>{/if}</div>
  {#if image}
    <img src={image} alt="An example of the registrar's invoice, with your signature" class:dim={phase === 'loading'} />
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
    <img src={image} alt="The example invoice, full screen" />
  </div>
{/if}

<style>
  .fs { position: fixed; inset: 0; z-index: 1000; background: rgba(20, 22, 30, 0.82); overflow: auto; display: flex; justify-content: center; padding: 56px 24px 24px; }
  .fs img { height: fit-content; width: min(900px, 100%); background: #fff; box-shadow: 0 8px 40px rgba(0, 0, 0, 0.4); }
</style>
