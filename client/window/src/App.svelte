<script lang="ts">
  /* The window. Opens on the short opening screen, then the first screen that is true (logic/opening.ts).
     Keyboard: Enter = the view's main button, Esc closes popups but never a run, Ctrl+1…4 for the sidebar,
     Ctrl+5 for History. */
  import { onMount } from 'svelte';
  import { app } from './bridge';
  import { opening } from './logic/opening';
  import { planScreen } from './logic/plan';
  import { store } from './state/store.svelte';
  import { ui, type Page } from './state/ui.svelte';
  import Invoices from './screens/invoices/Invoices.svelte';
  import Overview from './screens/Overview.svelte';
  import PlanScreen from './screens/PlanScreen.svelte';
  import Popups from './screens/popups/Popups.svelte';
  import RunWindow from './screens/run/RunWindow.svelte';
  import Settings from './screens/Settings.svelte';
  import Books from './screens/Books.svelte';
  import Downloads from './screens/Downloads.svelte';
  import Setup from './screens/setup/Setup.svelte';
  import Shell from './screens/Shell.svelte';
  import SignIn from './screens/SignIn.svelte';
  import Splash from './screens/Splash.svelte';
  import UpdateRequired from './screens/UpdateRequired.svelte';
  import Toasts from './ui/Toasts.svelte';

  let opened = $state(false);

  const s = $derived(store.snap);
  const o = $derived(s ? opening({ updateRequired: !!s.update, condition: s.condition, signedIn: !!s.account, hasArn: s.arns.length > 0 }) : null);

  onMount(() => {
    store.start().then(() => {
      opened = true;
      const first = o?.screen ?? 'signin';
      if (first === 'setup') ui.startSetup(false); else if (first !== 'update') ui.go(first);
    });
  });

  // signed out elsewhere, or the last ARN gone: follow the opening order again
  $effect(() => {
    if (!opened || !o || o.screen === 'update') return;
    if (o.screen === 'signin' && ui.page !== 'signin') ui.go('signin');
    else if (o.screen === 'setup' && ui.page !== 'setup') ui.startSetup(false);
    else if (o.screen === 'overview' && (ui.page === 'signin' || ui.page === 'splash' || (ui.page === 'setup' && !ui.adding && ui.reached === 0))) ui.go('overview');
  });

  // where the window is, told to the app so an update comes back here
  $effect(() => {
    const place = { page: ui.page, section: ui.section, month: ui.invoicesMonth ?? '' };
    if (opened && (place.page === 'overview' || place.page === 'invoices' || place.page === 'settings')) void app.here(place);
  });

  // the person pressed the window's close button: a run in progress asks once; otherwise the app quits
  let seen = 0;
  $effect(() => {
    const n = store.closeRequested;
    if (n === seen) return;
    seen = n;
    const going = !!store.run && !store.run.ended;
    if (!going) { app.quit(); return; }
    if (ui.top?.type !== 'close_ask') ui.open({ type: 'close_ask' });
  });

  const NAV: Page[] = ['overview', 'invoices', 'downloads', 'books', 'settings'];
  const inMain = $derived(NAV.includes(ui.page));

  function topLayer(): HTMLElement | null {
    const all = document.querySelectorAll<HTMLElement>('[data-layer]');
    return all[all.length - 1] ?? null;
  }

  function onkey(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      if (ui.menu) { ui.menu = ''; e.preventDefault(); return; }
      if (ui.popups.length) { ui.close(); e.preventDefault(); }
      return;                                             // a run window is never closed by Esc
    }
    if (e.ctrlKey && !e.altKey && !e.shiftKey && /^[1-5]$/.test(e.key)) {
      if (!inMain || ui.runWith || ui.popups.length) return;
      e.preventDefault();
      const n = Number(e.key);
      if (n === 5) { ui.go('settings'); ui.goSection('History'); } else ui.go(NAV[n - 1]);
      return;
    }
    if (e.key === 'Enter' && !e.ctrlKey && !e.altKey && !e.shiftKey && !e.isComposing) {
      const t = e.target as HTMLElement;
      const own = t.closest('button, a, textarea, select, [data-own-enter], tr[tabindex], th[tabindex], [role="menuitem"]');
      const typeable = t instanceof HTMLInputElement && !['checkbox', 'radio', 'range', 'file'].includes(t.type);
      if (own || (t !== document.body && !typeable && t.tagName !== 'DIV')) return;
      const main = topLayer()?.querySelector<HTMLButtonElement>('[data-primary]:not([disabled])');
      if (main) { e.preventDefault(); main.click(); }
    }
  }
</script>

<svelte:window onkeydown={onkey} onclick={() => { if (ui.menu) ui.menu = ''; }} />

<div class="content">
  {#if !opened || !s}
    <Splash />
  {:else if o?.screen === 'update'}
    <UpdateRequired />
  {:else if ui.page === 'signin'}
    <SignIn banner={o?.banner ?? null} />
  {:else if ui.page === 'setup'}
    <Setup />
  {:else if s.profile && s.month}
    <Shell>
      {#if ui.page === 'overview'}
        {@const plan = planScreen(s.plan, s.arn, s.profile)}
        {#if plan}<PlanScreen kind={plan} />{:else}<Overview banner={o?.banner ?? null} />{/if}
      {:else if ui.page === 'invoices'}<Invoices />
      {:else if ui.page === 'downloads'}{#key s.arn}<Downloads />{/key}
      {:else if ui.page === 'books'}{#key s.arn}<Books />{/key}
      {:else if ui.page === 'settings'}<Settings />{/if}
    </Shell>
    {#if ui.runWith}{#key ui.runWith}<RunWindow registrars={ui.runWith.registrars} period={ui.runWith.period} what={ui.runWith.what} periods={ui.runWith.periods} />{/key}{/if}
  {/if}
  <Popups />
  <Toasts />
</div>

{#if import.meta.env.DEV}
  {#await import('./dev/DevPanel.svelte') then m}<m.default />{/await}
{/if}
