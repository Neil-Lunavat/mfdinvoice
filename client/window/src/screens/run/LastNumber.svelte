<script lang="ts">
  /* Change the last invoice number in your books, in place, before a run: the person may have issued invoices of
     their own since the last run, and this is the one moment a clash is still cheap to avoid. The number exactly as
     printed, and the part that goes up by 1, as at setup. The run starts at the one after it. */
  import { untrack } from 'svelte';
  import type { NextNumber } from '../../bridge';
  import { below, bump, counterOf, parts, rule46 } from '../../logic/numbering';

  let { value, floor = '', ondone }: { value: NextNumber; floor?: string; ondone: (last: NextNumber | null) => void } = $props();

  let text = $state(untrack(() => value.text));
  let at = $state(untrack(() => value.at));
  const segs = $derived(parts(text));
  const counting = $derived(counterOf(text, at));
  const next = $derived(counting >= 0 ? bump(text.trim(), counterOf(text.trim(), at)) : '');
  const refused = $derived(rule46(text));
  // it may skip ahead, never go below the highest this software has used this financial year
  const tooLow = $derived(!!floor && below(text, counterOf(text.trim(), at), floor));
  const ok = $derived(!!next && !refused && !tooLow);
</script>

<div class="rm-stage">
  <div class="work-hd"><div><h3>Your last invoice number</h3>
    <p class="sub">Exactly as printed on the last invoice in your books.</p></div></div>
  <div class="field">
    <label for="last">Last invoice number</label>
    <input id="last" class="input mono" style="max-width:300px" value={text}
      oninput={e => { text = e.currentTarget.value; at = counterOf(text, -1); }} />
    {#if segs.some(p => p.digits)}
      <div class="segs"><span class="hint">Which part goes up by 1?</span>
        <div class="segrow">
          {#each segs as p (p.start)}
            {#if p.digits}<button type="button" class="seg-t" class:on={p.start === counting} onclick={() => (at = p.start)}>{p.text}</button>
            {:else}<span class="seg-f">{p.text}</span>{/if}
          {/each}
        </div></div>
    {/if}
    {#if refused}<span class="err" role="alert">{refused}</span>{/if}
    {#if tooLow}<span class="err" role="alert">{floor} has already been used this financial year, so this can't be lower than that.</span>{/if}
    {#if next && !refused}<div class="derived"><span>This run starts at <b>{next}</b></span></div>{/if}
  </div>
</div>
<div class="rm-foot">
  <button class="btn ghost" onclick={() => ondone(null)}>Cancel</button>
  <button class="btn primary" data-primary style="margin-left:auto" disabled={!ok}
    onclick={() => ondone({ text: text.trim(), at: counterOf(text.trim(), at) })}>Save</button>
</div>
