<script lang="ts">
  import { store } from '../state/store.svelte';
</script>

<div class="toastzone" role="status" aria-live="polite">
  {#each store.toastQueue as t (t.id)}
    <div class="toast">{t.text}</div>
  {/each}
</div>
