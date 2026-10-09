<script lang="ts">
  /* Stopped, inside the run window: what stopped it (the portal's own words in quotes), what each registrar got to,
     and what the person can do. The run is over: Close, or Run again for the stops running again can help. A sign-in
     that belongs to another ARN, and a mailbox that can't be read, are put right here before running again. Which
     stop offers what: logic/stops.ts. */
  import type { Entered as EnteredRow, Left, Stop } from '../../bridge';
  import { regName } from '../../logic/format';
  import { stopScreen } from '../../logic/stops';
  import { ui } from '../../state/ui.svelte';
  import { icons } from '../../ui/icons';
  import Editor from '../setup/Editor.svelte';
  import Entered from './Entered.svelte';

  let { stop, enter = [], left = [], notes = [], onclose, onagain }: { stop: Stop; enter?: EnteredRow[]; left?: Left[]; notes?: string[]; onclose: () => void; onagain: () => void } = $props();

  const sc = $derived(stopScreen(stop));
  // both registrars stopped: one heading, and each registrar's stop in its own block (Neil, 8 Oct)
  const all = $derived(stop.others?.length ? [stop, ...stop.others].map(s => ({ reg: s.registrar, sc: stopScreen(s) })) : []);
  const again = $derived(all.length ? all.some(a => a.sc.again) : sc.again);
  const support = $derived(all.length ? all.some(a => a.sc.support) : sc.support);
  let fixing = $state<'cams' | 'kf' | 'mb' | null>(null);
  const FIX = { cams: 'Change CAMS email', kf: 'Change KFintech login', mb: 'Fix mailbox' };
</script>

{#if fixing}
  <Editor which={fixing} layout="run" ondone={() => (fixing = null)} />
{:else}
  <div class="rm-stage">
    {#if all.length}
    <div class="stop-hd"><span class="tick big no">{@html icons.bang}</span>
      <div><h3>{all.map(a => a.reg ? regName(a.reg) : '').filter(Boolean).join(' and ')} both stopped</h3></div></div>
    {#each all as a, i (i)}
      <div class="stop-one">
        <div class="label">{a.reg ? regName(a.reg) : 'This run'}</div>
        <h4>{a.sc.title}</h4>
        {#if a.sc.quote}<div class="q">{#each a.sc.quote.split('\n') as q (q)}<div>“{q}”</div>{/each}</div>{/if}
        {#each a.sc.lines as l (l)}<p class="line">{l}</p>{/each}
      </div>
    {/each}
    {:else}
    <div class="stop-hd"><span class="tick big {sc.mark === 'bad' ? 'no' : sc.mark}">{@html sc.mark === 'stop' ? icons.stop : sc.mark === 'ok' ? icons.tickSm : icons.bang}</span>
      <div><h3>{sc.title}</h3>{#if sc.quote}<div class="q">{#each sc.quote.split('\n') as q (q)}<div>“{q}”</div>{/each}</div>{/if}</div></div>
    {#each sc.lines as l (l)}<p class="line">{l}</p>{/each}
    {/if}
    {#if sc.fix.length}
      <div class="cklist">
        {#each sc.fix as f (f)}
          <div class="ck"><span class="v">{f === 'cams' ? 'The CAMS email this ARN signs in with' : f === 'kf' ? 'The KFintech login this ARN signs in with' : 'The mailbox CAMS sends to'}</span>
            <a href="#change" onclick={e => { e.preventDefault(); fixing = f; }}>{FIX[f]}</a></div>
        {/each}
      </div>
      {#if stop.kind === 'arn_mismatch'}<p class="line">To run a different ARN, add it from the ARN menu at the top left.</p>{/if}
    {/if}
    <Entered {enter} {left} />
    {#if notes.length}
      <div class="sofar"><div class="label">Along the way</div>
        <ul>{#each notes as n (n)}<li class="line">{n}</li>{/each}</ul></div>
    {/if}
    {#if stop.so_far && !all.length}<div class="sofar"><div class="label">This run</div><div>{stop.so_far}</div></div>{/if}
  </div>
  <div class="rm-foot">
    {#if again}<button class="btn primary" data-primary onclick={onagain}>{@html icons.playFill}Run again</button>{/if}
    <button class="btn {again ? 'secondary' : 'primary'}" data-primary={again ? undefined : ''} onclick={onclose}>Close</button>
    {#if support}
      <button class="btn ghost" style="margin-left:auto" onclick={() => ui.open({ type: 'support', where: `Run stopped: ${sc.kind}` })}>{@html icons.help}Send to support</button>
    {/if}
  </div>
{/if}
