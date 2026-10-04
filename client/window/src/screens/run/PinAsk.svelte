<script lang="ts">
  /* A USB token's PIN, typed here (Window.pin): only for a token whose own software cannot ask for it. The PIN goes
     to the token and is kept nowhere; a wrong one shows the token's own words. Cancel signs nothing. */
  import { onMount } from 'svelte';
  import type { Ask } from '../../bridge';
  import { store } from '../../state/store.svelte';
  import { icons } from '../../ui/icons';

  let { ask }: { ask: Extract<Ask, { type: 'pin' }> } = $props();
  let value = $state('');
  let field: HTMLInputElement;
  onMount(() => setTimeout(() => field.focus(), 50));
</script>

<div class="rm-stage">
  <div class="work-hd"><div><h3>Type your token's PIN</h3><p class="sub">Your invoices are signed with your USB token. It asks for its PIN once for this run.</p></div></div>
  <div class="field"><label for="pin">Token PIN</label>
    <div class="secret"><input bind:this={field} id="pin" type="password" class="input" style="max-width:220px" bind:value autocomplete="off" />
      <span class="lock">{@html icons.lock}Never saved</span></div>
    {#if ask.said}<span class="err">{ask.said}</span>{/if}</div>
</div>
<div class="rm-foot">
  <button class="btn ghost" onclick={() => store.answerRun({ type: 'pin', value: null })}>Cancel</button>
  <button class="btn primary" data-primary style="margin-left:auto" disabled={!value} onclick={() => store.answerRun({ type: 'pin', value })}>Sign</button>
</div>
