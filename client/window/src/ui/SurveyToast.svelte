<script lang="ts">
  /* A survey from the panel (website: Survey › Software), asked on Overview only, never during a run or setup. A toast
     at the bottom right until it is answered or closed; its X means never again for that survey. Opened, it asks one
     question at a time (none is required), then thanks them with the checkout's heart. */
  import { app, type SurveyAnswers, type SurveyAsk } from '../bridge';
  import { store } from '../state/store.svelte';
  import { icons } from './icons';

  const s = $derived(store.snap!);
  let sv = $state<SurveyAsk | null>(null);              // the survey open now, kept while the thanks shows
  let at = $state(0);
  let answers = $state<SurveyAnswers>({});
  let busy = $state(false), thanked = $state(false), said = $state('');

  const shown = $derived(!!s.survey && !s.run && !sv);
  const q = $derived(sv?.questions[at]);
  const a = $derived(q ? (answers[q.key] ?? { picked: [], text: '' }) : { picked: [], text: '' });
  const any = $derived(Object.values(answers).some(x => x.picked.length || x.text.trim()));
  const last = $derived(!!sv && at === sv.questions.length - 1);

  function open() { sv = s.survey!; at = 0; answers = {}; thanked = false; said = ''; }
  async function never() { await app.answerSurvey(s.survey!.id, null); }
  function set(picked: string[], text = a.text) { answers = { ...answers, [q!.key]: { picked, text } }; }
  function pick(o: string) {
    if (q!.type === 'one') set(a.picked[0] === o ? [] : [o], '');
    else set(a.picked.includes(o) ? a.picked.filter(x => x !== o) : [...a.picked, o]);
  }
  // drawn at the window's root: Overview's entry animation would hold anything fixed inside it
  function portal(node: HTMLElement) { document.body.appendChild(node); return { destroy() { node.remove(); } }; }
  async function submit() {
    busy = true; said = '';
    const clean = Object.fromEntries(Object.entries(answers).filter(([, x]) => x.picked.length || x.text.trim()));
    const r = await app.answerSurvey(sv!.id, clean);
    busy = false;
    if (r.sent) thanked = true;
    else said = "It didn't send. Check the internet connection and try again.";
  }
</script>

{#if shown}
  <div class="sv-toast enter" role="status" use:portal>
    <button class="sv-open" onclick={open}><b>Fill a quick survey to help improve</b><span>{s.survey!.questions.length} {s.survey!.questions.length === 1 ? 'question' : 'questions'} · a minute</span></button>
    <button class="icon-btn xs sv-x" aria-label="Don't ask me this survey again" data-tip="Don't ask again" onclick={never}>×</button>
  </div>
{/if}

{#if sv}
  <div class="sv-layer" use:portal>
  <div class="sv-scrim" role="presentation" onclick={() => (sv = null)}></div>
  <div class="sv-sheet" role="dialog" aria-modal="true" aria-label={sv.title}>
    {#if thanked}
      <div class="sv-thanks">
        <svg class="heart" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>
        <div><b>Thank you!</b><p>We read every answer ourselves. Every bit of feedback counts!</p></div>
      </div>
      <div class="sv-foot"><button class="btn primary" data-primary onclick={() => (sv = null)}>Close</button></div>
    {:else if q}
      <div class="sv-hd"><span class="line">Question {at + 1} of {sv.questions.length}</span>
        <button class="icon-btn xs" aria-label="Close" onclick={() => (sv = null)}>×</button></div>
      <h2>{q.q}</h2>
      {#if q.type === 'text'}
        <textarea class="input" rows="4" maxlength="1000" placeholder="Your answer" value={a.text} oninput={e => set([], e.currentTarget.value)}></textarea>
      {:else}
        <div class="sv-opts" role={q.type === 'one' ? 'radiogroup' : 'group'}>
          {#each q.options as o (o)}
            <button class="tile" class:on={a.picked.includes(o)} role={q.type === 'one' ? 'radio' : 'checkbox'} aria-checked={a.picked.includes(o)} onclick={() => pick(o)}>
              <span class="mk" class:sq={q.type === 'many'}>{#if a.picked.includes(o)}{@html icons.tickSm}{/if}</span>{o}</button>
          {/each}
          {#if q.other}
            <input class="input" maxlength="1000" placeholder="Other: in your words" value={a.text}
              oninput={e => set(q.type === 'one' && e.currentTarget.value ? [] : a.picked, e.currentTarget.value)} />
          {/if}
        </div>
        {#if q.type === 'many'}<p class="line">Pick as many as you like.</p>{/if}
      {/if}
      {#if said}<p class="err">{said}</p>{/if}
      <div class="sv-foot">
        {#if at > 0}<button class="btn ghost" onclick={() => at--}>Back</button>{/if}
        {#if last}<button class="btn primary" data-primary disabled={busy || !any} onclick={submit}>{busy ? 'Sending…' : 'Submit'}</button>
        {:else}<button class="btn primary" data-primary onclick={() => at++}>Next</button>{/if}
      </div>
    {/if}
  </div>
  </div>
{/if}

<style>
  .sv-toast { position: fixed; right: 20px; bottom: 20px; z-index: 40; display: flex; align-items: flex-start; gap: 4px; max-width: 340px;
    padding: 12px 10px 12px 16px; border: 1px solid var(--line); border-radius: var(--r-card); background: var(--surface); box-shadow: var(--e-sheet); }
  .sv-open { all: unset; cursor: pointer; display: flex; flex-direction: column; gap: 3px; font-size: 13.5px; }
  .sv-open span { color: var(--muted); font-size: 12.5px; }
  .sv-open:hover b { color: var(--blue); }
  .sv-x { font-size: 16px; }
  .sv-layer { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; }
  .sv-scrim { position: absolute; inset: 0; background: rgba(15, 23, 42, .32); }
  .sv-sheet { position: relative; width: min(520px, calc(100vw - 48px)); max-height: calc(100vh - 48px); overflow: auto;
    display: flex; flex-direction: column; gap: 14px; padding: 20px 22px; border-radius: var(--r-sheet); background: var(--surface); box-shadow: var(--e-sheet); }
  .sv-hd { display: flex; align-items: center; justify-content: space-between; }
  h2 { font-size: 17px; font-weight: 600; line-height: 1.4; margin: 0; }
  .sv-opts { display: flex; flex-direction: column; gap: 8px; }
  .sv-opts .tile { display: flex; flex-direction: row; align-items: center; justify-content: flex-start; gap: 10px; text-align: left; padding: 11px 14px; height: auto; min-height: 44px; width: 100%; }
  .mk { width: 18px; height: 18px; border-radius: 50%; border: 1.5px solid var(--line); display: grid; place-items: center; flex-shrink: 0; color: var(--blue); }
  .mk.sq { border-radius: 5px; }
  .tile.on .mk { border-color: var(--blue); }
  textarea { width: 100%; height: auto; padding: 10px 12px; resize: vertical; }
  .sv-foot { display: flex; justify-content: flex-end; gap: 8px; }
  .sv-thanks { display: flex; align-items: center; gap: 14px; padding: 18px; border-radius: var(--r-card); background: #fff1f3; border: 1.5px solid #fecdd3; }
  .sv-thanks p { margin: 2px 0 0; color: var(--ink-2); font-size: 14px; }
  .heart { width: 30px; height: 30px; flex-shrink: 0; fill: #e11d48; animation: beat 900ms ease 200ms both; }
  @keyframes beat { 0% { transform: scale(.3); opacity: 0 } 35% { transform: scale(1.15); opacity: 1 } 55% { transform: scale(.95) } 75% { transform: scale(1.08) } 100% { transform: scale(1) } }
</style>
