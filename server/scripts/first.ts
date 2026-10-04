/* `bun run first`: everything the software's server needs before its first deploy, done once. Safe to run again.

     1. the database (software-db): made if it is not there, and its id written into wrangler.jsonc
     2. the bucket (software-files): made if it is not there
     3. the admin key: made if this PC has none, kept in ~/.mfdinvoice/server-admin.key, and set as the Worker's secret
     4. the deploy

   The admin key is what reads the reports back (ops/reports.py). */
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

const DB = 'software-db', BUCKET = 'software-files';
const CONFIG = join(import.meta.dir, '..', 'wrangler.jsonc');
const KEY = join(homedir(), '.mfdinvoice', 'server-admin.key');

function wrangler(args: string[], input?: string) {
  const r = spawnSync('bunx', ['wrangler', ...args], { cwd: join(import.meta.dir, '..'), encoding: 'utf8', input, shell: true });
  return { ok: r.status === 0, out: `${r.stdout ?? ''}${r.stderr ?? ''}` };
}
const idOf = () => {
  const r = wrangler(['d1', 'list', '--json']);
  try { return (JSON.parse(r.out.slice(r.out.indexOf('['))) as { name: string; uuid: string }[]).find(d => d.name === DB)?.uuid ?? ''; } catch { return ''; }
};

let id = idOf();
if (!id) {
  const made = wrangler(['d1', 'create', DB]);
  if (!made.ok) { console.error(made.out); process.exit(1); }
  id = idOf();
}
if (!id) { console.error(`Couldn't find ${DB} after making it. Is wrangler signed in? (bunx wrangler login)`); process.exit(1); }
const config = readFileSync(CONFIG, 'utf8');
writeFileSync(CONFIG, config.replace(/("database_name": "software-db", "database_id": ")[^"]*(")/, `$1${id}$2`));
console.log(`database ${DB}: ${id}`);

const bucket = wrangler(['r2', 'bucket', 'create', BUCKET]);
console.log(bucket.ok ? `bucket ${BUCKET}: made` : /already exists|already own/i.test(bucket.out) ? `bucket ${BUCKET}: already there` : bucket.out);

if (!existsSync(KEY)) {
  mkdirSync(join(homedir(), '.mfdinvoice'), { recursive: true });
  writeFileSync(KEY, crypto.randomUUID().replace(/-/g, '') + crypto.randomUUID().replace(/-/g, ''));
  console.log(`admin key: made, in ${KEY}`);
}

const deployed = wrangler(['deploy']);
console.log(deployed.out);
if (!deployed.ok) process.exit(1);
const secret = wrangler(['secret', 'put', 'ADMIN_KEY'], readFileSync(KEY, 'utf8').trim());
console.log(secret.ok ? 'admin key: set on the Worker' : secret.out);
