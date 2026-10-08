<script lang="ts">
  import { NAME } from '../../brand';
  /* Every popup, stacked in the order opened. Esc closes the top one. */
  import { app } from '../../bridge';
  import { consentNow, consentText } from '../../logic/consent';
  import { dayMonth } from '../../logic/format';
  import { store } from '../../state/store.svelte';
  import { ui } from '../../state/ui.svelte';
  import { icons } from '../../ui/icons';
  import Modal from '../../ui/Modal.svelte';
  import Editor from '../setup/Editor.svelte';
  import CamsFilesPopup from './CamsFilesPopup.svelte';
  import InvoicePopup from './InvoicePopup.svelte';

  let text = $state('');
  let sending = $state(false);
  const NOT_SENT = "Couldn't send it just now. Try again in a minute.";

  /* Nobody is answered from here: a problem is fixed for everyone, so sending is all there is to do. */
  async function send(where: string) {
    sending = true;
    const r = await app.sendSupport({ text: text.trim(), where });
    sending = false;
    if (!r.sent) { store.toast(NOT_SENT); return; }
    text = '';
    ui.close();
    store.toast(`Sent. Thank you for helping ${NAME} get better.`);
  }
  let remove = $state(false);
  let agreed = $state(false);
  const registrars = $derived([store.snap?.profile?.camsUsed && 'CAMS', store.snap?.profile?.kfintech.used && 'KFintech'].filter(Boolean) as string[]);
  async function signOut() {
    sending = true;
    await app.signOut(remove);
    sending = false; remove = false;
    ui.popups = [];
  }
  async function agree() {
    sending = true;
    const r = await app.agree(consentNow(registrars));
    sending = false; agreed = false;
    ui.close();
    store.toast(r.ok ? 'Saved' : r.said);
  }
  function quit() {
    const r = store.run;
    if (r) app.closeRun(r.id);
    ui.close();
    app.quit();
  }
</script>

{#each ui.popups as p, i (i)}
  {#if p.type === 'support'}
    <Modal label="Send to support" onclose={() => ui.close()}>
      <div class="m-bd">
        <div class="work-hd"><h3>Send to support</h3></div>
        <div class="field"><label for="st">What happened? (optional)</label>
          <textarea id="st" class="input ta" rows="5" placeholder="e.g. It stopped at Get and said…" bind:value={text}></textarea></div>
        <div class="goes"><div class="label">What we'll see</div>
          <ul>
            <li>What you write here</li>
            <li>What {NAME} was doing on this PC, and where it stopped</li>
            <li>{NAME}'s version and this PC: its name, Windows version, memory and free disk space</li>
          </ul>
          <p class="line">{@html icons.lock} Never your passwords, signature or mailbox.</p></div>
      </div>
      {#snippet foot()}
        <button class="btn ghost" onclick={() => ui.close()}>Cancel</button>
        <button class="btn primary" data-primary disabled={sending} onclick={() => send(p.where)}>Send</button>
      {/snippet}
    </Modal>
  {:else if p.type === 'edit'}
    <Modal label="Change a detail" onclose={() => ui.close()}>
      <Editor which={p.which} layout="modal" ondone={() => ui.close()} />
    </Modal>
  {:else if p.type === 'invoice'}
    <InvoicePopup invoice={p.invoice} period={p.period} />
  {:else if p.type === 'cams_files'}
    <CamsFilesPopup done={p.done} />
  {:else if p.type === 'close_ask'}
    <Modal label="Close {NAME}?" onclose={() => ui.close()}>
      <div class="m-bd ask-close">
        <div class="work-hd"><h3>A run is going. Close {NAME}?</h3></div>
        <p>Closing ends the run. Nothing is submitted without you, and the next run picks up what this one already fetched.</p>
      </div>
      {#snippet foot()}
        <button class="btn ghost" onclick={quit}>Close {NAME}</button>
        <button class="btn primary" data-primary onclick={() => ui.close()}>Keep running</button>
      {/snippet}
    </Modal>
  {:else if p.type === 'sign_out'}
    <Modal label="Sign out of this PC" onclose={() => ui.close()}>
      <div class="m-bd ask-close">
        <div class="work-hd"><h3>Sign out of {NAME} on this PC?</h3></div>
        <p>Your invoice files stay on this PC. Your logins and signature stay too, ready for when you sign in again.</p>
        <label class="check"><input type="checkbox" bind:checked={remove} /> Also remove passwords and signature from this PC</label>
      </div>
      {#snippet foot()}
        <button class="btn ghost" onclick={() => ui.close()}>Cancel</button>
        <button class="btn primary" data-primary disabled={sending} onclick={signOut}>Sign out</button>
      {/snippet}
    </Modal>
  {:else if p.type === 'consent'}
    <Modal label="Your authority" onclose={() => ui.close()}>
      <div class="m-bd ask-close">
        <div class="work-hd"><h3>Before {NAME} acts for you</h3></div>
        <p>{NAME} signs in to CAMS and KFintech with your own logins, from this PC, and does only what you would do by hand.</p>
        <label class="check"><input type="checkbox" bind:checked={agreed} /> {consentText(registrars)}</label>
      </div>
      {#snippet foot()}
        <button class="btn ghost" onclick={() => ui.close()}>Cancel</button>
        <button class="btn primary" data-primary disabled={!agreed || sending} onclick={agree}>Confirm</button>
      {/snippet}
    </Modal>
  {:else if p.type === 'trial_started'}
    <Modal label="Your free trial has started" onclose={() => ui.close()}>
      <div class="m-bd ask-close">
        <div class="work-hd"><h3>You're in. Everything is unlocked.</h3></div>
        <p>{NAME} is yours in full{store.snap?.plan?.until ? ` until ${dayMonth(store.snap.plan.until)}` : ' for 15 days'}: both registrars, every fund house, every invoice. Use it as if you own it.</p>
        <p>We'll email you 3 days before your trial ends, so it never catches you by surprise.</p>
      </div>
      {#snippet foot()}
        <button class="btn primary" data-primary style="margin-left:auto" onclick={() => ui.close()}>Let's run</button>
      {/snippet}
    </Modal>
  {:else if p.type === 'leave_settings'}
    <Modal label="Unsaved changes" onclose={() => ui.close()}>
      <div class="m-bd ask-close">
        <div class="work-hd"><h3>Save your changes?</h3></div>
        <p>Your changes in Settings aren't saved yet.</p>
      </div>
      {#snippet foot()}
        <button class="btn ghost" onclick={() => ui.close()}>Cancel</button>
        <button class="btn secondary" onclick={() => { ui.discardSettings?.(); ui.close(); p.go(); }}>Discard</button>
        <button class="btn primary" data-primary onclick={async () => { await ui.saveSettings?.(); ui.close(); p.go(); }}>Save</button>
      {/snippet}
    </Modal>
  {/if}
{/each}
