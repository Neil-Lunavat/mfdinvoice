<script lang="ts">
  /* Add CAMS's files: zips and Excels for any months, dropped or chosen at once. The box is cleared when this opens;
     what each call returns is the whole box so far. Done (or Esc) hands the months added back to Downloads. */
  import { app, type CamsFiles } from '../../bridge';
  import { ui } from '../../state/ui.svelte';
  import Modal from '../../ui/Modal.svelte';

  let { done }: { done: (periods: string[]) => void } = $props();

  const NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const MON = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
  const key = (of: string) => { const [m, y] = of.split('-'); return Number(y) * 12 + MON.indexOf(m); };
  const label = (of: string) => `${NAMES[MON.indexOf(of.split('-')[0])]} ${of.split('-')[1]}`;

  let box = $state<CamsFiles>({ added: [], refused: [], waiting: [] });
  let over = $state(false);
  let busy = $state(false);
  let failed = $state('');
  // one line a month (the last pair given for it), the newest month first
  const added = $derived([...new Map(box.added.map(a => [a.period, a])).values()].sort((a, b) => key(b.period) - key(a.period)));

  async function run(go: () => Promise<CamsFiles>) {
    busy = true; failed = '';
    try { box = await go(); } catch { failed = "Couldn't read those files just now. Try again."; }
    busy = false;
  }
  $effect(() => { run(() => app.camsFilesStart()); });

  const base64 = (f: File) => new Promise<string>((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(String(r.result).split(',', 2)[1] ?? '');
    r.onerror = () => rej(r.error);
    r.readAsDataURL(f);
  });
  async function drop(e: DragEvent) {
    e.preventDefault();
    over = false;
    const files = [...(e.dataTransfer?.files ?? [])];
    if (!files.length || busy) return;
    await run(async () => app.dropCamsFiles(await Promise.all(files.map(async f => ({ name: f.name, bytes: await base64(f) })))));
  }
  function close() { done(box.added.map(a => a.period)); ui.close(); }
</script>

<Modal label="Add CAMS's files" onclose={close}>
  <div class="m-bd">
    <div class="work-hd"><div><h3>Add CAMS's files</h3>
      <p class="sub">Drop in all of CAMS's zips and Excels from its emails, for any months, at once.</p></div></div>
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="drop files" class:over ondragover={e => { e.preventDefault(); over = true; }} ondragleave={() => (over = false)} ondrop={drop}>
      {#if busy}<span class="spin"></span>{:else}<b>Drop the files here</b><span>or choose them from where you saved them</span>
        <button class="btn" onclick={() => run(() => app.chooseCamsFiles())}>Choose files</button>{/if}
    </div>
    <div class="cf-res">
      {#each added as a (a.period)}
        <div class="cf-line">{label(a.period)}: {a.count} {a.count === 1 ? 'invoice' : 'invoices'} added</div>
      {/each}
      {#each box.waiting as w}<div class="cf-line muted">{w.name}: {w.why}</div>{/each}
      {#each box.refused as r}<div class="cf-line err">{r.name}: {r.why}</div>{/each}
      {#if box.said}<div class="cf-line err">{box.said}</div>{/if}
      {#if failed}<div class="cf-line err">{failed}</div>{/if}
      {#if box.added.length}<div class="cf-line muted">Download these months to read them in; CAMS won't be asked to email them again.</div>{/if}
    </div>
  </div>
  {#snippet foot()}
    <button class="btn primary" data-primary disabled={busy} onclick={close}>Done</button>
  {/snippet}
</Modal>

<style>
  .cf-res { margin-top: 14px; display: flex; flex-direction: column; gap: 6px; font-size: 13.5px; }
  .cf-line.muted { color: var(--muted); font-size: 12.5px; }
</style>
