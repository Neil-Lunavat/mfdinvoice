<script lang="ts">
  /* Your books, optional: Tally on this PC or Zoho Books, one per ARN. Tally: the company chosen while TallyPrime is
     open. Zoho Books: let in through the person's own browser, then the organisation chosen, each with its GSTIN seen
     beside this ARN's. Nothing is written to either here. Skipped, the Books tab asks the first time it is opened. */
  import { onMount } from 'svelte';
  import { app, type ProfileDraft, type TallySetup, type ZohoOrg } from '../../bridge';
  import { connectZoho } from '../../logic/zoho';
  import { icons } from '../../ui/icons';

  let { d = $bindable() }: { d: ProfileDraft } = $props();
  let kind = $state<'' | 'tally' | 'zoho' | 'none'>(d.zoho?.org ? 'zoho' : d.tally?.company ? 'tally' : '');
  let look = $state<TallySetup | null>(null);
  let busy = $state(false);
  let orgs = $state<ZohoOrg[] | null>(null);       // null: not let in yet
  let waiting = $state(false);                      // Zoho's Accept page is open in the browser
  let said = $state('');

  async function readTally() {
    if (busy) return;
    busy = true;
    const got = await app.booksSetup({ kind: 'tally', gstin: d.gstin, arn: d.arn });
    look = { state: got.state, companies: got.companies };
    busy = false;
    // the company chosen before is kept only while Tally still has it open
    if (d.tally?.company && look.state === 'ready' && !look.companies.some(c => c.guid === d.tally!.guid)) d.tally = undefined;
    if (look.state === 'ready' && !d.tally?.company) {
      const mine = look.companies.filter(c => c.same);
      if (mine.length === 1) pickCompany(mine[0]);
      else if (look.companies.length === 1) pickCompany(look.companies[0]);
    }
  }
  function pickCompany(c: TallySetup['companies'][number]) {
    d.tally = { company: c.name, guid: c.guid, gstin: c.gstin, same: c.same, sure: false };
  }
  function pickOrg(o: ZohoOrg) {
    d.zoho = { orgId: o.id, org: o.name, gstin: o.gstin, same: o.same, sure: false };
  }

  async function connect() {
    if (waiting) return;
    waiting = true;
    said = '';
    try {
      const r = await connectZoho(d.arn, d.gstin);
      if (!r.ok) { said = r.cancelled ? '' : r.said; return; }
      orgs = r.orgs;
      const mine = r.orgs.filter(o => o.same);
      if (mine.length === 1) pickOrg(mine[0]);
      else if (r.orgs.length === 1) pickOrg(r.orgs[0]);
    } catch (e) {
      said = e instanceof Error && e.message ? e.message : "Zoho Books isn't answering. Try again.";
    } finally {
      waiting = false;
    }
  }
  function cancel() { void app.zohoCancel(); }

  function choose(k: 'tally' | 'zoho' | 'none') {
    if (k === kind) return;
    const was = kind;
    kind = k;
    said = '';
    if (k !== 'zoho') {
      d.zoho = undefined;
      orgs = null;
      if (was === 'zoho') void app.zohoDisconnect(d.arn);      // the grant is let go of at Zoho
    }
    if (k !== 'tally') d.tally = undefined;
    if (k === 'tally') void readTally();
  }
  onMount(() => { if (kind === 'tally') void readTally(); });
</script>

<p class="line">Each month's invoices can go into your books. This step is optional: you can connect your books later, from the Books tab.</p>

<div class="field"><span class="flabel">Which books do you keep?</span>
  <div class="tcs">
    <button type="button" class="tile tc" class:on={kind === 'tally'} aria-pressed={kind === 'tally'} onclick={() => choose('tally')}>
      <b>Tally</b><span>TallyPrime on this PC</span></button>
    <button type="button" class="tile tc" class:on={kind === 'zoho'} aria-pressed={kind === 'zoho'} onclick={() => choose('zoho')}>
      <b>Zoho Books</b><span>Opens Zoho in your browser, for you to accept</span></button>
    <button type="button" class="tile tc" class:on={kind === 'none'} aria-pressed={kind === 'none'} onclick={() => choose('none')}>
      <b>Neither, for now</b><span>You can connect one later</span></button>
  </div>
</div>

{#if kind === 'tally'}
  {#if !look}
    <div class="testrow"><span class="spin"></span></div>
  {:else if look.state !== 'ready'}
    <div class="detected enter"><div><b>{look.state === 'closed' ? 'No company is open in TallyPrime' : "Tally isn't open"}</b>
      <span>{look.state === 'closed' ? 'Open your company in TallyPrime, then look again.' : 'To connect it, open TallyPrime and your company, then look again. Or continue without it.'}</span></div>
      <button class="btn secondary sm" disabled={busy} onclick={readTally}>{#if busy}<span class="spin"></span>{:else}{@html icons.sync}{/if}Refresh</button></div>
    {#if look.state === 'off'}
      <p class="line">The first time: in TallyPrime press F1 (Help) › Settings › Connectivity › Client/Server configuration. Set "TallyPrime acts as" to Both and the port to 9000, then close TallyPrime and open it again.</p>
    {/if}
  {:else}
    <div class="field"><span class="flabel">{look.companies.length > 1 ? 'Which company do these invoices go into?' : 'Tally is open'}</span>
      <div class="tcs">
        {#each look.companies as c (c.guid)}
          <button type="button" class="tile tc" class:on={d.tally?.guid === c.guid} aria-pressed={d.tally?.guid === c.guid} onclick={() => pickCompany(c)}>
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
    {/if}
    <div class="testrow"><button class="btn ghost sm" disabled={busy} onclick={readTally}>{#if busy}<span class="spin"></span>{:else}{@html icons.sync}{/if}Refresh</button></div>
  {/if}
{:else if kind === 'zoho'}
  {#if waiting}
    <div class="detected enter"><div><b>Waiting for Zoho in your browser</b>
      <span>Sign in to Zoho if it asks, then press Accept. Come back here when it says you can close the tab.</span></div>
      <button class="btn secondary sm" onclick={cancel}>Cancel</button></div>
  {:else if !orgs}
    {#if said}<div class="banner wait nospin" role="alert"><div>{said}</div></div>{/if}
    {#if d.zoho?.org}<div class="testrow"><span class="okl">{@html icons.tickSm}Connected to {d.zoho.org}</span></div>{/if}
    <div class="testrow"><button class="btn secondary" onclick={connect}>{d.zoho?.org ? 'Connect again' : 'Connect Zoho Books'}</button>
      <span class="line">Your browser opens at Zoho. The software is only let into your Zoho Books, and you can let go of it in Settings.</span></div>
  {:else}
    <div class="field"><span class="flabel">{orgs.length > 1 ? 'Which organisation do these invoices go into?' : 'Zoho Books is connected'}</span>
      <div class="tcs">
        {#each orgs as o (o.id)}
          <button type="button" class="tile tc" class:on={d.zoho?.orgId === o.id} aria-pressed={d.zoho?.orgId === o.id} onclick={() => pickOrg(o)}>
            <b>{o.name}</b><span class="mono">{o.gstin || 'No GSTIN in Zoho Books'}</span></button>
        {/each}
      </div>
    </div>
    {#if d.zoho?.org}
      {#if d.zoho.same}
        <div class="testrow"><span class="okl">{@html icons.tickSm}{d.zoho.org}'s GSTIN in Zoho Books is yours: {d.gstin}</span></div>
      {:else}
        <div class="banner wait nospin" role="alert"><div><b>{d.zoho.org}'s GSTIN in Zoho Books is {d.zoho.gstin || 'not set'}. Yours here is {d.gstin}.</b>
          Choose another organisation, or say this is the one.</div></div>
        <label class="check"><input type="checkbox" bind:checked={d.zoho.sure} /> This is the right organisation</label>
      {/if}
    {/if}
  {/if}
{/if}

<style>
  .flabel { font-size: 13px; font-weight: 500; color: var(--ink-2); }
  .tcs { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 6px; }
  .tc { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; min-width: 240px; text-align: left; }
  .tc span { font-size: 12.5px; color: var(--muted); }
</style>
