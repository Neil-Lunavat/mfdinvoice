<script lang="ts">
  /* One invoice's own PDF, small, for the invoice popup: the signed one once it is signed, else the registrar's as it
     came. Never a drawing of one (Neil, 9 Oct): with no file on this PC, it says so. */
  import { app } from '../bridge';

  let { key }: { key: string } = $props();

  let pdf = $state('');
  let looked = $state(false);
  $effect(() => { const k = key; pdf = ''; looked = false; app.preview(k).then(u => { if (k === key) { pdf = u; looked = true; } }); });
</script>

{#if pdf}
  <img class="page small full" src={pdf} alt="The invoice" />
{:else if looked}
  <p class="line">This invoice's file isn't on this PC yet. The next run or download gets it.</p>
{/if}
