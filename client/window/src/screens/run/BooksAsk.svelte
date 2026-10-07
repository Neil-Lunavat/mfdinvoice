<script lang="ts">
  /* The books' questions, asked once in a run, before Your check: Tally's kind of sales voucher, which ledger or
     customer is a fund house, whether the company or organisation is the person's. Each answer is remembered. */
  import { app, type Ask } from '../../bridge';
  import { optionText } from '../../logic/books';
  import { store } from '../../state/store.svelte';

  let { ask }: { ask: Extract<Ask, { type: 'books_ask' }> } = $props();

  let picked = $state<Record<string, string>>({});
  const done = $derived(ask.asks.every(a => !!picked[a.id]));
  function stop() { if (store.run) { store.run.stopAsked = true; app.stopRun(store.run.id); } }
</script>

<div class="rm-stage">
  <div class="work-hd"><div><h3>Your books need an answer</h3>
    <p class="sub">Asked once. Your answers are remembered for this ARN.</p></div></div>
  {#each ask.asks as a (a.id)}
    <div class="field">
      <span class="label">{a.question}</span>
      <div class="seg" role="radiogroup" aria-label={a.question} style="flex-wrap:wrap;height:auto">
        {#each a.options as o (o)}
          <button type="button" role="radio" aria-checked={picked[a.id] === o} class:on={picked[a.id] === o}
            onclick={() => (picked = { ...picked, [a.id]: o })}>{optionText(o)}</button>
        {/each}
      </div>
    </div>
  {/each}
</div>
<div class="rm-foot">
  <button class="btn ghost" onclick={stop}>Stop</button>
  <button class="btn primary" data-primary style="margin-left:auto" disabled={!done}
    onclick={() => store.answerRun({ type: 'books_ask', answers: { ...picked } })}>Continue</button>
</div>
