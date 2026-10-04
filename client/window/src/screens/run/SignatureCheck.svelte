<script lang="ts">
  /* The first run ever for an ARN: one real invoice signed the person's way before anything else is signed, "Does
     this look right?" Fix my signature changes it in place; the app then signs the same invoice again and asks again.
     Nothing else is signed until the person says it looks right, and it is never asked again for this ARN. */
  import { app, type Ask } from '../../bridge';
  import { store } from '../../state/store.svelte';
  import Editor from '../setup/Editor.svelte';

  let { ask }: { ask: Extract<Ask, { type: 'signature' }> } = $props();

  let fixing = $state(false);
  let page = $state('');
  $effect(() => { const k = ask.key; page = ''; app.preview(k).then(u => { if (k === ask.key) page = u; }); });
</script>

{#if fixing}
  <Editor which="sig" layout="run" ondone={saved => { fixing = false; if (saved) store.answerRun({ type: 'signature', looksRight: false, fixed: true }); }} />
{:else}
  <div class="rm-stage">
    <div class="work-hd"><div><h3>Does this look right?</h3>
      <p class="sub">{ask.amc}'s invoice, with your signature on it. The rest are signed the same way once you say it looks right.</p></div></div>
    {#if page}<img class="page small full" src={page} alt="{ask.amc}'s invoice, signed" />
    {:else}<div class="page small full" aria-busy="true"><span class="spin"></span></div>{/if}
  </div>
  <div class="rm-foot">
    <button class="btn ghost" onclick={() => store.answerRun({ type: 'signature', looksRight: false, fixed: false })}>Stop</button>
    <button class="btn secondary" onclick={() => (fixing = true)}>Fix my signature</button>
    <button class="btn primary" data-primary style="margin-left:auto" onclick={() => store.answerRun({ type: 'signature', looksRight: true, fixed: false })}>It looks right</button>
  </div>
{/if}
