<script lang="ts">
  /* Before a run starts. On the person's own invoices, one question: is this still the last invoice number in their
     books? (They may have issued invoices of their own since.) When their Tally is open on this PC its own last
     number is shown beside it, and the person still says which is right. On the registrar's invoices nothing is
     asked, and the run starts at once; so do a status check and a download. The mailbox clash holds a run until it
     is settled. */
  import { onMount } from 'svelte';
  import { app, type NextNumber, type Registrar, type RunKind } from '../../bridge';
  import { blocksRun } from '../../logic/clash';
  import { bump, counterOf } from '../../logic/numbering';
  import { store } from '../../state/store.svelte';
  import { ui } from '../../state/ui.svelte';
  import { icons } from '../../ui/icons';
  import Editor from '../setup/Editor.svelte';
  import LastNumberEditor from './LastNumber.svelte';

  let { registrars, period, what, onclose }: { registrars: Registrar[]; period: string; what: RunKind; onclose: () => void } = $props();

  const p = $derived(store.snap!.profile!);
  const held = $derived(what !== 'check' && blocksRun(ui.clash, registrars));
  const own = $derived(what === 'run' && p.invoices.source === 'own');
  let editing = $state<'last' | 'mb' | null>(null);
  let starting = $state(false);

  let changed = $state<NextNumber | null>(null);
  const last = $derived<NextNumber>(changed ?? { text: p.invoices.last.trim(), at: counterOf(p.invoices.last.trim(), p.invoices.at) });
  const next = $derived(last.text ? bump(last.text, last.at) : '');
  // what Tally says its last invoice is, when it is open on this PC
  let tally = $state<{ company: string; last: string } | null>(null);
  const differs = $derived(!!tally && tally.last !== last.text);

  // Keeping the old mailbox settles the clash, and the app remembers it is settled.
  async function keep() { await app.saveDetails({ mailbox: $state.snapshot(p.mailbox) }); ui.clash = null; }

  async function start() {
    if (held || starting || (own && !next)) return;
    starting = true;
    const r = await app.startRun({ registrars, period, what, last: own ? last : null });
    if (!r.run) { store.toast(r.said || "It couldn't start just now."); onclose(); return; }
    store.beginRun(r.run, registrars, what, period);
  }
  onMount(() => {
    if (own) void app.tallyLast().then(r => { if (r.state === 'ready' && r.last) tally = { company: r.company, last: r.last }; });
    if (!own && !held) void start();
  });
</script>

{#if editing === 'last'}
  <LastNumberEditor value={last} ondone={(v: NextNumber | null) => { if (v) changed = v; editing = null; }} />
{:else if editing === 'mb'}
  <Editor which="mb" layout="run" ondone={() => (editing = null)} />
{:else if own || held}
  <div class="rm-stage">
    {#if own}
      <div class="work-hd"><div><h3>{tally ? 'Is this your last invoice number in Tally?' : 'Is this still your last invoice number?'}</h3>
        <p class="sub">The last one in your books. Change it if you have issued invoices of your own since the last run.</p></div></div>
      <div class="cklist">
        <div class="ck"><span class="k">Your last invoice</span><span class="v mono">{last.text || '—'}</span>
          <a href="#change" onclick={e => { e.preventDefault(); editing = 'last'; }}>Change</a></div>
        {#if tally}
          <div class="ck"><span class="k">Tally's last invoice</span><span class="v mono">{tally.last} <span class="line">· {tally.company}</span></span>
            {#if differs}<a href="#use" onclick={e => { e.preventDefault(); changed = { text: tally!.last, at: counterOf(tally!.last, -1) }; }}>Use this</a>
            {:else}<span class="line">The same</span>{/if}</div>
        {/if}
        <div class="ck"><span class="k">This run starts at</span><span class="v mono">{next || '—'}</span></div>
      </div>
    {/if}
    {#if held && ui.clash}
      <div class="banner wait nospin" role="alert"><div><b>Your mailbox is still {ui.clash.mailbox}.</b>
        <p>CAMS's email is now {ui.clash.camsEmail}. CAMS sends its invoice mails there, so the run won't find them in {ui.clash.mailbox}.</p></div>
        <div class="bact"><button class="btn secondary sm" onclick={keep}>Keep {ui.clash.mailbox}</button>
          <button class="btn primary sm" onclick={() => (editing = 'mb')}>Change mailbox</button></div></div>
    {/if}
  </div>
  <div class="rm-foot">
    <button class="btn ghost" onclick={onclose}>Not now</button>
    <button class="btn primary" data-primary style="margin-left:auto" disabled={held || starting || (own && !next)} onclick={start}>
      {@html icons.playFill}{own ? 'Yes, run' : 'Run'}</button>
  </div>
{:else}
  <div class="rm-stage"><div class="work-hd"><div><h3>Starting</h3></div><span class="spin big"></span></div></div>
  <div class="rm-foot"></div>
{/if}
