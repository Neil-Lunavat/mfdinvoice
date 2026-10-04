/* DEVELOPMENT ONLY: the fake app with its switches, driven by the development panel. bridge/index.ts uses this
   class only when `import.meta.env.DEV`, so the shipped build leaves it out. */

import { FakeApp, type Scenario } from '../bridge/fake/fake';
import * as D from '../bridge/fake/data';

const now = () => { const d = new Date(), p = (n: number) => String(n).padStart(2, '0'); return `${D.TODAY}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`; };

export class DevFakeApp extends FakeApp {

  set(s: Partial<Scenario>) { Object.assign(this.scenario, s); this.rebuild(); }

  approvalsArrive() {
    const c = this.cur;
    if (!c) return;
    let n = 0;
    c.month.invoices = c.month.invoices.map(x => x.status === 'Waiting approval' && x.amc !== 'Axis' ? (n++, D.withStatus(x, 'Approved', c.month.submittedOn || D.TODAY)) : x);
    if (!n) return;
    const text = `${n} invoices approved.`;
    c.notes.unshift({ id: 'n' + Date.now(), kind: 'approved', text, detail: '', opens: 'invoices', when: now(), read: false });
    c.activity.unshift({ at: now(), text: `${n} invoices approved`, registrar: null, who: '', tone: 'plain' });
    this.publish();
    this.push({ type: 'notify', kind: 'approved', text, opens: 'invoices', toast: true });
  }

  rejectionArrives() {
    const c = this.cur;
    if (!c) return;
    const x = c.month.invoices.find(i => i.status !== 'Rejected' && i.status !== 'Not submitted' && i.registrar === 'KFINTECH')
      ?? c.month.invoices.find(i => i.status !== 'Rejected' && i.status !== 'Not submitted');
    if (!x) return;
    c.month.invoices = c.month.invoices.map(i => i === x ? D.withStatus(i, 'Rejected', c.month.submittedOn || D.TODAY) : i);
    const reg = x.registrar === 'CAMS' ? 'CAMS' : 'KFintech';
    const text = `${x.amc} rejected an invoice.`;
    c.notes.unshift({ id: 'n' + Date.now(), kind: 'rejected', text, detail: `${reg} says: “${D.REJECTION}”`, opens: 'invoices', when: now(), read: false });
    c.activity.unshift({ at: now(), text: `${x.amc} rejected ${x.number}: “${D.REJECTION}”`, registrar: x.registrar, who: '', tone: 'bad' });
    this.publish();
    this.push({ type: 'notify', kind: 'rejected', text, opens: 'invoices', toast: true });
  }

  pressClose() { this.push({ type: 'close_requested' }); }

}
