<script lang="ts">
  /* A popup over the window. Esc and a click outside close it (App's keyboard handler finds the top one);
     Tab stays inside it while it is open. */
  import type { Snippet } from 'svelte';
  import { onMount } from 'svelte';

  let { onclose, wide = false, label, children, foot }: {
    onclose: () => void; wide?: boolean; label: string; children: Snippet; foot?: Snippet;
  } = $props();

  let box: HTMLDivElement;
  const back = document.activeElement as HTMLElement | null;

  onMount(() => {
    const first = box.querySelector<HTMLElement>('input:not([disabled]),textarea,select,[data-primary]:not([disabled]),button:not([disabled])');
    setTimeout(() => first?.focus(), 60);
    return () => back?.focus?.();
  });

  function trap(e: KeyboardEvent) {
    if (e.key !== 'Tab') return;
    const all = [...box.querySelectorAll<HTMLElement>('a[href],button:not([disabled]),input:not([disabled]),textarea,select,[tabindex="0"]')];
    if (!all.length) return;
    const first = all[0], last = all[all.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="modal-ov" data-layer="popup" onclick={e => { if (e.target === e.currentTarget) onclose(); }} onkeydown={trap}>
  <div class="modal" class:wide2={wide} role="dialog" aria-modal="true" aria-label={label} bind:this={box}>
    {@render children()}
    {#if foot}<div class="m-ft">{@render foot()}</div>{/if}
  </div>
</div>
