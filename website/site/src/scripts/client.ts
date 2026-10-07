/* The helpers every page's script shares: find an element, escape text for HTML, POST to our API, the success tick,
   and the one dialog. Buttons: primary on the right, secondary on its left. Anything that can't be undone is red and
   asks for a word to be typed. */
export const $ = (id: string): any => document.getElementById(id);
export const esc = (v: unknown) => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);

/* JSON (or a form with files) to one of our routes → its JSON with ok and status; offline → { ok: false, error: 'offline' } */
export async function post(url: string, data: object | FormData): Promise<any> {
  const form = data instanceof FormData;
  try {
    const r = await fetch(url, { method: 'POST', ...(form ? {} : { headers: { 'content-type': 'application/json' } }), body: form ? data : JSON.stringify(data) });
    return { ok: r.ok, status: r.status, ...(await r.json().catch(() => ({}))) };
  } catch (e) { return { ok: false, error: 'offline' }; }
}

/* who is signed in: { signed_in, email, active, had_plan } (for the pages built ahead of time) */
export const me = (): Promise<{ signed_in: boolean; email?: string; active?: boolean; had_plan?: boolean }> => fetch('/api/me', { cache: 'no-store' }).then(r => r.json());

/* an email address that looks right (the server checks it again) */
export const validEmail = (v: string) => /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(v.trim());

/* the green tick that says something worked; "dt pop" draws itself in (base.css) */
export const tick = (cls = 'dt pop') => `<svg class="${cls}" viewBox="0 0 24 24"><circle cx="12" cy="12" r="11"/><path d="M7.5 12.4l3 3 6-6.4"/></svg>`;
/* the red cross that says it didn't (kit.css .done .x) */
export const cross = () => '<span class="x"><svg viewBox="0 0 24 24"><path d="M8 8l8 8M16 8l-8 8"/></svg></span>';

/* A short message that doesn't deserve a page: it drops in from the top, stays 5 seconds while its bar runs down,
   then goes. Nothing to click. */
export function toast(text: string, tone: '' | 'warn' = '', ms = 5000) {
  const t = document.createElement('div');
  t.className = `toast ${tone}`; t.setAttribute('role', 'status'); t.style.setProperty('--ms', ms + 'ms');
  t.innerHTML = `<p>${esc(text)}</p><i></i>`;
  document.body.appendChild(t);
  setTimeout(() => { t.classList.add('out'); setTimeout(() => t.remove(), 300); }, ms);
}

/* A toast for the next page, when this one is about to leave (Sign in → where they were going). Layout shows it on
   the next page's load. */
export function toastNext(text: string, tone: '' | 'warn' = '') {
  try { sessionStorage.setItem('toast', JSON.stringify([text, tone])); } catch (e) {}
}
export function toastWaiting() {
  try {
    const t = sessionStorage.getItem('toast'); if (!t) return;
    sessionStorage.removeItem('toast');
    const [text, tone] = JSON.parse(t); toast(text, tone);
  } catch (e) {}
}

/* One dialog at a time, over a scrim. closable: ×, Cancel, Escape and a click outside close it; focus goes back. */
export function dialog(html: string, closable = true) {
  let scrim = $('scrim');
  if (!scrim) {
    scrim = document.createElement('div'); scrim.className = 'scrim'; scrim.id = 'scrim'; scrim.hidden = true;
    scrim.innerHTML = '<div class="dlg" role="dialog" aria-modal="true" aria-labelledby="dlgT" id="dlg"></div>';
    document.body.appendChild(scrim);
  }
  const back = document.activeElement as HTMLElement | null;
  $('dlg').className = 'dlg';
  $('dlg').innerHTML = html;
  scrim.hidden = false;
  const close = () => { scrim.hidden = true; $('dlg').innerHTML = ''; removeEventListener('keydown', key); back?.focus(); };
  const key = (e: KeyboardEvent) => { if (e.key === 'Escape') close(); };
  if (closable) {
    $('dlgX')?.addEventListener('click', close);
    $('dlgC')?.addEventListener('click', close);
    scrim.onclick = (e: Event) => { if (e.target === scrim) close(); };
    addEventListener('keydown', key);
  } else scrim.onclick = null;
  return close;
}

export type Ask = {
  title: string; text?: string; warn?: string; action: string; danger?: boolean;
  phrase?: string;                                    /* type this to enable the button */
  field?: { label: string; value?: string; placeholder?: string; mono?: boolean; type?: string; required?: boolean };
  tick?: string;                                      /* a tick box under the field, unticked */
  run: (value: string, ticked: boolean) => Promise<any>;   /* resolves to the POST's result */
  done?: (r: any) => void;                            /* default: reload */
  error?: (r: any) => string;                         /* the line shown when run fails */
};

/* One dialog for every action: optional warning, optional input or typed confirmation, Cancel + the action. */
export function ask(a: Ask) {
  const close = dialog(`<div class="dlg-h"><h2 id="dlgT">${esc(a.title)}</h2><button type="button" id="dlgX" aria-label="Close">×</button></div>
    ${a.warn ? `<div class="warn">${a.warn}</div>` : ''}
    <div class="dlg-b">${a.text ? `<p>${a.text}</p>` : ''}
      ${a.phrase ? `<p>To confirm, type <b class="mono">${esc(a.phrase)}</b> below.</p>` : ''}
      ${a.field ? `<label class="note" for="dlgI">${esc(a.field.label)}</label>` : ''}
      ${a.field || a.phrase ? `<input class="input${a.field?.mono || a.phrase ? ' mono' : ''}" id="dlgI" type="${a.field?.type ?? 'text'}" autocomplete="off" spellcheck="false" value="${esc(a.field?.value ?? '')}" placeholder="${esc(a.field?.placeholder ?? '')}">` : ''}
      ${a.tick ? `<label class="check" style="margin-top:12px"><input type="checkbox" id="dlgK"><span>${esc(a.tick)}</span></label>` : ''}
      <span class="err" id="dlgE" hidden></span></div>
    <div class="dlg-f"><button class="btn secondary" type="button" id="dlgC">Cancel</button><button class="btn ${a.danger ? 'danger' : 'primary'}" type="button" id="dlgY">${esc(a.action)}</button></div>`);
  const y = $('dlgY'), i = $('dlgI');
  const valid = () => (!a.phrase || i.value === a.phrase) && (!a.field?.required || i.value.trim() !== '');
  if (i) { i.focus(); i.oninput = () => { y.disabled = !valid(); }; i.onkeydown = (e: KeyboardEvent) => { if (e.key === 'Enter' && !y.disabled) y.click(); }; }
  y.disabled = !valid();
  y.onclick = async () => {
    y.disabled = true; const label = y.textContent; y.innerHTML = '<span class="spin"></span>' + esc(label);
    const r = await a.run(i ? i.value.trim() : '', !!$('dlgK')?.checked);
    if (r?.ok) { close(); return (a.done ?? (() => location.reload()))(r); }
    y.textContent = label; y.disabled = false;
    $('dlgE').textContent = a.error ? a.error(r) : r?.error === 'offline' ? 'Couldn’t reach the server.' : 'That didn’t work. Try again.';
    $('dlgE').hidden = false;
  };
}
