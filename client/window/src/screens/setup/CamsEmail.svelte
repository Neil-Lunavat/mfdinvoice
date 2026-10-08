<script lang="ts">
  /* CAMS: the email, the authority tick (in setup), and a sign-in that verifies it by reading the ARN CAMS shows.
     In setup the first portal verified sets the ARN; this one must then show the same. In a Change the ARN is the
     ARN's own. Or "I don't use CAMS": CAMS is left out of every run. */
  import { app, type ProfileDraft } from '../../bridge';
  import { consentNow, consentText } from '../../logic/consent';
  import { mismatchLine, reread, sameArn } from '../../logic/details';
  import { store } from '../../state/store.svelte';
  import { ui } from '../../state/ui.svelte';
  import { emailOk } from '../../logic/validate';
  import { icons } from '../../ui/icons';
  import Help from './Help.svelte';

  let { d = $bindable(), signInEmail, saved = '' }: { d: ProfileDraft; signInEmail: string; saved?: string } = $props();
  let same = $state(false);
  let touched = $state(false);
  let busy = $state(false);
  let said = $state('');
  let failed = $state(false);
  let ours = $state(false);
  let changed = $state(false);              // CAMS's page misbehaved twice in a row
  let typed = '';                           // what was typed before "Same as my sign-in email", back when it is unticked
  let field = $state<HTMLInputElement>();
  const bad = $derived(touched && !!d.camsEmail && !emailOk(d.camsEmail));
  const inSetup = $derived(ui.page === 'setup');
  const edited = () => { d.camsArn = ''; said = ''; failed = false; changed = false; if (inSetup) { reread(d, 'CAMS'); ui.read.cams = ''; } };
  const ticked = $derived(!inSetup || !!d.ticks?.cams);
  const dup = $derived(inSetup && sameArn(d.camsArn, d.arn) && !!store.snap?.arns.some(a => sameArn(a.arn, d.arn)));

  function skip() { d.camsUsed = false; d.camsEmail = ''; same = false; edited(); if (d.ticks) d.ticks.cams = null; }

  async function test() {
    busy = true; edited();
    const r = await app.testCams({ email: d.camsEmail.trim() });
    busy = false;
    if (r.ok) {
      d.camsArn = r.arn;
      if (inSetup) { if (!d.arn) d.arn = r.arn; ui.read.cams = r.name; ui.read.version++; }
    }
    else { said = r.said; ours = !!r.ours; changed = !!r.changed; failed = true; }
  }
</script>

{#if inSetup}
  <div class="need"><b>About 10 minutes.</b> Keep these handy: your CAMS email, your KFintech login, your mailbox, and your signature image or DSC token.</div>
{/if}
{#if !d.camsUsed}
  <div class="detected enter"><div><b>CAMS is hidden for this ARN</b><span>You can turn it back on in Settings.</span></div>
    <a href="#use" onclick={e => { e.preventDefault(); d.camsUsed = true; }}>I use CAMS</a></div>
{:else}
<div class="field">
  <label for="ce">CAMS email <Help text="The email CAMS sends your brokerage mails to" /></label>
  <input bind:this={field} id="ce" class="input" type="email" disabled={same} bind:value={d.camsEmail} class:bad
    oninput={() => { edited(); if (d.camsEmail.trim().length > 3) touched = true; }} onblur={() => { if (d.camsEmail) touched = true; }} />
  {#if bad}<span class="err">Incomplete email</span>
  {:else if saved}<span class="hint">Saved on this PC: {saved}. Type the new one.</span>
  {:else}<span class="hint">The email registered with CAMS</span>{/if}
</div>
<label class="check"><input type="checkbox" bind:checked={same}
  onchange={() => { if (same) typed = d.camsEmail; d.camsEmail = same ? signInEmail : typed; edited(); if (!same) setTimeout(() => field?.focus()); }} />
  Same as my sign-in email <span class="mono" style="color:var(--muted);font-size:12.5px">{signInEmail}</span></label>
{#if inSetup}
  <label class="check consent"><input type="checkbox" checked={!!d.ticks?.cams}
    onchange={e => { d.ticks = { cams: e.currentTarget.checked ? consentNow(['CAMS']) : null, kfintech: d.ticks?.kfintech ?? null }; }} /> {consentText(['CAMS'])}</label>
{/if}
<div class="testrow"><button class="btn secondary" disabled={!emailOk(d.camsEmail) || !ticked || busy} onclick={test}>Verify sign-in</button>
  {#if busy}<span class="spin"></span>
  {:else if sameArn(d.camsArn, d.arn)}<span class="okl">{@html icons.tickSm}CAMS shows {d.camsArn}</span>
    {#if dup}<span class="err">{d.arn} is already set up in this software.</span>{/if}
  {:else if d.camsArn}<span class="err">{mismatchLine(d, 'CAMS', inSetup)}</span>
  {:else if changed}<span class="err">{said} {#if d.kfintech.used}You can <a href="#skip" onclick={e => { e.preventDefault(); skip(); }}>skip CAMS for now</a> and continue with KFintech, or you can{:else}You can{/if}
    <a href="#support" onclick={e => { e.preventDefault(); ui.open({ type: 'support', where: 'Setup, CAMS: its sign-in page misbehaved twice' }); }}>send to support</a> and we'll fix it as soon as possible.</span>
  {:else if said}<span class="err">{ours ? said : `CAMS says: “${said}”`}</span>
  {:else if failed}<span class="err">CAMS couldn't be reached just now.</span>{/if}</div>
{#if !d.camsArn}
  <p class="line">Verifying signs into CAMS and reads your ARN from it.</p>
{/if}
<a href="#nocams" class="small-link" onclick={e => { e.preventDefault(); skip(); }}>I don't use CAMS</a>
{/if}
