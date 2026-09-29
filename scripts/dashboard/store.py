# -*- coding: utf-8 -*-
"""
store.py —— Web AI 外包看板的持久化数据层（SQLite）

为什么要它：
    以前是「每次重扫 profile → 覆盖 data.json → 重渲染 html」，
    采集是无状态的全量重建，历史随浏览器 History 一起过期，调用记录还得
    靠产出目录里的文件反推，所以永远做不到"实时"。

现在的分工：
    SQLite 库（web-ai.db）= 唯一事实来源，只增不改历史；
    collect.py  = 慢变信息（站点 / 登录态 / 历史对话）增量 upsert；
    askw.py     = 每次外包调用**当场**写一条流水（这一步才是"实时"）；
    render.py   = 只从库里读，纯渲染，不再自己扫描。

用法（作为库）：
    import store
    con = store.connect()
    store.upsert_conversations(con, convs)
    data = store.build_data(con)
"""

import csv
import datetime as dt
import glob
import json
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(HERE, "web-ai.db")
TZ = dt.timezone(dt.timedelta(hours=8))

SCHEMA = """
CREATE TABLE IF NOT EXISTS providers (
  id            TEXT PRIMARY KEY,
  name          TEXT,
  url           TEXT,
  requires_login INTEGER DEFAULT 0,
  enabled       INTEGER DEFAULT 0,
  note          TEXT,
  login_state   TEXT,
  visits        INTEGER DEFAULT 0,
  first_visit   TEXT,
  last_visit    TEXT,
  cookies_json  TEXT,
  tokens_json   TEXT,
  evidence_json TEXT,
  ls_present    INTEGER DEFAULT 0,
  updated_at    TEXT
);

CREATE TABLE IF NOT EXISTS conversations (
  url          TEXT PRIMARY KEY,
  provider     TEXT,
  title        TEXT,
  session      TEXT,
  kind         TEXT,
  visits       INTEGER DEFAULT 0,
  first_visit  TEXT,
  last_visit   TEXT,
  created_at   TEXT,
  updated_at   TEXT
);

CREATE TABLE IF NOT EXISTS calls (
  id          TEXT NOT NULL,
  started_at  TEXT NOT NULL DEFAULT '',
  provider    TEXT,
  model       TEXT,
  status      TEXT,
  error       TEXT,
  chars       INTEGER,
  elapsed_ms  INTEGER,
  cached      INTEGER DEFAULT 0,
  chat_url    TEXT,
  session     TEXT,
  prompt_file TEXT,
  prompt      TEXT,
  answer_head TEXT,
  artifact    TEXT,
  shot        TEXT,
  source      TEXT,
  created_at  TEXT,
  PRIMARY KEY (id, started_at)
);
CREATE INDEX IF NOT EXISTS idx_calls_started ON calls(started_at);
CREATE INDEX IF NOT EXISTS idx_calls_session ON calls(session);

CREATE TABLE IF NOT EXISTS sessions (
  name       TEXT PRIMARY KEY,
  url        TEXT,
  provider   TEXT,
  updated_at TEXT,
  summary    TEXT
);

CREATE TABLE IF NOT EXISTS artifacts (
  dir    TEXT NOT NULL,
  file   TEXT NOT NULL,
  size   INTEGER,
  mtime  TEXT,
  kind   TEXT,
  note   TEXT,
  chat_url TEXT,
  conversation TEXT,
  PRIMARY KEY (dir, file)
);

CREATE TABLE IF NOT EXISTS quota (
  provider    TEXT PRIMARY KEY,
  calls       INTEGER DEFAULT 0,
  daily_quota INTEGER DEFAULT 40,
  last_call_at TEXT,
  history_json TEXT
);

CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);
"""


# ---------- 基础 ----------
def now_iso():
    return dt.datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


def connect(db_path=None):
    con = sqlite3.connect(db_path or DEFAULT_DB, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    _migrate(con)
    return con


def _migrate(con):
    """轻量迁移：老库补新列（SQLite 的 ADD COLUMN 只加不删，安全）。"""
    cols = {r["name"] for r in con.execute("PRAGMA table_info(calls)")}
    for col, decl in (("shot", "TEXT"), ("page_text", "TEXT"), ("watchdog", "TEXT")):
        if col not in cols:
            con.execute("ALTER TABLE calls ADD COLUMN %s %s" % (col, decl))
    scols = {r["name"] for r in con.execute("PRAGMA table_info(sessions)")}
    if "summary" not in scols:
        con.execute("ALTER TABLE sessions ADD COLUMN summary TEXT")
    con.commit()


def session_usage(con, name):
    """某会话的用量：轮数、累计答案字数、最早/最近调用时间。"""
    row = con.execute(
        "SELECT count(*) n, COALESCE(sum(chars),0) ch, min(started_at) f, max(started_at) l "
        "FROM calls WHERE session=?", (name,)).fetchone()
    return {"turns": row["n"] or 0, "chars": row["ch"] or 0,
            "first": row["f"], "last": row["l"]}


def set_session_summary(con, name, summary):
    """存会话的「接手说明」（由在线 AI 自己生成，不是本地拼的）。"""
    con.execute("INSERT INTO sessions(name, summary) VALUES(?,?) "
                "ON CONFLICT(name) DO UPDATE SET summary=excluded.summary", (name, summary))
    con.commit()


def get_session_summary(con, name):
    row = con.execute("SELECT summary FROM sessions WHERE name=?", (name,)).fetchone()
    return row["summary"] if row else None


def set_meta(con, key, value):
    con.execute("INSERT INTO meta(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, "" if value is None else str(value)))


def get_meta(con, key, default=None):
    row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def _j(v):
    return json.dumps(v, ensure_ascii=False)


def _loads(s, default):
    try:
        return json.loads(s) if s else default
    except Exception:
        return default


# ---------- 写入：慢变信息（collect.py 调用） ----------
def upsert_providers(con, providers):
    """站点与登录态。providers 为空时直接跳过，避免一次失败扫描把库覆盖空。"""
    if not providers:
        return 0
    ts = now_iso()
    n = 0
    for p in providers:
        con.execute("""
        INSERT INTO providers (id,name,url,requires_login,enabled,note,login_state,
                               visits,first_visit,last_visit,cookies_json,tokens_json,
                               evidence_json,ls_present,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
          name=excluded.name,
          url=excluded.url,
          requires_login=excluded.requires_login,
          enabled=excluded.enabled,
          note=COALESCE(NULLIF(excluded.note,''), providers.note),
          login_state=excluded.login_state,
          visits=MAX(COALESCE(providers.visits,0), COALESCE(excluded.visits,0)),
          first_visit=COALESCE(providers.first_visit, excluded.first_visit),
          last_visit=COALESCE(excluded.last_visit, providers.last_visit),
          cookies_json=excluded.cookies_json,
          tokens_json=excluded.tokens_json,
          evidence_json=excluded.evidence_json,
          ls_present=excluded.ls_present,
          updated_at=excluded.updated_at
        """, (
            p.get("id"), p.get("name"), p.get("url"),
            1 if p.get("requiresLogin") else 0,
            1 if p.get("enabled") else 0,
            p.get("note"), p.get("loginState"),
            p.get("visits") or 0, p.get("firstVisit"), p.get("lastVisit"),
            _j(p.get("cookies") or []), _j(p.get("tokens") or {}),
            _j(p.get("evidence") or []), 1 if p.get("lsPresent") else 0, ts,
        ))
        n += 1
    return n


def upsert_conversations(con, convs):
    if not convs:
        return 0
    ts = now_iso()
    n = 0
    for c in convs:
        con.execute("""
        INSERT INTO conversations (url,provider,title,session,kind,visits,
                                   first_visit,last_visit,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(url) DO UPDATE SET
          provider=excluded.provider,
          title=COALESCE(NULLIF(excluded.title,''), conversations.title),
          session=COALESCE(excluded.session, conversations.session),
          kind=COALESCE(excluded.kind, conversations.kind),
          visits=MAX(COALESCE(conversations.visits,0), COALESCE(excluded.visits,0)),
          first_visit=COALESCE(conversations.first_visit, excluded.first_visit),
          last_visit=COALESCE(excluded.last_visit, conversations.last_visit),
          updated_at=excluded.updated_at
        """, (
            c.get("url"), c.get("provider"), c.get("title"), c.get("session"),
            c.get("kind"), c.get("visits") or 0, c.get("firstVisit"), c.get("lastVisit"),
            ts, ts,
        ))
        n += 1
    return n


def upsert_sessions(con, sessions):
    if not sessions:
        return 0
    ts = now_iso()
    for s in sessions:
        if not s.get("name"):
            continue
        con.execute("""
        INSERT INTO sessions (name,url,provider,updated_at) VALUES (?,?,?,?)
        ON CONFLICT(name) DO UPDATE SET
          url=excluded.url, provider=excluded.provider,
          updated_at=COALESCE(excluded.updated_at, sessions.updated_at)
        """, (s.get("name"), s.get("url"), s.get("provider"), s.get("updatedAt") or ts))
    return len(sessions)


def upsert_calls(con, calls):
    """调用流水。同一 (id, started_at) 只留一条，缺的字段后续可补齐。"""
    if not calls:
        return 0
    ts = now_iso()
    n = 0
    for c in calls:
        con.execute("""
        INSERT INTO calls (id,started_at,provider,model,status,error,chars,elapsed_ms,
                           cached,chat_url,session,prompt_file,prompt,answer_head,
                           artifact,source,created_at,shot,page_text,watchdog)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id,started_at) DO UPDATE SET
          provider=COALESCE(NULLIF(excluded.provider,''), calls.provider),
          model=COALESCE(excluded.model, calls.model),
          status=COALESCE(excluded.status, calls.status),
          error=COALESCE(excluded.error, calls.error),
          chars=COALESCE(excluded.chars, calls.chars),
          elapsed_ms=COALESCE(excluded.elapsed_ms, calls.elapsed_ms),
          cached=excluded.cached,
          chat_url=COALESCE(excluded.chat_url, calls.chat_url),
          session=COALESCE(excluded.session, calls.session),
          prompt_file=COALESCE(excluded.prompt_file, calls.prompt_file),
          prompt=COALESCE(excluded.prompt, calls.prompt),
          answer_head=COALESCE(NULLIF(excluded.answer_head,''), calls.answer_head),
          artifact=COALESCE(excluded.artifact, calls.artifact),
          shot=COALESCE(excluded.shot, calls.shot),
          page_text=COALESCE(excluded.page_text, calls.page_text),
          watchdog=COALESCE(excluded.watchdog, calls.watchdog),
          source=excluded.source
        """, (
            c.get("id") or "?", c.get("startedAt") or "", c.get("provider"), c.get("model"),
            c.get("status"), c.get("error"), c.get("chars"), c.get("elapsedMs"),
            1 if c.get("cached") else 0, c.get("chatUrl"), c.get("session"),
            c.get("promptFile"), c.get("prompt"), c.get("answerHead"),
            c.get("artifacts"), c.get("source") or "scan", ts, c.get("shot"),
            c.get("pageText"), c.get("watchdog"),
        ))
        n += 1
    return n


def upsert_artifacts(con, outputs, notes):
    ts = now_iso()
    for o in (outputs or []):
        con.execute("""
        INSERT INTO artifacts (dir,file,size,mtime,kind,note,chat_url,conversation)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(dir,file) DO UPDATE SET
          size=excluded.size, mtime=excluded.mtime
        """, (o.get("dir") or "", o["file"], o.get("size"), o.get("mtime"),
              "output", None, None, None))
    for x in (notes or []):
        con.execute("""
        INSERT INTO artifacts (dir,file,size,mtime,kind,note,chat_url,conversation)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(dir,file) DO UPDATE SET
          size=excluded.size, mtime=excluded.mtime, note=excluded.note,
          chat_url=excluded.chat_url, conversation=excluded.conversation
        """, (x.get("dir") or "", x["file"], x.get("size"), x.get("mtime"),
              "note", x.get("note"), x.get("chatUrl"), x.get("conversation")))
    return len(outputs or []) + len(notes or [])


def upsert_quota(con, quota):
    if not quota:
        return 0
    for q in quota:
        con.execute("""
        INSERT INTO quota (provider,calls,daily_quota,last_call_at,history_json)
        VALUES (?,?,?,?,?)
        ON CONFLICT(provider) DO UPDATE SET
          calls=excluded.calls,
          daily_quota=COALESCE(quota.daily_quota, excluded.daily_quota),
          last_call_at=excluded.last_call_at, history_json=excluded.history_json
        """, (q.get("provider"), q.get("calls") or 0, q.get("dailyQuota") or 40,
              q.get("lastCallAt"), _j(q.get("history") or [])))
    return len(quota)


def set_quota(con, provider, daily_quota):
    """手动调整某站点的每日配额上限（看板页面上改的就是它）。"""
    if not provider:
        raise ValueError("provider 不能为空")
    v = max(1, int(daily_quota))
    con.execute("INSERT INTO quota(provider,daily_quota) VALUES(?,?) "
                "ON CONFLICT(provider) DO UPDATE SET daily_quota=excluded.daily_quota",
                (provider, v))
    con.commit()
    return v


# ---------- 写入：实时（askw.py 每次外包后调用） ----------
def record_call(con, *, provider=None, model=None, status=None, error=None,
                chars=None, elapsed_ms=None, chat_url=None, session=None,
                prompt_file=None, prompt=None, answer_head=None, call_id=None,
                started_at=None, cached=False, source="askw", artifact=None,
                shot=None, page_text=None, watchdog=None):
    """一次外包调用的即时落库。返回 (call_id, started_at)。"""
    started_at = started_at or now_iso()
    call_id = call_id or ("c" + dt.datetime.now(TZ).strftime("%Y%m%d%H%M%S"))
    upsert_calls(con, [{
        "id": call_id, "startedAt": started_at, "provider": provider, "model": model,
        "status": status, "error": error, "chars": chars, "elapsedMs": elapsed_ms,
        "cached": cached, "chatUrl": chat_url, "session": session,
        "promptFile": prompt_file, "prompt": prompt, "answerHead": answer_head,
        "artifacts": artifact, "shot": shot, "pageText": page_text,
        "watchdog": watchdog, "source": source,
    }])
    set_meta(con, "last_call_at", started_at)
    if session:
        con.execute("INSERT INTO sessions(name,url,provider,updated_at) VALUES(?,?,?,?) "
                    "ON CONFLICT(name) DO UPDATE SET url=COALESCE(excluded.url,sessions.url), "
                    "updated_at=excluded.updated_at",
                    (session, chat_url, provider, started_at))
    if chat_url:
        # 新对话首次出现时先把壳存下来，collect 之后补标题
        con.execute("INSERT INTO conversations(url,provider,title,kind,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET "
                    "session=COALESCE(excluded.session,conversations.session), updated_at=excluded.updated_at",
                    (chat_url, provider, "", "chat", started_at, started_at))
        con.execute("UPDATE conversations SET session=COALESCE(?,session) WHERE url=?",
                    (session, chat_url))
    con.commit()
    return call_id, started_at


# ---------- 读取：组装看板数据 ----------
def build_data(con, sources=None):
    """从库组装出与原 data.json 完全同构的结构，render.py 直接用。"""
    providers, conversations, calls, sessions = [], [], [], []

    conv_rows = con.execute("SELECT * FROM conversations").fetchall()
    conv_index = {r["url"]: dict(r) for r in conv_rows}

    call_rows = con.execute(
        "SELECT * FROM calls ORDER BY started_at DESC, id DESC").fetchall()

    # 按对话 / 站点聚合调用（流水倒序：最新的在最前）
    today = dt.datetime.now(TZ).strftime("%Y-%m-%d")
    by_url, by_provider = {}, {}
    today_by_prov, last_call_by_prov = {}, {}
    ans_head_by_url, ans_head_by_prov = {}, {}
    for r in call_rows:
        d = dict(r)
        u = d.get("chat_url") or ""
        p = d.get("provider") or ""
        if p:
            if (d.get("started_at") or "").startswith(today):
                today_by_prov[p] = today_by_prov.get(p, 0) + 1
            if (d.get("started_at") or "") > (last_call_by_prov.get(p) or ""):
                last_call_by_prov[p] = d["started_at"]
        st = by_url.setdefault(u, {"n": 0, "ok": 0, "chars": 0, "ms": 0})
        for k, v in (("n", 1), ("ok", 1 if d["status"] == "success" else 0),
                     ("chars", d.get("chars") or 0), ("ms", d.get("elapsed_ms") or 0)):
            st[k] += v
        if p:
            sp = by_provider.setdefault(p, {"n": 0, "ok": 0})
            sp["n"] += 1
            sp["ok"] += 1 if d["status"] == "success" else 0
        ans_head_by_url[u] = ans_head_by_url.get(u, 0) + (d.get("chars") or 0)
        ans_head_by_prov[p] = ans_head_by_prov.get(p, 0) + (d.get("chars") or 0)
        calls.append({
            "id": d["id"], "file": None, "provider": d.get("provider"),
            "model": d.get("model"), "status": d.get("status"), "error": d.get("error"),
            "chars": d.get("chars"), "elapsedMs": d.get("elapsed_ms"),
            "cached": bool(d.get("cached")), "chatUrl": d.get("chat_url"),
            "session": d.get("session"),
            "startedAt": d.get("started_at"),
            "artifacts": d.get("artifact"), "promptFile": d.get("prompt_file"),
            "prompt": d.get("prompt"), "answerHead": d.get("answer_head"),
            "shot": d.get("shot"), "pageText": d.get("page_text"),
            "watchdog": d.get("watchdog"), "source": d.get("source"),
        })

    for u, c in conv_index.items():
        st = by_url.get(u, {"n": 0, "ok": 0, "chars": 0, "ms": 0})
        conversations.append({
            "provider": c.get("provider"), "url": u, "title": c.get("title") or "(无标题)",
            "visits": c.get("visits") or 0,
            "firstVisit": c.get("first_visit"), "lastVisit": c.get("last_visit"),
            "kind": c.get("kind") or "chat", "session": c.get("session"),
            "calls": st["n"], "okCalls": st["ok"], "answerChars": st["chars"],
            "avgSec": round(st["ms"] / 1000 / st["n"], 1) if st["n"] else None,
        })
    conversations.sort(key=lambda x: x["lastVisit"] or "", reverse=True)

    for r in con.execute("SELECT * FROM providers").fetchall():
        p = dict(r)
        p["requiresLogin"] = bool(p.pop("requires_login"))
        p["enabled"] = bool(p.pop("enabled"))
        p["lsPresent"] = bool(p.pop("ls_present"))
        pid = p["id"]
        p["conversations"] = len([c for c in conversations if c["provider"] == pid])
        p["calls"] = (by_provider.get(pid) or {}).get("n", 0)
        p["todayCalls"] = today_by_prov.get(pid, 0)
        p["lastCallAt"] = last_call_by_prov.get(pid)
        p["cookies"] = _loads(p.pop("cookies_json"), [])
        p["tokens"] = _loads(p.pop("tokens_json"), {})
        p["evidence"] = _loads(p.pop("evidence_json"), [])
        p["loginState"] = p.pop("login_state")
        p["visits"] = p.get("visits") or 0
        lv = p.pop("last_visit")
        # 「最近活动」= 浏览器最近访问 与 最近一次外包调用，取更晚的那个
        last_call = p["lastCallAt"]
        if last_call and (not lv or last_call > lv):
            p["lastVisit"], p["lastVisitSource"] = last_call, "外包调用"
        else:
            p["lastVisit"], p["lastVisitSource"] = lv, ("浏览器访问" if lv else None)
        p["browserLastVisit"] = lv
        p["firstVisit"] = p.pop("first_visit")
        p["updatedAt"] = p.pop("updated_at")
        providers.append(p)

    for r in con.execute("SELECT * FROM sessions ORDER BY updated_at DESC").fetchall():
        s = dict(r)
        c = conv_index.get(s.get("url"))
        sessions.append({
            "name": s["name"], "url": s.get("url"), "provider": s.get("provider"),
            "updatedAt": s.get("updated_at"),
            "title": (c or {}).get("title"), "calls": 0,
            "summary": s.get("summary"),
        })
    for s in sessions:
        s["calls"] = len([c for c in calls if c.get("session") == s["name"]])

    outputs, notes = [], []
    for r in con.execute("SELECT * FROM artifacts ORDER BY kind, mtime").fetchall():
        a = dict(r)
        if a["kind"] == "note":
            notes.append({"file": a["file"], "note": a.get("note") or "文本型产出",
                          "size": a.get("size"), "mtime": a.get("mtime"),
                          "chatUrl": a.get("chat_url"), "conversation": a.get("conversation")})
        else:
            outputs.append({"file": a["file"], "size": a.get("size"), "mtime": a.get("mtime")})

    # 配额：**今日调用数**从 calls 表按当天实时统计（历史调用不再计入"今日"）
    quota = []
    q_rows = {r["provider"]: dict(r) for r in con.execute("SELECT * FROM quota").fetchall()}
    for p in providers:
        pid = p["id"]
        q = q_rows.get(pid) or {}
        quota.append({
            "provider": pid,
            "calls": today_by_prov.get(pid, 0),
            "totalCalls": (by_provider.get(pid) or {}).get("n", 0),
            "dailyQuota": q.get("daily_quota") or 40,
            "lastCallAt": last_call_by_prov.get(pid) or q.get("last_call_at"),
            "toolHistory": _loads(q.get("history_json"), []),
            "date": today,
        })

    T = {
        "sites": len(providers),
        "sitesUsed": len([p for p in providers if (p.get("visits") or 0) > 0]),
        "signedIn": len([p for p in providers if p.get("loginState") == "signed-in"]),
        "conversations": len(conversations),
        "sessions": len(sessions),
        "calls": len(calls),
        "okCalls": len([c for c in calls if c["status"] == "success"]),
        "answerChars": sum(c.get("chars") or 0 for c in calls),
        "avgSec": round(sum(c.get("elapsedMs") or 0 for c in calls) / 1000 / max(1, len(calls)), 1),
        "todayCalls": sum(today_by_prov.values()),
        "today": today,
    }
    src = {"profile": get_meta(con, "profile", ""), "tool": get_meta(con, "tool", ""),
           "tasks": get_meta(con, "tasks", "")}
    src.update(sources or {})
    return {
        "generatedAt": now_iso(),
        "db": {"path": os.path.basename(DEFAULT_DB),
               "lastScanAt": get_meta(con, "last_scan_at"),
               "lastCallAt": get_meta(con, "last_call_at"),
               "callCount": len(calls)},
        "sources": src,
        "providers": providers,
        "conversations": conversations,
        "sessions": sessions,
        "calls": calls,
        "quota": quota,
        "outputs": outputs,
        "notes": notes,
        "totals": T,
    }


# ---------- 导出：人读表格 ----------
def export_csv(con, out_dir, prefix="web-ai"):
    """导出 CSV 快照，Excel / WPS 双击可开（utf-8-sig 防中文乱码）。"""
    os.makedirs(out_dir, exist_ok=True)
    written = []

    def dump(name, header, rows):
        path = os.path.join(out_dir, "%s-%s.csv" % (prefix, name))
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(rows)
        written.append(path)
        return path

    dump("calls",
         ["时间", "编号", "站点", "会话名", "结果", "耗时(秒)", "字数", "所属对话", "提示词摘要", "来源"],
         [[c["started_at"], c["id"], c["provider"] or "", c["session"] or "",
           "成功" if c["status"] == "success" else (c["status"] or ""),
           round((c["elapsed_ms"] or 0) / 1000), c["chars"] or "",
           c["chat_url"] or "", (c["prompt"] or "").replace("\n", " ")[:60], c["source"] or ""]
          for c in con.execute("SELECT * FROM calls ORDER BY started_at DESC").fetchall()])

    dump("conversations",
         ["站点", "对话标题", "会话名", "首次访问", "最近访问", "访问次数", "类型", "链接"],
         [[c["provider"] or "", c["title"] or "", c["session"] or "",
           c["first_visit"] or "", c["last_visit"] or "", c["visits"] or "",
           c["kind"] or "", c["url"]]
          for c in con.execute("SELECT * FROM conversations ORDER BY last_visit DESC").fetchall()])

    dump("providers",
         ["站点", "地址", "登录状态", "启用", "访问次数", "最近活动", "Cookies", "更新时间"],
         [[p["name"] or p["id"], p["url"] or "", p["login_state"] or "",
           "是" if p["enabled"] else "否", p["visits"] or "", p["last_visit"] or "",
           len(_loads(p["cookies_json"], [])), p["updated_at"] or ""]
          for p in con.execute("SELECT * FROM providers ORDER BY id").fetchall()])

    dump("sessions",
         ["会话名", "站点", "对话标题", "更新时间", "链接"],
         [[s["name"], s["provider"] or "", (conv_index_title(con, s["url"]) or ""),
           s["updated_at"] or "", s["url"] or ""]
          for s in con.execute("SELECT * FROM sessions ORDER BY updated_at DESC").fetchall()])

    return written


def conv_index_title(con, url):
    if not url:
        return None
    row = con.execute("SELECT title FROM conversations WHERE url=?", (url,)).fetchone()
    return row["title"] if row else None


def summary(con):
    def one(sql, *a):
        r = con.execute(sql, a).fetchone()
        return (r[0] if r else 0) or 0
    return {
        "providers": one("SELECT count(*) FROM providers"),
        "conversations": one("SELECT count(*) FROM conversations"),
        "calls": one("SELECT count(*) FROM calls"),
        "ok_calls": one("SELECT count(*) FROM calls WHERE status='success'"),
        "sessions": one("SELECT count(*) FROM sessions"),
        "artifacts": one("SELECT count(*) FROM artifacts"),
        "chars": one("SELECT sum(chars) FROM calls"),
        "today_calls": one("SELECT count(*) FROM calls WHERE substr(started_at,1,10)=date('now','localtime')"),
        "last_call_at": get_meta(con, "last_call_at", "—"),
        "last_scan_at": get_meta(con, "last_scan_at", "—"),
    }


# ---------- 工具目录解析（与 collect.py 同源，修掉 .tools 漏检） ----------
def resolve_tool(cli=None):
    if cli:
        return cli
    if os.environ.get("AWA_TOOL"):
        return os.environ["AWA_TOOL"]
    home = os.path.expanduser("~")
    roots, seen = [], set()

    def add(p):
        if p and p not in seen:
            seen.add(p)
            roots.append(p)

    add(os.path.join(home, ".tools"))
    add(os.path.join(home, "tools"))
    d = os.getcwd()
    for _ in range(5):
        add(os.path.join(d, ".tools"))
        add(d)
        up = os.path.dirname(d)
        if up == d:
            break
        d = up
    for r in roots:
        if not os.path.isdir(r):
            continue
        for cand in sorted(glob.glob(os.path.join(r, "free-web-ai-worker*")), reverse=True):
            if os.path.exists(os.path.join(cand, "config", "default.json")):
                return cand
    return None
