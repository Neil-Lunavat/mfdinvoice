<script lang="ts">
  /* Settings › History: every action, who did it and on which PC. Permanent and uneditable. */
  import type { ActivityEntry } from '../bridge';
  import { dayMonth, hhmm, regTag } from '../logic/format';
  import { store } from '../state/store.svelte';

  let reg = $state<'All' | 'CAMS' | 'KFINTECH'>('All');
  const list = $derived((store.snap?.activity ?? []).filter(e => reg === 'All' || !e.registrar || e.registrar === reg));
  const days = $derived.by(() => {
    const out: [string, ActivityEntry[]][] = [];
    for (const e of list) {
      const d = dayMonth(e.at), last = out.at(-1);
      if (last && last[0] === d) last[1].push(e); else out.push([d, [e]]);
    }
    return out;
  });
</script>

<p class="sub" style="margin-bottom:10px">Everything done and approved on this account, by whom and on which PC. It can't be edited.</p>
<div class="filters" style="margin-bottom:10px"><div class="seg" role="group" aria-label="Registrar">
  {#each ['All', 'CAMS', 'KFINTECH'] as const as r (r)}
    <button class:on={reg === r} aria-pressed={reg === r} onclick={() => (reg = r)}>{r === 'KFINTECH' ? 'KFintech' : r}</button>
  {/each}
</div></div>
<div class="alist">
  {#each days as [d, es] (d)}
    <div class="aday"><div class="label">{d}</div>
      {#each es as e, i (i)}
        <div class="ar" class:bad={e.tone === 'bad'} class:set={e.tone === 'setting'}>
          <span class="at mono">{hhmm(e.at)}</span>
          <span class="as">{e.text}{#if e.who}{' '}<span class="aw">· {e.who}</span>{/if}</span>
          {#if e.registrar}<span class="reg">{regTag(e.registrar)}</span>{/if}
        </div>
      {/each}
    </div>
  {:else}
    <p class="line" style="padding:12px 0">Nothing yet.</p>
  {/each}
</div>
