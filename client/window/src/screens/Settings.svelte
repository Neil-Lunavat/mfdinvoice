<script lang="ts">
  import { NAME } from '../brand';
  /* Settings, one section at a time (#20). Each Change opens the setup control in a popup. History sits in the
     middle (#19). Leaving Your invoices with unsaved changes asks: Save · Discard · Cancel. */
  import { app, type ProfileDraft } from '../bridge';
  import { dayMon, dayMonYear, hhmm } from '../logic/format';
  import { noFreeSlot, planLine } from '../logic/plan';
  import { invoicesLine, invoicesStepValid, mailboxLine } from '../logic/details';
  import { panOf, stateOf } from '../logic/validate';
  import { store } from '../state/store.svelte';
  import { SECTIONS, ui, type Detail } from '../state/ui.svelte';
  import { icons } from '../ui/icons';
  import History from './History.svelte';
  import YourInvoices from './setup/YourInvoices.svelte';

  const s = $derived(store.snap!);
  const p = $derived(s.profile!);
  const edit = (which: Detail) => ui.open({ type: 'edit', which });

  // Your invoices: what goes on the invoice and the signature, edited in place beside the real invoice, saved or
  // discarded together
  const draftOf = (): ProfileDraft => {
    const q = store.snap!.profile!;
    return { arn: q.arn, name: q.name, gstin: q.gstin, camsUsed: q.camsUsed, camsEmail: q.camsEmail, camsArn: q.camsArn, mailbox: { ...q.mailbox },
      kfintech: { ...q.kfintech }, signature: { ...q.signature }, invoices: structuredClone($state.snapshot(q.invoices)), consent: q.consent,
      tally: q.books ? { company: q.tally.company, guid: '', gstin: q.tally.gstin ?? '', same: true, sure: true } : undefined };
  };
  let inv = $state<ProfileDraft>(draftOf());
  const sigDirty = $derived(inv.signature.image !== p.signature.image || inv.signature.size !== p.signature.size);
  const invDirty = $derived(JSON.stringify(inv.invoices) !== JSON.stringify(p.invoices) || sigDirty);
  $effect(() => { ui.settingsDirty = invDirty; ui.saveSettings = invDirty ? saveInvoice : null; ui.discardSettings = invDirty ? discard : null; });
  async function saveInvoice() {
    const r = await app.saveDetails({ invoices: $state.snapshot(inv.invoices), ...(sigDirty ? { signature: $state.snapshot(inv.signature) } : {}) });
    store.toast(r.ok ? 'Saved' : r.said);
    if (r.ok) inv = draftOf();
  }
  function discard() { void app.dropSignatureDraft(); inv = draftOf(); }
  // a Change to which invoice is uploaded comes back through the store: start the form again from it
  let seenSource = $state(store.snap!.profile!.invoices.source);
  $effect(() => { if (p.invoices.source !== seenSource) { seenSource = p.invoices.source; inv = draftOf(); } });

  let testing = $state(false);
  async function testMailbox() {
    testing = true;
    const r = await app.testMailbox({ provider: p.mailbox.provider, address: p.mailbox.address, appPassword: '' });
    testing = false;
    store.toast(r.ok ? `Connected · ${r.found} CAMS invoice mails in the last 30 days` : r.said);
  }
  async function camsOff(off: boolean) {
    const r = await app.saveDetails({ camsUsed: !off });
    store.toast(!r.ok ? r.said : off ? 'CAMS hidden for this ARN.' : 'CAMS back on. Add its email to use it.');
    if (r.ok && !off) edit('cams');
  }
  async function kfintechOff(off: boolean) {
    await app.saveDetails({ kfintech: { ...p.kfintech, used: !off } });
    store.toast(off ? 'KFintech hidden for this ARN.' : 'KFintech back on.');
  }
  let updating = $state(false);
  async function checkUpdates() {
    updating = true;
    const r = await app.checkForUpdates();
    updating = false;
    store.toast(r.upToDate ? 'Up to date' : 'An update is on its way');
  }
  // Windows' own uninstaller asks to confirm; the software closes so it can be removed
  async function uninstall() { const why = await app.uninstall(); if (why) store.toast('Uninstall works in the installed software, not in a checkout.'); }
  // Send an idea: the words and a picture they chose, to us; nothing comes back but the thanks
  let idea = $state(''), picture = $state<{ name: string; data: string } | null>(null), ideaFile = $state<HTMLInputElement | null>(null);
  let sendingIdea = $state(false), ideaSaid = $state('');
  function takePicture(f?: File) {
    ideaSaid = '';
    if (!f) return;
    if (f.size > 5 * 1024 * 1024) { ideaSaid = 'That picture is over 5 MB. Choose a smaller one.'; return; }
    const r = new FileReader();
    r.onload = () => (picture = { name: f.name, data: String(r.result) });
    r.readAsDataURL(f);
  }
  async function sendIdea() {
    sendingIdea = true; ideaSaid = '';
    const r = await app.sendIdea({ text: idea.trim(), picture: picture ?? undefined });
    sendingIdea = false;
    if (!r.sent) { ideaSaid = "It didn't send. Check the internet connection and try again."; return; }
    idea = ''; picture = null;
    store.toast('Sent. Thank you!');
  }
</script>

{#snippet row(k: string, v: string, mono = false)}<span class="k">{k}</span><span class="v" class:mono>{v}</span>{/snippet}

<div class="page-in fit setpage enter">
  <div class="mhd"><div><h1>Settings</h1><p class="sub">{p.arn} · {p.name}</p></div></div>
  <div class="setgrid">
    <nav class="setnav" aria-label="Settings sections">
      {#each SECTIONS as x (x)}
        <button class:on={x === ui.section} aria-current={x === ui.section ? 'page' : undefined} onclick={() => ui.goSection(x)}>{x}</button>
      {/each}
    </nav>
    <div class="setbody">
      <h3>{ui.section}</h3>
      {#if ui.section === 'Connections'}
        <div class="sgroup"><div class="sg-h"><b>CAMS</b>
            {#if p.camsUsed}<span class="chip {p.lastLogin.CAMS || p.camsArn ? 'good' : 'neutral'}">{p.lastLogin.CAMS ? `Last login ${dayMon(p.lastLogin.CAMS)}` : p.camsArn ? 'Verified at setup' : 'Not verified'}</span>{/if}</div>
          {#if p.camsUsed}
            <div class="srow">{@render row('Email', p.camsEmail)}<button class="btn ghost sm" onclick={() => edit('cams')}>Change</button></div>
          {/if}
          <label class="switch srow"><span>I don't use CAMS</span><input type="checkbox" checked={!p.camsUsed} disabled={p.camsUsed && !p.kfintech.used} onchange={e => camsOff(e.currentTarget.checked)} /></label>
        </div>
        {#if p.camsUsed}
        <div class="sgroup"><div class="sg-h"><b>Mailbox</b><span class="chip {p.mailbox.connected ? 'good' : 'bad'}">{p.mailbox.connected ? 'Connected' : 'Not connected'}</span></div>
          <div class="srow">{@render row(p.mailbox.provider === 'folder' ? 'No mailbox' : p.mailbox.provider === 'forward' ? 'Forwarded' : 'Gmail', mailboxLine(p.mailbox).replace(/^Gmail · /, ''))}
            {#if p.mailbox.provider === 'gmail'}<button class="btn ghost sm" disabled={testing} onclick={testMailbox}>{testing ? 'Verifying…' : 'Verify connection'}</button>{/if}
            <button class="btn ghost sm" onclick={() => edit('mb')}>Change</button></div>
          {#if p.mailbox.provider === 'gmail'}<div class="srow"><span class="k">App password</span><span class="v">•••• •••• •••• •••• <span class="lock">{@html icons.lock}This PC only</span></span></div>{/if}
        </div>
        {/if}
        <div class="sgroup"><div class="sg-h"><b>KFintech</b>
            {#if p.kfintech.used}<span class="chip good">{p.lastLogin.KFINTECH ? `Logged in ${dayMon(p.lastLogin.KFINTECH)}` : 'Verified at setup'}</span>{/if}</div>
          {#if p.kfintech.used}
            <div class="srow">{@render row('Username', p.kfintech.username, true)}<button class="btn ghost sm" onclick={() => edit('kf')}>Change</button></div>
            <div class="srow"><span class="k">Password</span><span class="v">•••••••• <span class="lock">{@html icons.lock}This PC only</span></span></div>
          {/if}
          <label class="switch srow"><span>I don't use KFintech</span><input type="checkbox" checked={!p.kfintech.used} disabled={p.kfintech.used && !p.camsUsed} onchange={e => kfintechOff(e.currentTarget.checked)} /></label>
        </div>
        <div class="sgroup"><div class="sg-h"><b>Tally</b>{#if p.tally.company}<span class="chip good">In use</span>{/if}</div>
          {#if p.tally.company}
            <div class="srow"><span class="k">Company</span><span class="v">{p.tally.company} <span class="line">· {p.tally.ledgers} fund {p.tally.ledgers === 1 ? 'house' : 'houses'} matched to its ledgers</span></span>
              <button class="btn ghost sm" onclick={async () => { await app.tallyForget(); store.toast('Forgotten. The Tally tab asks which company next time.'); }}>Change</button></div>
            <div class="srow"><span class="k">GSTIN</span><span class="v"><span class="mono">{p.tally.gstin || 'Not read yet'}</span> <span class="line">in Tally · yours: <span class="mono">{p.gstin}</span></span>
              {#if p.tally.gstin && p.tally.gstin !== p.gstin}<span class="chip wait">Not the same</span>{/if}</span></div>
          {:else}
            <p class="line" style="padding-bottom:12px">Each month's invoices go into the TallyPrime open on this PC. <a href="#tally" onclick={e => { e.preventDefault(); ui.go('tally'); }}>Open the Tally tab</a></p>
          {/if}</div>
        <div class="sgroup muted"><div class="sg-h"><b>Zoho Books</b><span class="tag later">Coming soon</span></div><p class="line" style="padding-bottom:12px">Import each month's invoices into your books.</p></div>
      {:else if ui.section === 'Your details'}
        <div class="sgroup">
          <div class="srow"><span class="k">ARN</span><span class="v"><span class="mono">{p.arn}</span>
            <span class="line">{#if p.arnConfirmed}· confirmed by your portal login · Wrong? <a href="#support" onclick={e => { e.preventDefault(); ui.open({ type: 'support', where: 'Settings › Your details: the ARN is wrong' }); }}>Contact support</a>{:else}· not confirmed yet{/if}</span></span></div>
          <div class="srow">{@render row('GSTIN', p.gstin, true)}<button class="btn ghost sm" onclick={() => edit('who')}>Change</button></div>
          <div class="srow"><span class="k">PAN · State</span><span class="v"><span class="mono">{panOf(p.gstin)}</span> · {stateOf(p.gstin)}</span></div>
          <div class="srow">{@render row('Name on invoices', p.name)}<button class="btn ghost sm" onclick={() => edit('who')}>Change</button></div>
        </div>
        <div class="sgroup"><div class="sg-h"><b>Your authority</b></div>
          {#if p.consent}
            <div class="srow"><span class="k">You agreed</span><span class="v">“{p.consent.text}”</span></div>
            <div class="srow">{@render row('When', `${dayMonYear(p.consent.at)}, ${hhmm(p.consent.at)}${p.consent.device ? ` · on ${p.consent.device}` : ''}`)}</div>
          {:else}
            <div class="srow">{@render row('Not confirmed yet', `${NAME} needs your say-so to act on CAMS and KFintech for this ARN.`)}
              <button class="btn secondary sm" onclick={() => ui.open({ type: 'consent' })}>Confirm</button></div>
          {/if}
        </div>
      {:else if ui.section === 'Your invoices'}
        <div class="sgroup">
          <div class="srow">{@render row('Uploaded', invoicesLine(p.invoices, !!p.books))}<button class="btn ghost sm" onclick={() => edit('inv')}>Change</button></div>
        </div>
        <div class="sgroup"><YourInvoices bind:d={inv} settingsOnly />
          <div class="savebar" class:is-dirty={invDirty}><span class="dirty">Unsaved changes</span>
            <button class="btn ghost sm" disabled={!invDirty} onclick={discard}>Discard</button>
            <button class="btn primary sm" data-primary disabled={!invDirty || !invoicesStepValid(inv)} onclick={saveInvoice}>Save</button></div>
        </div>
      {:else if ui.section === 'History'}
        <History />
      {:else if ui.section === 'Account & plan'}
        <div class="sgroup">
          <div class="srow">{@render row('Signed in as', s.account?.email ?? '')}</div>
          <div class="srow">{@render row('Plan', planLine(s.plan) || 'Not checked yet')}<button class="btn ghost sm" onclick={() => app.open('billing')}>Manage on the website</button></div>
          <div class="srow">{@render row('This PC', 'Signing out keeps your invoice files here.')}<button class="btn ghost sm" onclick={() => ui.open({ type: 'sign_out' })}>Sign out</button></div>
        </div>
        <div class="sgroup"><div class="sg-h"><b>ARNs on this PC</b>{#if s.plan?.state === 'active'}<span class="line">Your plan has {s.plan.slots} ARN {s.plan.slots === 1 ? 'slot' : 'slots'}</span>{/if}</div>
          {#each s.arns as a (a.arn)}
            <div class="srow"><span class="k mono">{a.arn}</span><span class="v">{a.name}</span>{#if a.arn === s.arn}<span class="chip neutral">This ARN</span>{/if}</div>
          {/each}
          <div class="srow">{#if s.arns.length >= (s.account?.maxArns ?? 6)}<span class="line">For more than {s.account?.maxArns ?? 6} ARNs, talk to us.</span>
            {:else if noFreeSlot(s.plan, s.arns.map(a => a.arn))}<span class="line">Every ARN slot on your plan is in use.</span>
              <button class="btn secondary sm" onclick={() => app.open('billing')}>Add ARNs on the website</button>
            {:else}<button class="btn secondary sm" onclick={() => ui.startSetup(true)}>Add ARN</button>{/if}</div>
        </div>
      {:else if ui.section === 'This PC'}
        <div class="sgroup"><div class="srow">{@render row('Files', "Every month's invoices, signed, kept on this PC")}<button class="btn ghost sm" onclick={() => app.openFolder('files')}>Open folder</button></div>
          <div class="srow">{@render row(`Uninstall ${NAME}`, "Removes the software from this PC. Your invoices, settings and saved passwords stay here, so a new install picks up where you left off.")}
            <button class="btn ghost sm" disabled={!!s.run} onclick={uninstall}>Uninstall</button></div></div>
      {:else if ui.section === 'Support'}
        <div class="sgroup">
          <div class="srow">{@render row('Something went wrong?', "We see what the software was doing and where it stopped. Never your passwords, signature or mailbox.")}
            <button class="btn secondary sm" onclick={() => ui.open({ type: 'support', where: 'Settings › Support' })}>Send to support</button></div>
          <div class="srow">{@render row('Help', 'How a month works · Connect Gmail · KFintech captcha · When a fund house rejects')}<button class="btn ghost sm" onclick={() => app.open('help')}>Open help</button></div>
          <div class="srow"><span class="k">Version</span><span class="v"><span class="mono">v{s.version}</span> · Up to date</span>
            <button class="btn ghost sm" disabled={updating} onclick={checkUpdates}>{updating ? 'Checking…' : 'Check for updates'}</button></div>
        </div>
      {:else if ui.section === 'Send an idea'}
        <div class="sgroup idea">
          <p class="line">Something that would make {NAME} better for you? Write it here. We read every idea ourselves.</p>
          <textarea class="input" rows="7" maxlength="4000" placeholder="Your idea" bind:value={idea}></textarea>
          <div class="idea-row">
            <input bind:this={ideaFile} type="file" accept="image/png,image/jpeg,image/webp" hidden onchange={() => takePicture(ideaFile?.files?.[0])} />
            {#if picture}
              <span class="line">{picture.name}</span><button class="btn ghost sm" onclick={() => (picture = null)}>Remove</button>
            {:else}
              <button class="btn ghost sm" onclick={() => ideaFile?.click()}>Add a picture</button><span class="line">optional, a screenshot helps</span>
            {/if}
            <button class="btn primary sm" style="margin-left:auto" disabled={sendingIdea || !idea.trim()} onclick={sendIdea}>{sendingIdea ? 'Sending…' : 'Send idea'}</button>
          </div>
          {#if ideaSaid}<p class="err">{ideaSaid}</p>{/if}
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .idea { display: flex; flex-direction: column; gap: 10px; padding-top: 12px; padding-bottom: 14px; }
  .idea textarea { width: 100%; height: auto; padding: 10px 12px; resize: vertical; }
  .idea-row { display: flex; align-items: center; gap: 10px; }
</style>
