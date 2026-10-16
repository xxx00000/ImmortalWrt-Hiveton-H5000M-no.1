// Exercise the actual LuCI handler through its RPC boundary.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');

(async () => {
  const source = await fs.readFile(process.argv[2], 'utf8');
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'mt5700-logs-'));
  const log = path.join(directory, 'notifications.log');
  let deny = false;
  let notifications = [];
  const view = new Function('view', 'fs', 'ui', 'uci', 'E', '_', 'L', 'window', 'setTimeout', source)(
    { extend: value => value },
    { write: (file, content) => deny ? Promise.reject(new Error('permission denied')) : fs.writeFile(file, content) },
    { addNotification: (_title, _body, type) => notifications.push(type) },
    { get: () => log },
    () => ({}),
    value => ({ format: () => value }),
    { Request: { get: () => { throw new Error('Unauthenticated CGI must not be used'); } } },
    { location: { reload() {} } },
    () => {}
  );
  try {
    await fs.writeFile(log, 'test notification');
    await view.handleClearLog();
    assert.equal(await fs.readFile(log, 'utf8'), '');
    assert.deepEqual(notifications, ['success']);
    await fs.writeFile(log, 'keep on permission error');
    deny = true;
    notifications = [];
    await view.handleClearLog();
    assert.equal(await fs.readFile(log, 'utf8'), 'keep on permission error');
    assert.deepEqual(notifications, ['error']);
    console.log('LuCI authenticated log clearing: 2 checks passed');
  } finally {
    await fs.rm(directory, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
