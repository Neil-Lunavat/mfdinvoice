<script lang="ts">
  import { NAME } from '../brand';
  /* The main window: the sidebar (#10) with the bell (#21) and the ARN switcher (#22) at its top, and the
     account and version at its foot. Activity is Settings › History (#19). The books tab is named for the books
     the person keeps: Books. */
  import type { Snippet } from 'svelte';
  import { app } from '../bridge';
  import { dayMon, hhmm } from '../logic/format';
  import { noFreeSlot, planLine } from '../logic/plan';
  import { store } from '../state/store.svelte';
  import { ui, type Page } from '../state/ui.svelte';
  import { icons } from '../ui/icons';

  let { children }: { children: Snippet } = $props();

  const s = $derived(store.snap!);
  const NAV: [Page, string, string][] = [['overview', 'Overview', icons.cal], ['invoices', 'Invoices', icons.doc], ['downloads', 'Downloads', icons.downloads], ['books', 'Books', icons.book], ['settings', 'Settings', icons.gear]];
  const unread = $derived(s.notes.filter(n => !n.read).length);
  const current = $derived(s.arns.find(a => a.arn === s.arn));
  const full = $derived(s.arns.length >= (s.account?.maxArns ?? 6));
  const noSlot = $derived(noFreeSlot(s.plan, s.arns.map(a => a.arn)));
  const cond = $derived(s.condition);

  const chip = (a: (typeof s.arns)[number]) =>
    a.status === 'Rejected' ? { t: `${a.rejected} rejected`, c: 'bad' } : a.status === 'Approved' ? { t: 'Approved', c: 'good' }
      : a.status === 'Submitted' ? { t: 'Submitted', c: 'wait' } : { t: 'Not submitted', c: 'neutral' };

  function toggle(m: 'bell' | 'arn', e: MouseEvent) {
    e.stopPropagation();
    ui.menu = ui.menu === m ? '' : m;
    if (m === 'bell' && ui.menu === 'bell' && unread) app.markNotesRead();
  }
  async function switchTo(arn: string) {
    ui.menu = '';
    if (arn === s.arn) return;
    if (store.run && !store.run.ended) { store.toast('A run is going. Switch once it has ended.'); return; }
    ui.month = null;
    await app.switchArn(arn);
    const a = store.snap?.arns.find(x => x.arn === arn);
    if (a) store.toast(`Switched to ${a.arn} · ${a.name}`);
    ui.go('overview');
  }
  function when(iso: string) { return `${dayMon(iso)}, ${hhmm(iso)}`; }
  // Refresh: ask the website again what the plan says (a plan or an ARN just bought there shows at once)
  let refreshing = $state(false);
  async function refresh() { refreshing = true; await app.checkPlan(); refreshing = false; store.toast('Refreshed'); }
</script>

<div class="view app" data-layer="page">
  <div class="shell side">
    <aside class="snav" aria-label="Main">
      <div class="brand"><span class="mark">{@html icons.mark(14)}</span>{NAME}
        <div class="bell-wrap">
          <button class="icon-btn bell" aria-label={unread ? `Notifications, ${unread} new` : 'Notifications'} aria-expanded={ui.menu === 'bell'} onclick={e => toggle('bell', e)}>
            {@html icons.bell}{#if unread}<i class="bdg">{unread}</i>{/if}</button>
          {#if ui.menu === 'bell'}
            <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
            <div class="npop" role="dialog" tabindex="-1" aria-label="Notifications" onclick={e => e.stopPropagation()}>
              <div class="np-hd"><b>Notifications</b></div>
              {#each s.notes as n (n.id)}
                <button class="np" class:unread={!n.read} onclick={() => { ui.menu = ''; if (n.opens) ui.go(n.opens); }}>
                  <b>{n.text}</b>{#if n.detail}<span>{n.detail}</span>{/if}<em>{when(n.when)}</em></button>
              {:else}
                <p class="line" style="padding:6px 10px 10px">Nothing yet.</p>
              {/each}
            </div>
          {/if}
        </div>
      </div>

      <div class="arnsw">
        <button id="arnsw" aria-haspopup="menu" aria-expanded={ui.menu === 'arn'} onclick={e => toggle('arn', e)}>
          <div><b class="mono">{current?.arn}</b><span>{current?.name}</span></div><span class="chev2">{@html icons.chevDown}</span></button>
        {#if ui.menu === 'arn'}
          <div class="menu arnmenu" role="menu">
            {#each s.arns as a (a.arn)}
              {@const c = chip(a)}
              <button role="menuitem" class:on={a.arn === s.arn} onclick={e => { e.stopPropagation(); switchTo(a.arn); }}>
                <div><b class="mono">{a.arn}</b><span>{a.name}</span></div><span class="chip {c.c}">{c.t}</span></button>
            {/each}
            {#if full}
              <p class="line" style="padding:8px 12px">For more than {s.account?.maxArns ?? 6} ARNs, talk to us.</p>
            {:else if noSlot}
              <p class="line" style="padding:8px 12px 2px">Every ARN slot on your plan is in use.</p>
              <button role="menuitem" class="addarn" onclick={e => { e.stopPropagation(); ui.menu = ''; app.open('billing'); }}>Add ARNs on the website</button>
            {:else}
              <button role="menuitem" class="addarn" onclick={e => { e.stopPropagation(); ui.menu = ''; ui.startSetup(true); }}>+ Add ARN</button>
            {/if}
          </div>
        {/if}
      </div>

      <nav>
        {#each NAV as [k, label, ic], i (k)}
          <button class="nv" class:on={ui.page === k} aria-current={ui.page === k ? 'page' : undefined} title="{label} · Ctrl+{i + 1}" onclick={() => ui.go(k)}>
            {@html ic}<span>{label}</span></button>
        {/each}
      </nav>

      <div class="sfoot">
        <button class="acct" style="border:0;background:none;padding:12px 0 0;text-align:left;font:inherit;border-top:1px solid var(--line-2)"
          onclick={() => { ui.go('settings'); ui.goSection('Account & plan'); }}>
          <span class="av">{(s.account?.email ?? '?')[0].toUpperCase()}</span><div><b>{s.account?.email}</b><span>{planLine(s.plan)}</span></div></button>
        <span class="ver"><i class="dot" class:red={cond !== 'normal'} class:amber={cond === 'normal' && !!s.update}></i>v{s.version}{cond === 'offline' ? ' · offline' : cond === 'down' ? ' · our service is down' : ''}
          <button class="icon-btn" style="margin-left:auto" data-tip="Refresh" aria-label="Refresh" disabled={refreshing} onclick={refresh}>{#if refreshing}<span class="spin"></span>{:else}{@html icons.sync}{/if}</button></span>
      </div>
    </aside>
    <main class="main">{@render children()}</main>
  </div>
</div>
