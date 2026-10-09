<script lang="ts">
  /* MFDINVOICE-DEV-PANEL
     DEV ONLY: the test bench's panel in the real window (`uv run app`). App.svelte loads it behind
     `import.meta.env.VITE_DEVAPP === '1'`, which only a checkout's build sets, so the shipped window does not contain
     it (packaging/build.py fails if that marker is in dist/). The fake backend's panel is DevPanel.svelte. */
  import { onMount } from 'svelte';
  import { dev, type DevState } from './appDevTypes';
  import { STEP_TITLES } from '../logic/details';
  import { blankSettings, ui } from '../state/ui.svelte';

  let open = $state(false);
  let st = $state<DevState>({ submit: false, showBrowser: false, states: [], configured: [] });
  let name = $state('');
  let said = $state('');
  let busy = $state(false);

  const refresh = async () => { try { st = await dev.state(); } catch (e) { said = String(e); } };
  onMount(refresh);

  async function act(f: () => Promise<{ ok: boolean; said?: string }>, reload = false) {
    if (busy) return;
    busy = true;
    try {
      const r = await f();
      said = r.said ?? (r.ok ? '' : 'Not done.');
      await refresh();
      if (r.ok && reload) location.reload();     // the window opens again on what is true now
    } catch (e) { said = String(e); }
    busy = false;
  }
  async function toggle(k: 'submit' | 'showBrowser') {
    try { st = await dev.set({ [k]: !st[k] }); } catch (e) { said = String(e); }
  }
  /* On setup, fill every step's draft as if each were verified and stay on Check everything: Finish setup is Neil's. */
  async function fill(): Promise<{ ok: boolean; said?: string }> {
    if (ui.page !== 'setup') return dev.fill();
    const r = await dev.draft();
    if (!r.ok) return r;
    const { signatureImage, invoices, ...rest } = r.draft;
    const last = STEP_TITLES.length - 1;
    ui.draft = {
      ...ui.draft, ...rest,
      signature: { way: 'image', present: true, image: signatureImage, size: 100, cert: null },
      invoices: { ...invoices, settings: { ...blankSettings(), ...invoices.settings } },
      tally: undefined, zoho: undefined
    };
    ui.step = last; ui.reached = last; ui.returnTo = null;
    return { ok: true, said: 'Filled. Books stay unchosen: pick Tally on its step if you want it.' };
  }
  const save = () => { const n = name.trim(); if (n) void act(() => dev.save(n)); };
</script>

{#if !open}
  <button class="tab" data-dev="MFDINVOICE-DEV-PANEL" onclick={() => (open = true)}>dev</button>
{:else}
  <div class="panel" data-dev="MFDINVOICE-DEV-PANEL">
    <div class="head"><b>Dev bench</b><button class="x" onclick={() => (open = false)}>close</button></div>
    <label><input type="checkbox" checked={st.submit} onchange={() => toggle('submit')} /> Submit real</label>
    <label><input type="checkbox" checked={st.showBrowser} onchange={() => toggle('showBrowser')} /> Show browser</label>
    <div class="row">
      <button disabled={busy} onclick={() => act(dev.backToSetup, true)}>Back to setup</button>
      <button disabled={busy} onclick={() => act(fill, ui.page !== 'setup')}>Fill everything</button>
    </div>
    <div class="row">
      <input placeholder="state name" bind:value={name} onkeydown={e => { if (e.key === 'Enter') save(); }} />
      <button disabled={busy || !name.trim()} onclick={save}>Save</button>
    </div>
    {#each st.states as s (s)}
      <div class="state">
        <span>{s}</span>
        <button disabled={busy} onclick={() => act(() => dev.load(s), true)}>Load</button>
        <button disabled={busy} onclick={() => act(() => dev.remove(s))}>Delete</button>
      </div>
    {/each}
    {#if said}<p class="said">{said}</p>{/if}
  </div>
{/if}

<style>
  .tab, .panel { position: fixed; left: 8px; bottom: 8px; z-index: 2000; font: 11.5px system-ui, sans-serif; color: #e2e8f0; background: rgba(15, 23, 42, .92); }
  .tab { padding: 3px 9px; border: 0; border-radius: 8px; opacity: .55; cursor: pointer; }
  .tab:hover { opacity: 1; }
  .panel { width: 240px; padding: 8px; border-radius: 10px; display: flex; flex-direction: column; gap: 6px; }
  .head { display: flex; justify-content: space-between; align-items: center; }
  label { display: flex; align-items: center; gap: 6px; }
  .row, .state { display: flex; gap: 4px; align-items: center; }
  .state span { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  button, input:not([type]) { height: 24px; padding: 0 8px; border-radius: 6px; border: 0; font: inherit; color: #fff; background: rgba(255, 255, 255, .12); }
  input:not([type]) { flex: 1; min-width: 0; }
  button:hover:not(:disabled) { background: rgba(255, 255, 255, .24); }
  button:disabled { opacity: .5; }
  .x { background: none; }
  .said { margin: 0; color: #fcd34d; white-space: pre-wrap; }
</style>
