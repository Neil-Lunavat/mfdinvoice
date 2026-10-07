<script lang="ts">
  /* Tally, optional: the company this ARN's invoices go into, chosen while TallyPrime is open, with its GSTIN seen
     beside this ARN's. Nothing is written to Tally here. Skipped, the Tally tab asks the first time it is opened. */
  import { onMount } from 'svelte';
  import { app, type ProfileDraft, type TallySetup } from '../../bridge';
  import { icons } from '../../ui/icons';

  let { d = $bindable() }: { d: ProfileDraft } = $props();
  let look = $state<TallySetup | null>(null);
  let busy = $state(false);

  async function read() {
    if (busy) return;
    busy = true;
    look = await app.tallySetup(d.gstin);
    busy = false;
    // the company chosen before is kept only while Tally still has it open
    if (d.tally?.company && look.state === 'ready' && !look.companies.some(c => c.guid === d.tally!.guid)) d.tally = undefined;
    if (look.state === 'ready' && !d.tally?.company) {
      const mine = look.companies.filter(c => c.same);
      if (mine.length === 1) pick(mine[0]);
      else if (look.companies.length === 1) pick(look.companies[0]);
    }
  }
  function pick(c: TallySetup['companies'][number]) {
    d.tally = { company: c.name, guid: c.guid, gstin: c.gstin, same: c.same, sure: false };
  }
  onMount(read);
</script>

<p class="line">Each month's invoices can go into your books, in the TallyPrime on this PC. This step is optional: you can connect Tally later, from the Tally tab.</p>

{#if !look}
  <div class="testrow"><span class="spin"></span></div>
{:else if look.state !== 'ready'}
  <div class="detected enter"><div><b>{look.state === 'closed' ? 'No company is open in TallyPrime' : "Tally isn't open"}</b>
    <span>{look.state === 'closed' ? 'Open your company in TallyPrime, then look again.' : 'To connect it, open TallyPrime and your company, then look again. Or continue without it.'}</span></div>
    <button class="btn secondary sm" disabled={busy} onclick={read}>{#if busy}<span class="spin"></span>{:else}{@html icons.sync}{/if}Refresh</button></div>
  {#if look.state === 'off'}
    <p class="line">The first time: in TallyPrime press F1 (Help) › Settings › Connectivity › Client/Server configuration. Set "TallyPrime acts as" to Both and the port to 9000, then close TallyPrime and open it again.</p>
  {/if}
{:else}
  <div class="field"><span class="flabel">{look.companies.length > 1 ? 'Which company do these invoices go into?' : 'Tally is open'}</span>
    <div class="tcs">
      {#each look.companies as c (c.guid)}
        <button type="button" class="tile tc" class:on={d.tally?.guid === c.guid} aria-pressed={d.tally?.guid === c.guid} onclick={() => pick(c)}>
          <b>{c.name}</b><span class="mono">{c.gstin || 'No GSTIN in Tally'}</span></button>
      {/each}
    </div>
  </div>
  {#if d.tally?.company}
    {#if d.tally.same}
      <div class="testrow"><span class="okl">{@html icons.tickSm}{d.tally.company}'s GSTIN in Tally is yours: {d.gstin}</span></div>
    {:else}
      <div class="banner wait nospin" role="alert"><div><b>{d.tally.company}'s GSTIN in Tally is {d.tally.gstin || 'not set'}. Yours here is {d.gstin}.</b>
        Choose another company, or say this is the one.</div></div>
      <label class="check"><input type="checkbox" bind:checked={d.tally.sure} /> This is the right company</label>
    {/if}
    <a href="#notally" class="small-link" onclick={e => { e.preventDefault(); d.tally = undefined; }}>Don't connect Tally now</a>
  {/if}
  <div class="testrow"><button class="btn ghost sm" disabled={busy} onclick={read}>{#if busy}<span class="spin"></span>{:else}{@html icons.sync}{/if}Refresh</button></div>
{/if}

<style>
  .flabel { font-size: 13px; font-weight: 500; color: var(--ink-2); }
  .tcs { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 6px; }
  .tc { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; min-width: 240px; text-align: left; }
  .tc span { font-size: 12.5px; color: var(--muted); }
</style>
