<script lang="ts">
  import { ui } from '../../state/ui.svelte';
  import MonthView from './MonthView.svelte';
  import Year from './Year.svelte';
</script>

{#if ui.invoicesMonth}
  {#key ui.invoicesMonth}<MonthView period={ui.invoicesMonth} />{/key}
{:else}
  <Year />
{/if}
