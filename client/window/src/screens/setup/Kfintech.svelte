<script lang="ts">
  /* KFintech: the authority tick (in setup), then Verify login, which asks for the captcha in place. KFintech shows
     one ARN per login. In setup the first portal verified sets the ARN and this one must show the same; a sign-in that
     does (or "I don't use KFintech") unlocks Continue. */
  import { app, type ProfileDraft } from '../../bridge';
  import { consentNow, consentText } from '../../logic/consent';
  import { mismatchLine, reread, sameArn } from '../../logic/details';
  import { store } from '../../state/store.svelte';
  import { ui } from '../../state/ui.svelte';
  import Captcha from '../../ui/Captcha.svelte';
  import { icons } from '../../ui/icons';
  import Help from './Help.svelte';

  let { d = $bindable(), saved = '' }: { d: ProfileDraft; saved?: string } = $props();
  let pw = $state('');
  let busy = $state(false);
  let said = $state('');
  let failed = $state(false);
  let ours = $state(false);
  let changed = $state(false);              // KFintech's page misbehaved twice in a row

  const filled = $derived(d.kfintech.username.trim().length > 2 && pw.length > 2);
  const inSetup = $derived(ui.page === 'setup');
  const other = $derived(!!d.kfintech.loggedInAs && !sameArn(d.kfintech.arn, d.arn));   // it logged in, as another ARN
  const ticked = $derived(!inSetup || !!d.ticks?.kfintech);
  const dup = $derived(inSetup && sameArn(d.kfintech.arn, d.arn) && !!store.snap?.arns.some(a => sameArn(a.arn, d.arn)));
  const edited = () => { d.kfintech.loggedInAs = ''; d.kfintech.arn = ''; said = ''; failed = false; changed = false; if (inSetup) { reread(d, 'KFintech'); ui.read.kf = ''; ui.read.gstin = ''; } };

  async function test() {
    busy = true; edited();
    const r = await app.testKfintech({ username: d.kfintech.username.trim(), password: pw, expect: d.arn });
    busy = false;
    store.setupCaptcha = null;
    if (r.ok) {
      d.kfintech.loggedInAs = r.as; d.kfintech.arn = r.arn;
      if (inSetup) {
        if (!d.arn) d.arn = r.arn;
        if (sameArn(r.arn, d.arn)) { ui.read.kf = r.name; ui.read.gstin = r.gstin; ui.read.version++; }   // another ARN's name is never taken
      }
    }
    else { said = r.said; ours = !!r.ours; changed = !!r.changed; failed = !!r.said || !r.ours; }
  }
  function skip() { d.kfintech.used = false; edited(); if (d.ticks) d.ticks.kfintech = null; }
  function answer(text: string, refresh: boolean) {
    const q = store.setupCaptcha;
    if (!q) return;
    store.setupCaptcha = null;
    app.answer(q.id, { type: 'captcha', text, refresh });
  }
</script>

{#if !d.kfintech.used}
  <div class="detected enter"><div><b>KFintech is hidden for this ARN</b><span>You can turn it back on in Settings.</span></div>
    <a href="#use" onclick={e => { e.preventDefault(); d.kfintech.used = true; }}>I use KFintech</a></div>
  {#if inSetup && !sameArn(d.camsArn, d.arn)}
    <p class="line">Without KFintech, CAMS confirms your ARN: verify your CAMS email before you finish.</p>
  {/if}
{:else}
  <div class="field"><label for="ku">Username <Help text="The username you use on the KFintech distributor site" /></label>
    <input id="ku" class="input mono" style="max-width:300px" bind:value={d.kfintech.username} oninput={edited} /><span class="hint">{saved ? `Saved on this PC: ${saved}. Type it to verify a new login.` : 'Your KFintech distributor login'}</span></div>
  <div class="field"><label for="kp">Password</label>
    <div class="secret"><input id="kp" type="password" class="input" style="max-width:300px" bind:value={pw} oninput={edited} />
      <span class="lock">{@html icons.lock}This PC only</span></div></div>
  {#if inSetup}
    <label class="check consent"><input type="checkbox" checked={!!d.ticks?.kfintech}
      onchange={e => { d.ticks = { cams: d.ticks?.cams ?? null, kfintech: e.currentTarget.checked ? consentNow(['KFintech']) : null }; }} /> {consentText(['KFintech'])}</label>
  {/if}
  <div class="testrow"><button class="btn secondary" disabled={!filled || !ticked || busy} onclick={test}>Verify login</button>
    {#if busy && !store.setupCaptcha}<span class="spin"></span>
    {:else if other}<span class="err">{mismatchLine(d, 'KFintech', inSetup)}</span>
    {:else if d.kfintech.loggedInAs}<span class="okl">{@html icons.tickSm}Logged in as {d.kfintech.loggedInAs} · {d.kfintech.arn}</span>
      {#if dup}<span class="err">{d.arn} is already set up in this software.</span>{/if}
    {:else if changed}<span class="err">{said} {#if d.camsUsed}You can <a href="#skip" onclick={e => { e.preventDefault(); skip(); }}>skip KFintech for now</a> and continue with CAMS, or you can{:else}You can{/if}
      <a href="#support" onclick={e => { e.preventDefault(); ui.open({ type: 'support', where: 'Setup, KFintech: its sign-in page misbehaved twice' }); }}>send to support</a> and we'll fix it as soon as possible.</span>
    {:else if said}<span class="err">{ours ? said : `KFintech says: “${said}”`}</span>
    {:else if failed}<span class="err">KFintech couldn't be reached just now.</span>{/if}</div>
  {#if store.setupCaptcha}
    <Captcha image={store.setupCaptcha.image} message={store.setupCaptcha.message} onanswer={answer} />
  {/if}
  {#if d.camsUsed}<a href="#nokf" class="small-link" onclick={e => { e.preventDefault(); skip(); }}>I don't use KFintech</a>{/if}
{/if}
