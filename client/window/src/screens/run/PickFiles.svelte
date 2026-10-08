<script lang="ts">
  /* CAMS's invoice files, from the person: the zip of invoices and the Excel report, out of the email CAMS has just
     been asked to send. Dropped here, or each opened from wherever it was saved. Nothing is checked by name: the run
     reads what is inside, and says so if they are not this month's. With KFintech in the same run, CAMS can be
     skipped instead: the run carries on with KFintech alone. */
  import { app, type Ask } from '../../bridge';
  import { store } from '../../state/store.svelte';
  import { icons } from '../../ui/icons';

  let { ask }: { ask: Extract<Ask, { type: 'pick_files' }> } = $props();

  let zip = $state('');
  let xls = $state('');
  let over = $state(false);
  let reading = $state(false);

  function took(r: { kind: string; name: string }) {
    if (r.kind === 'zip' && r.name) zip = r.name;
    else if (r.kind === 'xls' && r.name) xls = r.name;
  }
  async function pick(kind: 'zip' | 'xls') { took(await app.pickFile(kind)); }

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
    if (!files.length) return;
    reading = true;
    for (const f of files) {
      try {
        const r = await app.dropFile({ name: f.name, bytes: await base64(f) });
        if (r.kind) took(r); else store.toast(`${f.name} isn't a zip or an Excel file.`);
      } catch { store.toast(`${f.name} couldn't be read.`); }
    }
    reading = false;
  }
</script>

<div class="rm-stage" data-ask={ask.id}>
  <div class="work-hd"><div><h3>Add CAMS's invoice files</h3>
    <p class="sub">CAMS has emailed {ask.month}'s invoices{ask.sentTo ? ` to ${ask.sentTo}` : ''}. Save the zip and the Excel from that email, then add both here.</p></div></div>
  {#if ask.message}<p class="err" role="alert">{ask.message}</p>{/if}
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="drop files" class:over ondragover={e => { e.preventDefault(); over = true; }} ondragleave={() => (over = false)} ondrop={drop}>
    {#if reading}<span class="spin"></span>{:else}<b>Drop the zip and the Excel here</b><span>or open each one below</span>{/if}
  </div>
  <div class="field"><span class="label">Zip of invoices</span>
    <div class="sentline">{#if zip}{@html icons.tickSm}<b>{zip}</b>{:else}Not added yet{/if}<a href="#zip" onclick={e => { e.preventDefault(); pick('zip'); }}>{zip ? 'Change' : 'Open zip'}</a></div></div>
  <div class="field"><span class="label">Excel report</span>
    <div class="sentline">{#if xls}{@html icons.tickSm}<b>{xls}</b>{:else}Not added yet{/if}<a href="#xls" onclick={e => { e.preventDefault(); pick('xls'); }}>{xls ? 'Change' : 'Open Excel'}</a></div></div>
</div>
<div class="rm-foot">
  <button class="btn ghost" onclick={() => { if (store.run) { store.run.stopAsked = true; app.stopRun(store.run.id); } }}>Stop</button>
  {#if ask.skip}<button class="btn ghost" onclick={() => store.answerRun({ type: 'pick_files', skip: true })}>Skip CAMS</button>{/if}
  <button class="btn primary" data-primary style="margin-left:auto" disabled={!zip || !xls}
    onclick={() => store.answerRun({ type: 'pick_files' })}>Continue</button>
</div>
