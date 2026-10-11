const endpoint = 'http://127.0.0.1:49381';
const status = document.getElementById('status');
const input = document.getElementById('key');
const client = crypto.randomUUID();
let running = false;
let auctionTab = null;
let pairing = '';
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const auctionUrl = url => {
  const parsed = new URL(url);
  return parsed.protocol === 'https:' && ['eauctionsindia.com', 'www.eauctionsindia.com'].includes(parsed.hostname);
};
async function request(path, payload) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 35000);
  let response;
  try {response = await fetch(endpoint + path, {
    method: 'POST', headers: {'Authorization': 'Bearer ' + pairing, 'Content-Type': 'application/json'},
    body: JSON.stringify({...payload, client}), signal: controller.signal
  });} finally {clearTimeout(timeout);}
  if (!response.ok) throw new Error(response.status === 403 ? 'Pairing code rejected. Copy the code from Raahi setup.' : 'Connector request failed. Close any duplicate connector tab.');
  return response.json();
}
async function tabExists(id) {
  try { return auctionUrl((await chrome.tabs.get(id)).url); } catch (_) { return false; }
}
async function getTab() {
  if (auctionTab && await tabExists(auctionTab)) return auctionTab;
  const saved = (await chrome.storage.local.get('auctionTab')).auctionTab;
  if (saved && await tabExists(saved)) {
    try {
      const marked = await chrome.scripting.executeScript({target: {tabId: saved}, func: () => sessionStorage.getItem('raahi.extension.auction-tab') === '1'});
      if (marked[0]?.result) return auctionTab = saved;
    } catch (_) {}
  }
  const tab = await chrome.tabs.create({url: 'https://www.eauctionsindia.com/', active: true});
  auctionTab = tab.id;
  await chrome.storage.local.set({auctionTab});
  return auctionTab;
}
async function execute(command) {
  const {method, args} = command;
  if (method === 'is_closed') return !auctionTab || !(await tabExists(auctionTab));
  const id = await getTab();
  if (method === 'goto') {
    if (!auctionUrl(args[0])) throw new Error('Only eAuctionsIndia HTTPS pages are allowed.');
    await chrome.tabs.update(id, {url: args[0]});
    await pause(400);
    const until = Date.now() + 60000;
    while (Date.now() < until) {
      const tab = await chrome.tabs.get(id);
      if (tab.status === 'complete' && !tab.pendingUrl && auctionUrl(tab.url) && new URL(tab.url).href === new URL(args[0]).href) {
        try { await chrome.scripting.executeScript({target: {tabId: id}, func: () => sessionStorage.setItem('raahi.extension.auction-tab', '1')}); } catch (_) {}
        return {status: null}; // DOM readiness/challenge detection happens in the scraper.
      }
      await pause(400);
    }
    throw new Error('Auction page did not finish loading within 60 seconds.');
  }
  if (method === 'bring_to_front') {
    const tab = await chrome.tabs.update(id, {active: true});
    await chrome.windows.update(tab.windowId, {focused: true});
    return null;
  }
  if (method === 'content') {
    const result = await chrome.scripting.executeScript({target: {tabId: id}, func: () => document.documentElement.outerHTML});
    return result[0].result;
  }
  if (method === 'fetch_asset') {
    const url = new URL(args[0]);
    if (url.protocol !== 'https:' || !['eauctionsindia.com', 'www.eauctionsindia.com', 'eauctionsindia.org', 'www.eauctionsindia.org'].includes(url.hostname) || !url.pathname.startsWith('/storage/')) throw new Error('Unsupported attachment URL');
    const result = await chrome.scripting.executeScript({target: {tabId: id}, world: 'MAIN', args: [url.href], func: async url => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 30000);
      try {
        const response = await fetch(url, {credentials: 'include', signal: controller.signal});
        const type = response.headers.get('content-type') || '';
        if (!response.ok || type.toLowerCase().includes('text/html')) return {status: response.status, type, data: null};
        const bytes = new Uint8Array(await response.arrayBuffer());
        if (bytes.length > 32 * 1024 * 1024) throw new Error('Attachment exceeds the connector size limit.');
        let binary = '';
        for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
        return {status: response.status, type, data: btoa(binary)};
      } finally {clearTimeout(timeout);}
    }});
    return result[0].result;
  }
  throw new Error('Unsupported browser operation');
}
async function connect() {
  if (running) return;
  pairing = input.value.trim();
  if (!/^[A-Za-z0-9_-]{43}$/.test(pairing)) {status.textContent = 'Paste the complete pairing code from the app.'; return;}
  await chrome.storage.local.set({pairing});
  running = true;
  while (running) {
    try {
      status.textContent = 'Connecting to Raahi…';
      const {command} = await request('/poll', {});
      status.textContent = 'Connected. Start scraping in the Raahi desktop app.';
      if (command && running) {
        let payload = {id: command.id};
        try {payload.result = await execute(command);} catch (error) {payload.error = error.message;}
        await request('/result', payload);
      }
    } catch (error) {
      status.textContent = error.message + ' Keep the desktop app open; retrying…';
      await pause(2500);
    }
  }
  status.textContent = 'Paused';
}
document.getElementById('connect').addEventListener('click', connect);
document.getElementById('disconnect').addEventListener('click', () => {running = false;});
chrome.storage.local.get('pairing').then(saved => {
  if (saved.pairing) {input.value = saved.pairing; connect();}
});
