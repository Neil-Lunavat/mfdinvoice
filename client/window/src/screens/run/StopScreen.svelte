<script lang="ts">
  /* Stopped, inside the run window: what stopped it (the portal's own words in quotes), what each registrar got to,
     and what the person can do. The run is over: Close, or Run again for the stops running again can help. A sign-in
     that belongs to another ARN, and a mailbox that can't be read, are put right here before running again. Which
     stop offers what: logic/stops.ts. */
  import type { Stop } from '../../bridge';
  import { stopScreen } from '../../logic/stops';
  import { ui } from '../../state/ui.svelte';
  import { icons } from '../../ui/icons';
  import Editor from '../setup/Editor.svelte';

  let { stop, onclose, onagain }: { stop: Stop; onclose: () => void; onagain: () => void } = $props();

  const sc = $derived(stopScreen(stop));
  let fixing = $state<'cams' | 'kf' | 'mb' | null>(null);
  const FIX = { cams: 'Change CAMS email', kf: 'Change KFintech login', mb: 'Fix mailbox' };
</script>

{#if fixing}
  <Editor which={fixing} layout="run" ondone={() => (fixing = null)} />
{:else}
  <div class="rm-stage">
    <div class="stop-hd"><span class="tick big {sc.mark === 'bad' ? 'no' : sc.mark}">{@html sc.mark === 'stop' ? icons.stop : sc.mark === 'ok' ? icons.tickSm : icons.bang}</span>
      <div><h3>{sc.title}</h3>{#if sc.quote}<div class="q">{#each sc.quote.split('\n') as q (q)}<div>“{q}”</div>{/each}</div>{/if}</div></div>
    {#each sc.lines as l (l)}<p class="line">{l}</p>{/each}
    {#if sc.fix.length}
      <div class="cklist">
        {#each sc.fix as f (f)}
          <div class="ck"><span class="v">{f === 'cams' ? 'The CAMS email this ARN signs in with' : f === 'kf' ? 'The KFintech login this ARN signs in with' : 'The mailbox CAMS sends to'}</span>
            <a href="#change" onclick={e => { e.preventDefault(); fixing = f; }}>{FIX[f]}</a></div>
        {/each}
      </div>
      {#if stop.kind === 'arn_mismatch'}<p class="line">To run a different ARN, add it from the ARN menu at the top left.</p>{/if}
    {/if}
    {#if stop.so_far}<div class="sofar"><div class="label">This run</div><div>{stop.so_far}</div></div>{/if}
  </div>
  <div class="rm-foot">
    {#if sc.again}<button class="btn primary" data-primary onclick={onagain}>{@html icons.playFill}Run again</button>{/if}
    <button class="btn {sc.again ? 'secondary' : 'primary'}" data-primary={sc.again ? undefined : ''} onclick={onclose}>Close</button>
    {#if sc.support}
      <button class="btn ghost" style="margin-left:auto" onclick={() => ui.open({ type: 'support', where: `Run stopped: ${sc.kind}` })}>{@html icons.help}Send to support</button>
    {/if}
  </div>
{/if}
