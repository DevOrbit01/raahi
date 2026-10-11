// Exercise the actual extension command handler with controlled browser APIs.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('browser_extension/connector.js', 'utf8');
const tabs = new Map([[1, {id: 1, url: 'https://mail.example.com', status: 'complete'}]]);
const storage = {};
const nodes = new Map();
const navigated = [];
let next = 100;
let requests = 0;
const sandbox = {
  URL, AbortController, Uint8Array, Date, Promise,
  crypto: require('node:crypto').webcrypto,
  btoa: text => Buffer.from(text, 'binary').toString('base64'),
  setTimeout: (callback, ms) => setTimeout(callback, ms === 400 ? 0 : ms), clearTimeout,
  document: {documentElement: {outerHTML: '<html><h1>Auction 703774</h1></html>'}, getElementById: id => {
    if (!nodes.has(id)) nodes.set(id, {value: '', addEventListener() {}});
    return nodes.get(id);
  }},
  sessionStorage: {getItem: () => '1', setItem() {}},
  fetch: async url => {requests++; return {ok: true, status: 200, headers: {get: () => 'image/webp'}, arrayBuffer: async () => Uint8Array.from([0, 255, 42]).buffer};},
  chrome: {
    storage: {local: {get: async key => ({[key]: storage[key]}), set: async data => Object.assign(storage, data)}},
    tabs: {
      get: async id => {if (!tabs.has(id)) throw new Error('Closed'); return tabs.get(id);},
      create: async options => {const tab = {id: next++, windowId: 1, status: 'complete', ...options}; tabs.set(tab.id, tab); return tab;},
      update: async (id, options) => {navigated.push(id); return Object.assign(tabs.get(id), options);}
    },
    windows: {update: async () => {}},
    scripting: {executeScript: async data => {
      assert.notEqual(data.target.tabId, 1, 'personal tab must never be read');
      const fn = vm.runInContext('(' + data.func.toString() + ')', context);
      return [{result: await fn(...(data.args || []))}];
    }}
  }
};
const context = vm.createContext(sandbox);
vm.runInContext(source + '\nglobalThis.handler = execute;', context);
(async () => {
  const run = sandbox.handler;
  assert.equal((await run({method: 'goto', args: ['https://www.eauctionsindia.com/properties/703774']})).status, null);
  assert.match(await run({method: 'content', args: []}), /Auction 703774/);
  assert.equal(await run({method: 'is_closed', args: []}), false);
  assert.equal(tabs.size, 2);
  await run({method: 'goto', args: ['https://www.eauctionsindia.com/properties-in-sikkim']});
  assert.equal(tabs.size, 2, 'same managed auction tab must be reused');
  await assert.rejects(run({method: 'goto', args: ['https://evil.example/']}), /Only eAuctionsIndia/);
  await assert.rejects(run({method: 'fetch_asset', args: ['https://evil.example/storage/a.webp']}), /Unsupported attachment/);
  const asset = await run({method: 'fetch_asset', args: ['https://www.eauctionsindia.com/storage/images/a.webp']});
  assert.equal(asset.data, 'AP8q');
  assert.equal(requests, 1, 'attachments fetched only on explicit export operation');
  assert(!navigated.includes(1));
  console.log('Extension command tests passed: tab reuse, scoped navigation, DOM, binary export.');
})().catch(error => {console.error(error); process.exitCode = 1;});
