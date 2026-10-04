<script lang="ts">
  /* One detail, changed with the same control as setup. In a popup (Settings, Overview's banners) or in place
     inside the run window (Check your details, a stop that is fixed on the spot). */
  import { app, type DetailsPatch, type ProfileDraft } from '../../bridge';
  import { camsValid, detailsValid, kfintechValid, mailboxValid, signatureValid } from '../../logic/details';
  import { store } from '../../state/store.svelte';
  import { ui, type Detail } from '../../state/ui.svelte';
  import CamsEmail from './CamsEmail.svelte';
  import Kfintech from './Kfintech.svelte';
  import Mailbox from './Mailbox.svelte';
  import Signature from './Signature.svelte';
  import WhoYouAre from './WhoYouAre.svelte';
  import InvoicePreview from '../../ui/InvoicePreview.svelte';
  import RegistrarPreview from '../../ui/RegistrarPreview.svelte';
  import { nextInvoice } from '../../logic/details';
  import YourInvoices from './YourInvoices.svelte';

  let { which, layout, ondone }: { which: Detail; layout: 'modal' | 'run'; ondone: (saved: boolean) => void } = $props();

  const p = store.snap!.profile!;
  // The CAMS email and the KFintech username are credentials: the app keeps them in its vault and shows them masked
  // (p***@gmail.com). Changing one is typing it afresh, as a password is; the masked form is only shown beside it.
  let d = $state<ProfileDraft>({
    arn: p.arn, name: p.name, gstin: p.gstin, camsUsed: p.camsUsed, camsEmail: '', camsArn: '',
    mailbox: { ...p.mailbox }, kfintech: { ...p.kfintech, username: '' }, signature: { ...p.signature },
    invoices: structuredClone($state.snapshot(p.invoices)), consent: p.consent
  });
  let saving = $state(false);

  const TITLE: Record<Detail, string> = { who: 'Your details', cams: 'CAMS', mb: 'Mailbox', kf: 'KFintech login', sig: 'Signature', inv: 'Your invoices' };
  // one of the two registrars stays in use
  const camsOk = (x: ProfileDraft) => camsValid(x) && (x.camsUsed || x.kfintech.used);
  const valid = $derived({ who: detailsValid, cams: camsOk, mb: mailboxValid, kf: kfintechValid, sig: signatureValid, inv: (x: ProfileDraft) => x.invoices.source !== '' }[which](d));

  async function save() {
    if (!valid || saving) return;
    const patch: DetailsPatch =
      which === 'who' ? { gstin: d.gstin, name: d.name } : which === 'cams' ? { camsUsed: d.camsUsed, camsEmail: d.camsEmail, camsArn: d.camsArn }
        : which === 'mb' ? { mailbox: d.mailbox } : which === 'kf' ? { kfintech: d.kfintech }
        : which === 'inv' ? { invoices: d.invoices } : { signature: d.signature };
    saving = true;
    const r = await app.saveDetails($state.snapshot(patch));
    saving = false;
    if (!r.ok) { store.toast(r.said); return; }
    if (which === 'mb') ui.clash = null;       // a changed CAMS email's clash comes back in the app's snapshot
    store.toast('Saved');
    ondone(true);
  }
</script>

<div class={layout === 'modal' ? 'm-bd' : 'rm-stage'}>
  <div class="work-hd"><h3>{TITLE[which]}</h3></div>
  <div class="part edbody">
    {#if which === 'who'}<WhoYouAre bind:d editing arnLocked={p.arnConfirmed} />
    {:else if which === 'cams'}<CamsEmail bind:d signInEmail={store.snap?.account?.email ?? ''} saved={p.camsEmail} />
    {:else if which === 'mb'}<Mailbox bind:d />
    {:else if which === 'kf'}<Kfintech bind:d saved={p.kfintech.username} />
    {:else if which === 'inv'}<YourInvoices bind:d choiceOnly />
      <p class="line">{d.invoices.source === 'own' ? 'Your number, your signature and your details are in Settings › Your invoices.' : 'Your signature is in Settings › Your invoices.'}</p>
    {:else}
      <Signature bind:d />
      {#if d.signature.way === 'image' && d.signature.image}
        {#if d.invoices.source === 'own'}<InvoicePreview settings={d.invoices.settings} number={nextInvoice(d.invoices) || d.invoices.last} name={d.name} gstin={d.gstin} signature={d.signature} />
        {:else}<RegistrarPreview kind="cams" name={d.name} gstin={d.gstin} arn={d.arn} signature={d.signature} />{/if}
      {/if}
    {/if}
  </div>
</div>
<div class={layout === 'modal' ? 'm-ft' : 'rm-foot'}>
  <button class="btn ghost" onclick={() => { void app.dropSignatureDraft(); ondone(false); }}>Cancel</button>
  <button class="btn primary" data-primary style="margin-left:auto" disabled={!valid || saving} onclick={save}>Save</button>
</div>
