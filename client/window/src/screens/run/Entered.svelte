<script lang="ts">
  /* The end of a run, for own invoices: what was submitted without books, to enter in the person's own books with
     these invoice numbers; and what the books would not take this run. */
  import type { Entered, Left } from '../../bridge';
  import { ENTER_HEAD, LEFT_HEAD } from '../../logic/books';
  import { regName } from '../../logic/format';

  let { enter, left }: { enter: Entered[]; left: Left[] } = $props();
</script>

{#if enter.length}
  <div class="donelist">
    <div class="label">{ENTER_HEAD}</div>
    {#each enter as e (e.key)}<div class="row"><span>{e.amc} <span class="line">· {regName(e.registrar)}</span></span><span class="f mono">{e.number}</span></div>{/each}
  </div>
{/if}
{#if left.length}
  <div class="donelist">
    <div class="label">{LEFT_HEAD}</div>
    {#each left as l (l.amc + l.why)}<div class="row"><span>{l.amc}</span><span class="f">{l.why}</span></div>{/each}
  </div>
{/if}
