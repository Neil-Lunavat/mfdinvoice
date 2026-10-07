/* The View box for what the software sent (the Software tab, and an account's page): what it said, how the run ended and
   how long it took, Seen / Fixed, the same run's other reports, the pictures of the portals' pages, the other files,
   and the log. Any [data-view] button opens one, including the ones inside the box. */
import { $, esc, dialog, post } from './client';
import { RESULT, took, STATE } from '../lib/software';

const when = (iso: string) => new Date(iso).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
const tag = ([label, tone]: [string, string]) => `<span class="tag ${tone}">${esc(label)}</span>`;

async function view(id: string, b?: HTMLButtonElement) {
  if (b) b.disabled = true;
  const r = await fetch(`/api/admin/software?id=${id}`, { cache: 'no-store' }).then(x => x.json() as Promise<any>).catch(() => null);
  if (b) b.disabled = false;
  if (!r?.ok) { if (b) { b.title = 'The software’s server gave no answer.'; b.classList.add('bad'); } return; }
  const x = r.report, file = (n: string) => `/api/admin/software?id=${id}&file=${encodeURIComponent(n)}`;
  const files: { name: string; size: number }[] = r.files || [];
  const pictures = files.filter(f => /\.(jpe?g|png)$/i.test(f.name)), rest = files.filter(f => !/\.(jpe?g|png)$/i.test(f.name));
  const same: any[] = r.same || [];
  const ended = x.ended && x.kind !== 'problem' ? ` <span class="note mono">${esc(x.ended)}</span>` : '';
  dialog(`<div class="dlg-h"><h2 id="dlgT">#${esc(id)} ${tag(RESULT(x))}${ended}</h2><button type="button" id="dlgX" aria-label="Close">×</button></div>
    <div class="dlg-b">
      <p>${esc(x.email || 'No email')} <span class="note">· ${esc(x.arn || 'no ARN')} · ${esc(when(x.created_at))}${x.seconds != null ? ' · took ' + esc(took(x.seconds)) : ''}</span></p>
      <p class="note">${esc(x.place || '')}${x.place ? ' · ' : ''}software ${esc(x.version || '?')} · steps ${esc(x.steps || '?')}</p>
      <p class="note">${esc(x.pc || '')}</p>
      <div class="why">${x.message ? esc(x.message) : '<span class="muted">It said nothing.</span>'}</div>
      <div class="sw-state" id="swState">${['seen', 'fixed', ''].map(s => `<button type="button" class="btn sm ${x.state === s ? 'primary' : 'secondary'}" data-state="${s}">${s ? STATE[s][0] : 'Neither'}</button>`).join('')}<span class="err" id="swE" hidden></span></div>
      ${same.length ? `<div class="sw-same"><b>The same run</b>${same.map(o => `<div>${tag(RESULT(o))} <span class="note">#${o.id} · ${esc(when(o.created_at))}</span> ${esc(o.message || '')} <button type="button" class="btn secondary sm" data-view="${o.id}">View</button></div>`).join('')}</div>` : ''}
      ${pictures.length ? `<div class="shots">${pictures.map(f => `<a href="${file(f.name)}" target="_blank" title="${esc(f.name)}"><img src="${file(f.name)}" alt="${esc(f.name)}" loading="lazy"></a>`).join('')}</div>` : ''}
      ${rest.length ? `<p class="note">${rest.map(f => `<a class="blue" href="${file(f.name)}" target="_blank">${esc(f.name)}</a>`).join(' · ')}${x.record ? ` · <a class="blue" href="/api/admin/software?id=${id}&zip=1">all of it (zip)</a>` : ''}</p>` : ''}
      ${x.log ? `<pre class="applog">${esc(x.log)}</pre>` : '<p class="note">No log lines came with it.</p>'}
    </div>`);
  $('dlg').classList.add('wide');
  $('swState').querySelectorAll('[data-state]').forEach((s: HTMLButtonElement) => s.onclick = async () => {
    s.disabled = true;
    const res = await post('/api/admin/software', { id: +id, state: s.dataset.state });
    s.disabled = false;
    if (!res.ok) { $('swE').textContent = 'The software’s server didn’t take it. Try again.'; $('swE').hidden = false; return; }
    $('swState').querySelectorAll('[data-state]').forEach((o: HTMLButtonElement) => o.className = `btn sm ${o === s ? 'primary' : 'secondary'}`);
    const cell = document.querySelector(`[data-state-of="${id}"]`);
    if (cell) cell.innerHTML = s.dataset.state ? tag(STATE[s.dataset.state]) : '';
  });
}

document.addEventListener('click', e => {
  const b = (e.target as Element).closest?.('[data-view]') as HTMLButtonElement | null;
  if (b) view(b.dataset.view!, b);
});
