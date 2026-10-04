<script lang="ts">
  /* (?) beside a field: where to find the value. */
  let { text }: { text: string } = $props();
  let open = $state(false);
</script>

<button class="qh" type="button" aria-label="Where to find it" aria-expanded={open} onclick={e => { e.preventDefault(); open = !open; }}>?</button>
{#if open}<div class="pop enter" role="note"><div class="shot"></div><span>{text}</span></div>{/if}
