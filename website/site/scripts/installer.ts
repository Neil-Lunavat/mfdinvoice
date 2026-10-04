/* bun run installer -- <path to the .exe>
   Uploads the installer to R2 (the live bucket), replacing the one before: /api/download serves it. Run by
   ops/release.py, which then writes the release into RELEASES in src/consts.ts; after that, deploy. You must be
   logged in: bunx wrangler login. */
import { spawnSync } from 'bun';
import { existsSync, readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { INSTALLER } from '../src/consts';

const file = process.argv[2];
if (!file || !existsSync(file)) {
  console.log('Usage: bun run installer -- <path to the .exe>');
  process.exit(1);
}
const put = spawnSync(['bunx', 'wrangler', 'r2', 'object', 'put', `site-files/${INSTALLER}`, '--file', file,
  '--content-type', 'application/vnd.microsoft.portable-executable', '--remote'], { stdout: 'inherit', stderr: 'inherit' });
if (put.exitCode) process.exit(put.exitCode);
console.log(`\nUploaded. sha256: ${createHash('sha256').update(readFileSync(file)).digest('hex')}`);
console.log('ops/release.py writes the release into src/consts.ts next; then deploy.');
