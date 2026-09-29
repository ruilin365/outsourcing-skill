// shot.mjs —— 对"正在进行的外包浏览器"截图（经 CDP，无需额外依赖）
//
// 用途：ask-web-ai 调用在线 AI 时如果出问题（登录失效 / 限流 / 验证码 / 页面改版
// 找不到输入框 / 卡住不动），一行文字日志说明不了现场。这个脚本通过调试端口
// 直接抓取浏览器当前画面，用于事后定位。
//
// 用法：
//   node shot.mjs <输出.png> [url关键字]
//   CDP_PORT=9223 node shot.mjs out.png deepseek
//
// 成功：stdout 打印 {"ok":true,...}，退出码 0
// 失败：stdout 打印 {"ok":false,"error":"..."}，退出码 1（调用方据此降级）

import { writeFileSync } from 'node:fs';

const PORT = Number(process.env.CDP_PORT || 9222);
const outPath = process.argv[2] || 'shot.png';
const want = String(process.argv[3] || '').toLowerCase();

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function listTargets() {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 2500);
  try {
    const r = await fetch(`http://127.0.0.1:${PORT}/json/list`, { signal: ctl.signal });
    return await r.json();
  } finally {
    clearTimeout(timer);
  }
}

function pickTarget(list) {
  const pages = (list || []).filter(
    (t) => t && t.type === 'page' && t.webSocketDebuggerUrl &&
           !String(t.url || '').startsWith('devtools://')
  );
  if (!pages.length) return null;
  if (want) {
    const hit = pages.find((p) => String(p.url || '').toLowerCase().includes(want));
    if (hit) return hit;
  }
  return pages[0];
}

function cdp(wsUrl, method, params) {
  return new Promise((resolve, reject) => {
    let ws;
    try {
      ws = new WebSocket(wsUrl);
    } catch (e) {
      return reject(new Error('open ws failed: ' + e.message));
    }
    const id = 1;
    const timer = setTimeout(() => {
      try { ws.close(); } catch (e) {}
      reject(new Error('cdp timeout'));
    }, 8000);
    ws.onopen = () => ws.send(JSON.stringify({ id, method, params: params || {} }));
    ws.onmessage = (ev) => {
      let m;
      try { m = JSON.parse(ev.data); } catch (e) { return; }
      if (m.id !== id) return;
      clearTimeout(timer);
      try { ws.close(); } catch (e) {}
      if (m.error) reject(new Error(m.error.message || JSON.stringify(m.error)));
      else resolve(m.result);
    };
    ws.onerror = () => {
      clearTimeout(timer);
      reject(new Error('ws error（调试端口可能未开启或拒绝连接）'));
    };
  });
}

async function main() {
  const list = await listTargets();
  const target = pickTarget(list);
  if (!target) throw new Error('没有可截图的页面（浏览器可能已关闭）');
  const res = await cdp(target.webSocketDebuggerUrl, 'Page.captureScreenshot', {
    format: 'png',
    captureBeyondViewport: false,
  });
  if (!res || !res.data) throw new Error('截图返回为空');
  writeFileSync(outPath, Buffer.from(res.data, 'base64'));
  process.stdout.write(JSON.stringify({
    ok: true, file: outPath, url: target.url || '', title: target.title || '',
  }));
}

try {
  await main();
  process.exit(0);
} catch (e) {
  process.stdout.write(JSON.stringify({ ok: false, error: String(e.message || e) }));
  process.exit(1);
}
