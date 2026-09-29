// cdp-eval.mjs —— 对"正在进行的外包浏览器"执行一段 JS（经 CDP，零依赖）
//
// 用途：处理挡住流程的一次性弹窗（年龄确认 / Cookie 同意 / 新手引导层），
// 或者探查页面状态。不用人工去点，配合 askw.py 在调用进行中并行跑。
//
// 用法：
//   node cdp-eval.mjs "<js 表达式>" [url关键字]
//   node cdp-eval.mjs @脚本文件.js [url关键字]      # 从文件读 JS，免去转义地狱
//   node cdp-eval.mjs "document.title"
//   CDP_PORT=9223 node cdp-eval.mjs "..."
//
// 输出：{"ok":true,"result":...} / {"ok":false,"error":"..."}，失败退出码 1

import { readFileSync } from 'node:fs';

const PORT = Number(process.env.CDP_PORT || 9222);
const argExpr = process.argv[2];
const want = String(process.argv[3] || '').toLowerCase();

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
    }, 10000);
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
      reject(new Error('ws error（调试端口未开或拒绝连接）'));
    };
  });
}

async function main() {
  if (!argExpr) throw new Error('缺少 JS 表达式参数');
  const expr = argExpr.startsWith('@')
    ? readFileSync(argExpr.slice(1), 'utf8')
    : argExpr;
  const target = pickTarget(await listTargets());
  if (!target) throw new Error('没有可用页面（浏览器可能已关闭）');
  const res = await cdp(target.webSocketDebuggerUrl, 'Runtime.evaluate', {
    expression: expr,
    returnByValue: true,
    awaitPromise: true,
  });
  const err = res && res.exceptionDetails;
  if (err) throw new Error(err.text || 'JS 执行异常');
  process.stdout.write(JSON.stringify({
    ok: true, url: target.url || '', result: res && res.result ? res.result.value : null,
  }));
}

try {
  await main();
  process.exit(0);
} catch (e) {
  process.stdout.write(JSON.stringify({ ok: false, error: String(e.message || e) }));
  process.exit(1);
}
