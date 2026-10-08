<script lang="ts">
  /* The network toast: top right, on every screen, until the network is back. The software retries by itself
     (1, 5, 10, 30 s, then every 2 min); "reconnect" checks at once. */
  import { onMount } from 'svelte';
  import { app } from '../bridge';
  import { store } from '../state/store.svelte';

  let now = $state(Date.now());
  let busy = $state(false);

  onMount(() => {
    const t = setInterval(() => (now = Date.now()), 1000);
    return () => clearInterval(t);
  });

  const net = $derived(store.snap?.network);
  const left = $derived(net ? Math.ceil((net.retryAt - now) / 1000) : 0);
  const when = $derived(busy || left <= 0 ? 'Retrying…' : left >= 60 ? 'Retrying in 2 min' : `Retrying in ${left}s`);

  async function reconnect(e: MouseEvent) {
    e.preventDefault();
    if (busy) return;
    busy = true;
    try { await app.reconnect(); } finally { busy = false; }
  }
</script>

{#if net && !net.online}
  <div class="nettoast" role="alert"><b>Network not connected.</b> {when} · <a href="#reconnect" class="ul" onclick={reconnect}>reconnect</a></div>
{/if}

<style>
  .nettoast{position:fixed;top:16px;right:16px;z-index:90;padding:10px 14px;border-radius:10px;border:1px solid var(--red-line);background:var(--red-wash);color:#912018;font-size:13.5px;box-shadow:var(--e-sheet)}
  .nettoast a{color:inherit;text-decoration:underline;text-underline-offset:2px;cursor:pointer}
</style>
