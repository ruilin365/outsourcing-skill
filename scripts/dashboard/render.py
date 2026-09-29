# -*- coding: utf-8 -*-
"""
把 collect.py 产出的 data.json 渲染成一份离线单文件看板 dashboard.html，
并顺带产出人读版清单 checklist.md。

用法： python render.py [data.json] [输出.html]
"""

import argparse
import json
import os
import sys
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))

TPL = r"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Web AI 外包看板 · 站点与历史对话</title>
<style>
:root{
  --bg:#f4f6fa; --panel:#fff; --panel-2:#f8fafc; --text:#0f172a; --text-2:#475569; --muted:#94a3b8;
  --border:#e6ecf3; --accent:#2563eb; --accent-soft:#eaf1ff;
  --ok:#16a34a; --ok-soft:#e8f7ee; --warn:#d97706; --warn-soft:#fdf3e3;
  --info:#0891b2; --info-soft:#e3f6fa; --gray-soft:#eef1f5;
  --shadow:0 1px 2px rgba(15,23,42,.05), 0 8px 24px -12px rgba(15,23,42,.12);
  --radius:14px;
}
html[data-theme="dark"]{
  --bg:#0b1120; --panel:#131c2e; --panel-2:#0f1728; --text:#e8eef7; --text-2:#b3c0d3; --muted:#7b8aa3;
  --border:#223049; --accent:#60a5fa; --accent-soft:#17233c;
  --ok:#4ade80; --ok-soft:#122c20; --warn:#fbbf24; --warn-soft:#312408;
  --info:#22d3ee; --info-soft:#0d2f38; --gray-soft:#1c2740;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 10px 30px -14px rgba(0,0,0,.6);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",system-ui,sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 64px}
header.top{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;justify-content:space-between;margin-bottom:22px}
h1{margin:0;font-size:24px;letter-spacing:-.2px}
.sub{color:var(--muted);font-size:13px;margin-top:6px}
.sub code{background:var(--gray-soft);padding:1px 6px;border-radius:6px;font-size:12px}
button,select,input{font:inherit;color:inherit}
.btn{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:7px 12px;cursor:pointer;box-shadow:var(--shadow)}
.btn:hover{border-color:var(--accent);color:var(--accent)}
.btn.on{background:var(--accent);border-color:var(--accent);color:#fff}
.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
#q{flex:0 1 240px;min-width:170px;background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:7px 12px}
.ops{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.opgroup{display:inline-flex;gap:4px;align-items:center;padding:4px;border:1px solid var(--border);border-radius:12px;background:var(--panel);box-shadow:var(--shadow)}
.opgroup .btn,.opgroup .autosw{border-color:transparent;box-shadow:none;background:transparent}
.opgroup .btn:hover{border-color:var(--border);background:var(--panel-2);color:var(--accent)}
.opgroup .autosw:hover{background:var(--panel-2)}
.opgroup .autosw.on{background:var(--accent-soft)}

.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:20px}
@media (max-width:820px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
.stat{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);padding:14px 16px;box-shadow:var(--shadow)}
.stat .n{font-size:26px;font-weight:650;letter-spacing:-.5px}
.stat .l{color:var(--muted);font-size:12.5px;margin-top:2px}
.stat.accent{border-color:var(--accent);background:var(--accent-soft)}
.stat.accent .n{color:var(--accent)}

.tabs{display:flex;gap:6px;border-bottom:1px solid var(--border);margin:22px 0 18px;overflow:auto}
.tab{padding:9px 14px;border-radius:10px 10px 0 0;border:1px solid transparent;cursor:pointer;white-space:nowrap;color:var(--text-2)}
.tab:hover{background:var(--panel-2)}
.tab.on{background:var(--panel);border-color:var(--border);border-bottom-color:var(--panel);color:var(--text);font-weight:600}
.panel{display:none}
.panel.on{display:block}

.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);padding:16px;box-shadow:var(--shadow)}
.card h3{margin:0 0 2px;font-size:16px;display:flex;align-items:center;gap:8px}
.card .host{color:var(--muted);font-size:12.5px;word-break:break-all}
.row{display:flex;justify-content:space-between;gap:10px;font-size:13px;padding:4px 0;border-bottom:1px dashed var(--border)}
.row:last-child{border-bottom:0}
.row .k{color:var(--muted)}
.badge{font-size:11.5px;padding:2px 8px;border-radius:999px;font-weight:600;white-space:nowrap}
.b-ok{background:var(--ok-soft);color:var(--ok)}
.b-info{background:var(--info-soft);color:var(--info)}
.b-warn{background:var(--warn-soft);color:var(--warn)}
.b-gray{background:var(--gray-soft);color:var(--text-2)}
.bar{height:6px;border-radius:999px;background:var(--gray-soft);overflow:hidden;margin-top:8px}
.bar>i{display:block;height:100%;background:var(--accent)}
.ev{margin:10px 0 0;padding:0;list-style:none;font-size:12.5px;color:var(--text-2)}
.ev li{padding:2px 0 2px 14px;position:relative}
.ev li:before{content:"";position:absolute;left:2px;top:11px;width:5px;height:5px;border-radius:50%;background:var(--muted)}
a{color:var(--accent);text-decoration:none;word-break:break-all}
a:hover{text-decoration:underline}

table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;box-shadow:var(--shadow)}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);font-size:13.5px;vertical-align:top}
th{background:var(--panel-2);font-size:12.5px;color:var(--text-2);font-weight:600;white-space:nowrap}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover{background:var(--panel-2)}
.mono{font-family:ui-monospace,Consolas,Menlo,monospace;font-size:12px;color:var(--text-2)}
.wraptbl{overflow-x:auto;border-radius:var(--radius)}
details{margin-top:8px}
summary{cursor:pointer;color:var(--accent);font-size:13px}
.kv{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;font-size:13px;margin-top:8px}
.kv .k{color:var(--muted)}
pre.prm{background:var(--panel-2);border:1px solid var(--border);border-radius:10px;padding:10px;font-size:12.5px;white-space:pre-wrap;word-break:break-word;max-height:220px;overflow:auto;margin:8px 0 0}
.tl{position:relative;padding-left:22px}
.tl:before{content:"";position:absolute;left:6px;top:6px;bottom:6px;width:2px;background:var(--border)}
.tl .it{position:relative;background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:12px 14px;margin-bottom:10px;box-shadow:var(--shadow)}
.tl .it:before{content:"";position:absolute;left:-20px;top:18px;width:10px;height:10px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 3px var(--bg)}
.tl .it.err:before{background:#dc2626}
.tl .hd{display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between}
.tl .t{font-weight:600}
.tl .meta{color:var(--muted);font-size:12px}
.note{margin-top:26px;background:var(--panel);border:1px solid var(--border);border-radius:var(--radius);padding:16px;color:var(--text-2);font-size:13px;box-shadow:var(--shadow)}
.note h4{margin:0 0 8px;color:var(--text);font-size:14px}
.note code{background:var(--gray-soft);padding:1px 6px;border-radius:6px;font-size:12px}
.empty{padding:28px;text-align:center;color:var(--muted);background:var(--panel);border:1px dashed var(--border);border-radius:var(--radius)}
.qedit{cursor:pointer;border-bottom:1px dashed var(--accent);color:var(--accent);padding:0 3px;border-radius:4px}
.qedit:hover{background:var(--accent-soft)}
.live{font-size:11.5px;padding:3px 9px;border-radius:999px;font-weight:600;white-space:nowrap;background:var(--gray-soft);color:var(--text-2)}
.live.on{background:var(--ok-soft);color:var(--ok)}
.live.off{background:var(--warn-soft);color:var(--warn)}
.autosw{display:inline-flex;align-items:center;gap:6px;background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:6px 10px;cursor:pointer;font-size:13px;white-space:nowrap;box-shadow:var(--shadow)}
.autosw:hover{border-color:var(--accent);color:var(--accent)}
.autosw.on{border-color:var(--accent);background:var(--accent-soft);color:var(--accent)}
.autosw input{accent-color:var(--accent);cursor:pointer;margin:0}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div>
      <h1>Web AI 外包 · 站点与历史对话看板</h1>
      <div class="sub" id="metaLine"></div>
    </div>
    <div class="toolbar">
      <input id="q" placeholder="搜索：站点 / 对话标题 / 提示词">
      <div class="ops">
        <span class="live" id="liveBadge">离线快照</span>
        <div class="opgroup">
          <button class="btn" id="refreshBtn" title="从数据库重新取数并重画页面（毫秒级）">刷新页面</button>
          <label class="autosw" title="每 30 秒自动刷新一次页面"><input type="checkbox" id="autoRefresh">自动 30s</label>
        </div>
        <div class="opgroup">
          <button class="btn" id="scanBtn" title="扫描 Edge profile 的 Cookie / 登录态 / 浏览历史，增量入库（约 1-2 秒）">重新扫描浏览器 profile</button>
          <label class="autosw" title="每 5 分钟自动扫描一次浏览器 profile"><input type="checkbox" id="autoScan">自动 5min</label>
        </div>
        <button class="btn" id="themeBtn">深色</button>
      </div>
    </div>
  </header>

  <section class="stats" id="stats"></section>

  <nav class="tabs" id="tabs">
    <div class="tab on" data-p="sites">站点与登录态</div>
    <div class="tab" data-p="convs">历史对话</div>
    <div class="tab" data-p="calls">调用流水</div>
    <div class="tab" data-p="files">本地产出</div>
  </nav>

  <section class="panel on" id="p-sites"><div class="grid" id="sitesGrid"></div></section>

  <section class="panel" id="p-convs">
    <div class="wraptbl"><table id="convTbl">
      <thead><tr><th>站点</th><th>对话</th><th>会话名</th><th>首次</th><th>最近</th><th>访问</th><th>调用</th><th>答案字数</th><th>链接</th></tr></thead>
      <tbody></tbody></table></div>
  </section>

  <section class="panel" id="p-calls"><div class="tl" id="callList"></div></section>

  <section class="panel" id="p-files">
    <div class="wraptbl"><table id="fileTbl">
      <thead><tr><th>文件</th><th>大小</th><th>更新时间</th><th>说明</th></tr></thead>
      <tbody></tbody></table></div>
    <div class="wraptbl" style="margin-top:14px"><table id="noteTbl">
      <thead><tr><th>早期/文档型产出</th><th>归属对话</th><th>大小</th><th>时间</th></tr></thead>
      <tbody></tbody></table></div>
  </section>

  <div class="note" id="srcNote"></div>
</div>

<script id="DATA" type="application/json">__DATA__</script>
<script>
(function(){
  var D = JSON.parse(document.getElementById('DATA').textContent);
  var esc = function(s){ return String(s==null?'':s).replace(/[&<>"']/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); };
  var SITE = {}; D.providers.forEach(function(p){ SITE[p.id] = p; });
  var SNAME = {signed_in:'已登录',signed_in_2:''};
  function statLabel(s){
    return { 'signed-in':'已登录', 'anonymous':'游客/免登录', 'not-signed-in':'未登录', 'unused':'未使用' }[s] || s;
  }
  function statClass(s){
    return { 'signed-in':'b-ok', 'anonymous':'b-info', 'not-signed-in':'b-warn', 'unused':'b-gray' }[s] || 'b-gray';
  }
  function convName(u){
    if(!u) return null;
    var s = D.sessions.filter(function(x){return x.url===u;})[0];
    return s ? s.name : null;
  }
  function convTitle(u){
    var c = D.conversations.filter(function(x){return x.url===u;})[0];
    return c ? c.title : (u ? u.replace(/^https?:\/\//,'').slice(0,28)+'…' : '—');
  }
  function fmtBytes(n){ n=+n||0; return n>1024*1024 ? (n/1048576).toFixed(1)+' MB' : (n/1024).toFixed(1)+' KB'; }
  function short(s,n){ s=String(s||''); return s.length>n? s.slice(0,n)+'…' : s; }

  /* ---------- 概览（每次刷新都要重画） ---------- */
  function updateMeta(){
    var T = D.totals, DB = D.db || {};
    var demoTag = D.demo ? '<span class="badge b-warn">示例数据 · 全部虚构</span> ' : '';
    document.getElementById('metaLine').innerHTML = demoTag +
      '渲染于 <b>' + esc(D.generatedAt) + '</b> · 数据源 <code>' + esc(DB.path || 'data.json') + '</code>' +
      (DB.lastCallAt ? ' · 最后一次外包调用 <b>' + esc(DB.lastCallAt) + '</b>' : '') +
      (DB.lastScanAt ? ' · 最后扫描 ' + esc(DB.lastScanAt) : '') +
      ' · 调用共计 <b>' + T.calls + '</b> 次';
    document.getElementById('stats').innerHTML = [
      statCard(T.todayCalls||0, '今日调用', 'accent'),
      statCard(T.sitesUsed+' / '+T.sites, '站点：用过 / 支持'),
      statCard(T.signedIn, '已登录站点'),
      statCard(T.conversations, '历史对话'),
      statCard(T.sessions, '已命名会话'),
      statCard(T.okCalls+' / '+T.calls, '调用：成功 / 总数'),
      statCard((T.answerChars/10000).toFixed(1)+' 万字', '累计取回答案'),
      statCard(T.avgSec+' s', '平均单次耗时')
    ].join('');
  }
  function statCard(n,l,cls){ return '<div class="stat'+(cls?' '+cls:'')+'"><div class="n">'+esc(n)+'</div><div class="l">'+esc(l)+'</div></div>'; }

  /* ---------- 站点 ---------- */
  function quotaBar(pid){
    var q = D.quota.filter(function(x){return x.provider===pid;})[0];
    if(!q) return '';
    var pct = Math.min(100, Math.round(q.calls/q.dailyQuota*100));
    return '<div class="row"><span class="k">今日配额</span>'+
           '<span><b>'+q.calls+'</b> / <span class="qedit" data-provider="'+esc(pid)+'" title="点击可改每日上限">'+q.dailyQuota+'</span></span></div>'+
           '<div class="bar"><i style="width:'+pct+'%"></i></div>'+
           (q.totalCalls>q.calls ? '<div class="row"><span class="k">历史累计</span><span>'+q.totalCalls+' 次</span></div>' : '');
  }
  function siteCard(p){
    return '<div class="card" data-search="'+esc((p.name+' '+p.url+' '+statLabel(p.loginState)).toLowerCase())+'">'+
      '<h3>'+esc(p.name)+' <span class="badge '+statClass(p.loginState)+'">'+statLabel(p.loginState)+'</span>'+
      (p.enabled?'':' <span class="badge b-gray">未启用</span>')+'</h3>'+
      '<div class="host">'+esc(p.url)+'</div>'+
      '<div style="margin-top:10px">'+
        '<div class="row"><span class="k">历史对话</span><span>'+p.conversations+'</span></div>'+
        '<div class="row"><span class="k">外包调用</span><span>'+p.calls+(p.todayCalls?'（今日 '+p.todayCalls+'）':'')+'</span></div>'+
        '<div class="row"><span class="k">页面访问</span><span>'+p.visits+' 次</span></div>'+
        '<div class="row"><span class="k">最近活动</span><span>'+esc(p.lastVisit||'—')+
          (p.lastVisitSource?' <span class="badge b-gray">'+esc(p.lastVisitSource)+'</span>':'')+'</span></div>'+
        quotaBar(p.id)+
      '</div>'+
      '<ul class="ev">'+ p.evidence.map(function(e){return '<li>'+esc(e)+'</li>';}).join('') +'</ul>'+
      (p.note?'<div class="sub" style="margin-top:8px">'+esc(p.note)+'</div>':'')+
    '</div>';
  }

  /* ---------- 对话表 ---------- */
  function convRow(c){
    var calls = D.calls.filter(function(x){ return x.chatUrl===c.url; });
    var rows = calls.map(function(x){
      return '<div class="row"><span class="k">'+esc(x.startedAt||'')+'</span>'+
        '<span>'+(x.status==='success'?'✓ 成功':'✗ '+esc(x.status))+' · '+x.chars+' 字 · '+
        Math.round((x.elapsedMs||0)/1000)+'s · '+esc(x.id)+'</span></div>';
    }).join('');
    return '<tr data-search="'+esc((c.title+' '+c.provider+' '+(c.session||'')+' '+c.url).toLowerCase())+'">'+
      '<td>'+esc((SITE[c.provider]||{}).name||c.provider)+'</td>'+
      '<td><b>'+esc(c.title)+'</b>'+
        (c.kind==='entry'?' <span class="badge b-gray">入口页·非对话</span>':'')+
        (rows?'<details><summary>本对话的 '+calls.length+' 次调用</summary>'+rows+'</details>':
              '<div class="sub" style="margin:0">无 CLI 调用记录</div>')+'</td>'+
      '<td>'+(c.session?'<span class="badge b-ok">'+esc(c.session)+'</span>':'<span class="sub">—</span>')+'</td>'+
      '<td class="mono">'+esc(c.firstVisit||'—')+'</td>'+
      '<td class="mono">'+esc(c.lastVisit||'—')+'</td>'+
      '<td>'+c.visits+'</td>'+
      '<td>'+c.calls+'</td>'+
      '<td>'+(c.answerChars?(c.answerChars/1000).toFixed(1)+'k':'—')+'</td>'+
      '<td><a href="'+esc(c.url)+'" target="_blank" rel="noopener">打开</a></td>'+
    '</tr>';
  }

  /* ---------- 调用流水 ---------- */
  function callItem(x){
    var lines = [];
    if(x.prompt) lines.push(x.prompt);
    if(x.answerHead) lines.push('— 答案开头 —\n'+x.answerHead);
    if(x.error) lines.push('— 错误 —\n'+x.error);
    var det = lines.length ? '<details><summary>提示词 / 返回内容</summary><pre class="prm">'+esc(lines.join('\n\n'))+'</pre></details>' : '';
    if(x.shot){
      det += '<div style="margin-top:6px"><a href="'+esc(x.shot)+'" target="_blank" rel="noopener">'+
             '查看失败现场截图</a> <span class="sub" style="margin:0">（调用出错时自动抓的浏览器画面）</span></div>';
    }
    return '<div class="it'+(x.status==='success'?'':' err')+'" data-search="'+esc(((x.id||'')+' '+(x.prompt||'')+' '+convTitle(x.chatUrl)).toLowerCase())+'">'+
      '<div class="hd"><span class="t">'+esc(x.id)+' · '+esc(convTitle(x.chatUrl))+'</span>'+
      '<span class="meta">'+esc(x.startedAt||'')+'</span></div>'+
      '<div class="meta">'+(x.status==='success'
          ? '<span class="badge b-ok">成功</span>'
          : '<span class="badge b-warn">'+esc(x.status)+'</span>')+
        ' · '+esc((SITE[x.provider]||{}).name||x.provider||'—') +
        ' · '+Math.round((x.elapsedMs||0)/1000)+' s'+
        (x.chars?' · '+x.chars+' 字':'')+
        (x.cached?' · 命中缓存':'')+
        (x.promptFile?' · 提示词 <span class="mono">'+esc(x.promptFile)+'</span>':'')+
      '</div>'+
      '<div style="font-size:13px;color:var(--text-2);margin-top:6px">'+esc(short(x.prompt? x.prompt.replace(/\s+/g,' ') : (x.error||''),150))+'</div>'+
      det+
    '</div>';
  }

  /* ---------- 数据来源：优先本地服务（可刷新 / 可改配额），失败回退内嵌快照 ---------- */
  var LIVE = false, timerRefresh = null, timerScan = null;
  function setStatus(txt, cls){
    var el = document.getElementById('liveBadge');
    el.textContent = txt;
    el.className = 'live' + (cls ? ' ' + cls : '');
  }
  function applyQuotaOverride(){
    var o = {};
    try{ o = JSON.parse(localStorage.getItem('wa-quota')||'{}'); }catch(e){}
    Object.keys(o).forEach(function(k){
      D.quota.forEach(function(q){ if(q.provider===k) q.dailyQuota = o[k]; });
    });
  }
  function applyData(d){
    D = d;
    applyQuotaOverride();
    render();
    updateMeta();
  }
  function refresh(manual){
    return fetch('api/data', {cache:'no-store'})
      .then(function(r){ if(!r.ok) throw new Error('HTTP '+r.status); return r.json(); })
      .then(function(d){
        LIVE = true;
        applyData(d);
        setStatus('实时 · ' + String(d.generatedAt||'').slice(11), 'on');
      })
      .catch(function(){
        LIVE = false;
        setStatus(manual ? '离线快照（用 serve.py 打开才能刷新）' : '离线快照', 'off');
      });
  }
  function saveQuota(pid, val){
    if(LIVE){
      fetch('api/quota', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({provider: pid, dailyQuota: val})})
        .then(function(r){ return r.json(); })
        .then(function(j){
          if(j.ok){ setStatus('配额已写入数据库', 'on'); refresh(false); }
          else{ alert('保存失败：' + (j.error||'未知错误')); }
        })
        .catch(function(){ alert('保存失败：服务未响应'); });
    }else{
      var o = {};
      try{ o = JSON.parse(localStorage.getItem('wa-quota')||'{}'); }catch(e){}
      o[pid] = val;
      try{ localStorage.setItem('wa-quota', JSON.stringify(o)); }catch(e){}
      applyQuotaOverride();
      render(); updateMeta();
      setStatus('离线模式：配额只存在本浏览器', 'off');
    }
  }

  var state = {tab:'sites', q:''};
  function render(){
    document.getElementById('sitesGrid').innerHTML = D.providers.map(siteCard).join('');
    document.querySelector('#convTbl tbody').innerHTML = D.conversations.map(convRow).join('') ||
      '<tr><td colspan="9" style="text-align:center;color:var(--muted)">暂无数据</td></tr>';
    document.getElementById('callList').innerHTML = D.calls.map(callItem).join('') ||
      '<div class="empty">暂无调用记录</div>';
    var outs = D.outputs.slice().sort(function(a,b){
      return String(a.mtime||'').localeCompare(String(b.mtime||'')); });
    outs.forEach(function(o,i){ o._latest = (i === outs.length - 1); });
    document.querySelector('#fileTbl tbody').innerHTML = outs.map(function(o){
      return '<tr><td class="mono">'+esc(o.file)+'</td><td>'+fmtBytes(o.size)+'</td><td class="mono">'+esc(o.mtime)+'</td>'+
        '<td>'+(o._latest?'当前最终版本':'版本备份')+'</td></tr>';
    }).join('');
    document.querySelector('#noteTbl tbody').innerHTML = D.notes.map(function(n){
      return '<tr><td>'+esc(n.file)+'<div class="sub" style="margin:0">'+esc(n.note)+'</div></td>'+
        '<td>'+(n.conversation?'<span class="badge b-info">'+esc(n.conversation)+'</span><div class="sub" style="margin:0">按时间推断</div>':'—')+'</td>'+
        '<td>'+fmtBytes(n.size)+'</td><td class="mono">'+esc(n.mtime)+'</td></tr>';
    }).join('');
    applyFilter();
  }

  function applyFilter(){
    var q = state.q.trim().toLowerCase();
    ['sitesGrid','convTbl','callList'].forEach(function(id){
      var root = document.getElementById(id);
      var items = id==='convTbl' ? root.querySelectorAll('tbody tr')
                : root.querySelectorAll('[data-search]');
      items.forEach(function(el){
        var hit = !q || (el.getAttribute('data-search')||'').indexOf(q) >= 0;
        el.style.display = hit ? '' : 'none';
      });
    });
  }

  document.getElementById('q').addEventListener('input', function(e){ state.q = e.target.value; applyFilter(); });
  document.getElementById('tabs').addEventListener('click', function(e){
    var t = e.target.closest('.tab'); if(!t) return;
    state.tab = t.dataset.p;
    document.querySelectorAll('.tab').forEach(function(x){ x.classList.toggle('on', x===t); });
    document.querySelectorAll('.panel').forEach(function(x){ x.classList.toggle('on', x.id==='p-'+state.tab); });
  });
  document.getElementById('themeBtn').addEventListener('click', function(){
    var r = document.documentElement;
    var dark = r.getAttribute('data-theme')==='dark';
    r.setAttribute('data-theme', dark?'light':'dark');
    this.textContent = dark?'深色':'浅色';
    try{ localStorage.setItem('wa-dash-theme', dark?'light':'dark'); }catch(e){}
  });
  try{ var t0=localStorage.getItem('wa-dash-theme'); if(t0){ document.documentElement.setAttribute('data-theme',t0);
    document.getElementById('themeBtn').textContent = t0==='dark'?'浅色':'深色'; } }catch(e){}

  /* ---------- 刷新页面 / 重新扫描浏览器 profile / 改配额 ---------- */
  var SCAN_LABEL = '重新扫描浏览器 profile';
  function doScan(silent){
    var btn = document.getElementById('scanBtn');
    btn.disabled = true; btn.textContent = '扫描浏览器中…';
    setStatus('正在扫描浏览器 profile…');
    return fetch('api/scan').then(function(r){ return r.json(); }).then(function(j){
      btn.disabled = false; btn.textContent = SCAN_LABEL;
      if(j.ok){
        setStatus('扫描完成 · 已增量入库', 'on');
        return refresh(false);
      }
      if(!silent) alert('扫描失败：' + (j.error || (j.output||[]).join(' ')));
      setStatus('扫描失败（看服务是否在跑）', 'off');
    }).catch(function(){
      btn.disabled = false; btn.textContent = SCAN_LABEL;
      if(!silent) setStatus('离线快照（用 serve.py 打开才能扫描）', 'off');
    });
  }
  document.getElementById('refreshBtn').addEventListener('click', function(){
    setStatus('刷新中…');
    refresh(true);
  });
  document.getElementById('autoRefresh').addEventListener('change', function(){
    var on = this.checked;
    this.parentNode.classList.toggle('on', on);
    if(timerRefresh){ clearInterval(timerRefresh); timerRefresh = null; }
    if(on){
      refresh(false);
      timerRefresh = setInterval(function(){ refresh(false); }, 30000);
    }
  });
  document.getElementById('autoScan').addEventListener('change', function(){
    var on = this.checked;
    this.parentNode.classList.toggle('on', on);
    if(timerScan){ clearInterval(timerScan); timerScan = null; }
    if(on){
      doScan(true);
      timerScan = setInterval(function(){ doScan(true); }, 300000);
    }
  });
  document.getElementById('scanBtn').addEventListener('click', function(){ doScan(false); });
  document.addEventListener('click', function(e){
    var el = (e.target && e.target.closest) ? e.target.closest('.qedit') : null;
    if(!el) return;
    var pid = el.getAttribute('data-provider');
    var v = prompt('设置「' + pid + '」的每日配额上限：', el.textContent.trim());
    if(v === null) return;
    v = parseInt(v, 10);
    if(!v || v < 1){ alert('请输入大于 0 的整数'); return; }
    saveQuota(pid, v);
  });

  document.getElementById('srcNote').innerHTML =
    '<h4>数据是怎么来的（本地 SQLite 持久库 + 只读扫描）</h4>'+
    '所有记录都存在同目录的 <code>web-ai.db</code>（SQLite）里，本页只负责读取渲染，<b>不再每次重扫</b>。'+
    '<br>· <b>实时</b>：每次外包调用由 <code>askw.py</code> 当场写一条调用流水（站点、会话名、耗时、字数、对话 URL）。'+
    '<br>· <b>慢变</b>：站点清单取自工具配置 <code>'+esc(D.sources.tool)+'\\config\\default.json</code>；'+
    '登录态依据 profile 里的 Cookie / localStorage 凭据；历史对话与标题取自 Edge 浏览历史；'+
    '会话名取自 <code>~/.agent-web-ai/chats.json</code>。这些由 <code>collect.py --to-db</code> 增量补全，只增不改。'+
    '<br>· <b>今日配额</b>：按当天实际调用数实时统计（历史调用不计入今日）；点配额数字即可改每日上限。'+
    '<br><br><b>怎么让按钮生效</b>：直接双击本文件打开是离线快照，没有数据可拉。'+
    '要「刷新页面」「重新扫描浏览器 profile」、自动刷新、页面内改配额，用 <code>python serve.py</code> 启动本地服务后从 '+
    '<code>http://127.0.0.1:8787/dashboard.html</code> 打开。'+
    '<br>· <b>刷新页面</b>：只读数据库重画（毫秒级），能看到新入库的外包调用与配额改动。'+
    '<br>· <b>重新扫描浏览器 profile</b>：读 Edge 的 Cookie / 登录态 / 浏览历史并增量入库（约 1-2 秒），'+
    '浏览器里的登录变化、新对话、访问次数靠它更新。'+
    '本页完全离线，不含任何脚本外链，也不会上传数据；服务只监听本机。';

  applyQuotaOverride();
  updateMeta();
  render();
  refresh(false);
})();
</script>
</body>
</html>
"""


def render_markdown(d, path):
    """同步产出一份人读清单，便于直接查看或丢进文档里。"""
    T = d["totals"]
    L = []
    L.append("# Web AI 外包站点与对话清单\n")
    db = d.get("db") or {}
    L.append("> 渲染时间：%s ｜ 数据源：`%s` ｜ 最后扫描：%s ｜ 最后一次调用：%s\n" % (
        d["generatedAt"], db.get("path", "data.json"),
        db.get("lastScanAt") or "—", db.get("lastCallAt") or "—"))
    L.append("## 总览\n")
    L.append("| 指标 | 数值 |")
    L.append("| --- | --- |")
    L.append("| 支持站点 / 已使用 | %d / %d |" % (T["sites"], T["sitesUsed"]))
    L.append("| 已登录站点 | %d |" % T["signedIn"])
    L.append("| 历史对话 | %d 个 |" % T["conversations"])
    L.append("| 已命名会话 | %d 个 |" % T["sessions"])
    L.append("| 外包调用 | %d 次（成功 %d） |" % (T["calls"], T["okCalls"]))
    L.append("| 累计取回答案 | %.1f 万字 |" % (T["answerChars"] / 10000))
    L.append("| 平均单次耗时 | %.1f 秒 |" % T["avgSec"])
    L.append("\n## 一、站点与登录态\n")
    L.append("| 站点 | 地址 | 登录状态 | 对话数 | 调用数 | 最近活动 |")
    L.append("| --- | --- | --- | --- | --- | --- |")
    zh = {"signed-in": "已登录", "anonymous": "游客/免登录",
          "not-signed-in": "未登录", "unused": "未使用"}
    for p in d["providers"]:
        L.append("| %s | %s | %s | %s | %s | %s |" % (
            p["name"], p["url"], zh.get(p["loginState"], p["loginState"]),
            p["conversations"], p["calls"], p["lastVisit"] or "—"))
    L.append("\n### 判定依据\n")
    for p in d["providers"]:
        if p["visits"] or p["cookies"]:
            L.append("- **%s**：%s" % (p["name"], "；".join(p["evidence"])))
    L.append("\n## 二、历史对话\n")
    L.append("| 站点 | 对话标题 | 会话名 | 首次访问 | 最近访问 | 调用 | 答案字数 | 链接 |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for c in d["conversations"]:
        L.append("| %s | %s | %s | %s | %s | %s | %s | [打开](%s) |" % (
            c["provider"], c["title"], c["session"] or "—",
            c["firstVisit"] or "—", c["lastVisit"] or "—",
            c["calls"], ("%.1fk" % (c["answerChars"] / 1000)) if c["answerChars"] else "—",
            c["url"]))
    L.append("\n> 「会话名」是外包 skill 里 `--session` 登记的名字，等于一个任务的永久锚点，用它可以在同一对话里续聊。\n")
    L.append("\n## 三、调用流水\n")
    L.append("| 时间 | 编号 | 站点 | 结果 | 耗时 | 字数 | 所属对话 | 提示词 |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for x in d["calls"]:
        title = None
        for c in d["conversations"]:
            if c["url"] == x["chatUrl"]:
                title = c["title"]
        L.append("| %s | %s | %s | %s | %ss | %s | %s | %s |" % (
            (x["startedAt"] or "").split(" ")[-1], x["id"], x["provider"] or "—",
            "成功" if x["status"] == "success" else x["status"],
            round((x["elapsedMs"] or 0) / 1000), x["chars"] or "—",
            title or "—", (x["prompt"] or "").replace("\n", " ")[:34].replace("|", "/") or "—"))
    L.append("\n## 四、本地产出\n")
    for o in d["outputs"]:
        L.append("- `%s` — %.1f KB — %s" % (o["file"], o["size"] / 1024, o["mtime"]))
    L.append("\n### 早期 / 文档型产出\n")
    for n in d["notes"]:
        L.append("- `%s` — %s — 归属对话：%s（按时间推断）" % (
            n["file"], n["note"], n["conversation"] or "未确定"))
    L.append("""
## 五、数据怎么存 / 怎么刷新

数据存在同目录的 `web-ai.db`（SQLite 持久库），看板只读渲染、不再重扫：

| 环节 | 谁来做 | 频率 |
| --- | --- | --- |
| 调用流水（实时） | `askw.py` 每次外包后自动写一条 | 每次调用 |
| 站点 / 登录态 / 历史对话（慢变） | `collect.py --to-db` 增量补全，只增不改 | 想看最新时跑一次 |
| 渲染 | `render.py` 从库取数 | 随时 |
| 人读表格 | `store.export_csv()` → `web-ai-*.csv` | 需要时 |

```bash
cd <你的产出目录>
python askw.py ask -p deepseek --session 任务名 --file 需求.txt   # 外包，自动入库
python collect.py --to-db --tasks "目录A,目录B"                   # 可选：补站点/对话信息
python render.py                                                  # 从库渲染看板
```

数据全部来自本机，看板文件离线可用，不联网、不上传。
凭据只记录长度与指纹，不会写入任何明文。
""")
    open(path, "w", encoding="utf-8").write("\n".join(L))


def main():
    ap = argparse.ArgumentParser(description="把数据渲染成离线单文件看板 dashboard.html")
    ap.add_argument("src", nargs="?", help="data.json 路径（默认同目录 data.json）")
    ap.add_argument("out", nargs="?", help="输出 dashboard.html 路径")
    ap.add_argument("--db", help="SQLite 库路径（默认同目录 web-ai.db）")
    ap.add_argument("--from-db", action="store_true", help="强制从 SQLite 库取数")
    ap.add_argument("--from-json", action="store_true", help="强制从 data.json 取数")
    args = ap.parse_args()

    db_path = args.db or os.path.join(HERE, "web-ai.db")
    use_db = args.from_db or (not args.from_json and not args.src and os.path.exists(db_path))

    if use_db:
        sys.path.insert(0, HERE)
        import store
        con = store.connect(db_path)
        data = store.build_data(con)
        con.close()
        print("source: sqlite", db_path)
    else:
        src = args.src or os.path.join(HERE, "data.json")
        data = json.load(open(src, encoding="utf-8"))
        print("source: json", src)

    out = args.out or os.path.join(HERE, "dashboard.html")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    html = TPL.replace("__DATA__", payload)
    html = html.replace("__GENERATED__", dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
    open(out, "w", encoding="utf-8").write(html)
    print("written:", out, os.path.getsize(out), "bytes")

    md = os.path.join(os.path.dirname(os.path.abspath(out)), "checklist.md")
    render_markdown(data, md)
    print("written:", md, os.path.getsize(md), "bytes")


if __name__ == "__main__":
    main()
