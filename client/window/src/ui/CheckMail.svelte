<script lang="ts">
  /* Check mail: CAMS's emails looked for now, for every month waiting on one (Downloads, a month's page). Only for a
     mailbox the software reads by itself (Gmail, or forwarded to us); by hand there is nothing to check. */
  import { app } from '../bridge';
  import { registrarsOf } from '../logic/details';
  import { store } from '../state/store.svelte';

  const NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const MON = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
  const name = (of: string) => NAMES[MON.indexOf(of.split('-')[0])] ?? of;
  const listed = (m: string[]) => m.length < 2 ? m.join('') : `${m.slice(0, -1).join(', ')} and ${m[m.length - 1]}`;

  const p = $derived(store.snap?.profile ?? null);
  const shown = $derived(!!p && p.mailbox.provider !== 'folder' && registrarsOf(p).includes('CAMS'));
  let busy = $state(false);

  async function check() {
    busy = true;
    try {
      const r = await app.checkMail();
      if (r.said) store.toast(r.said);
      else if (r.got.length) store.toast(`CAMS's email came for ${listed(r.got.map(g => `${name(g.period)} (${g.count} ${g.count === 1 ? 'invoice' : 'invoices'})`))}.`);
      else if (r.waiting.length) store.toast(`No email from CAMS yet for ${listed(r.waiting.map(name))}. It's read in when it comes.`);
      else store.toast("No month is waiting for CAMS's email.");
    } catch { store.toast("The mailbox couldn't be checked just now. Try again."); }
    busy = false;
  }
</script>

{#if shown}<button class="btn secondary" disabled={busy} onclick={check}>{#if busy}<span class="spin"></span>{/if}Check mail</button>{/if}
