# -*- coding: utf-8 -*-
"""
站点 / 对话看板的数据采集脚本（外包 skill 配套工具）。

扫描本机 web-AI 工具的站点登录态、历史对话与调用记录，输出一份 data.json。

数据源（全部本机，只读）：
  1. <profile>/Network/Cookies              -> 站点 cookie / 登录线索
  2. <profile>/Local Storage/leveldb        -> 站点 localStorage 凭据
  3. <profile>/History                      -> 访问过的对话 URL / 标题 / 次数
  4. ~/.agent-web-ai/chats.json             -> --session 会话登记簿
  5. <profile-parent>/throttle.json         -> 配额与调用节流
  6. <tool>/config/default.json             -> 站点清单(provider)
  7. <tasks>/*.json|*.txt|*.html            -> 每次外包调用的产出

安全：localStorage 里的登录凭据**只记录长度与指纹，不落原文**，
      因此生成的 data.json / dashboard.html 可以放心传阅。

用法：
  python collect.py [--out data.json] [--tool <工具目录>] [--tasks <产出目录>] [--awa ~/.agent-web-ai]
环境变量同样生效：AWA_HOME / AWA_TOOL / AWA_TASKS
"""

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import sqlite3
import sys

AI_HOSTS = [
    "chat.deepseek.com", "chat.qwen.ai", "duck.ai",
    "chatgpt.com", "grok.com", "gemini.google.com",
    "claude.ai", "www.doubao.com", "yuanbao.tencent.com",
]

# ---------- 时间工具 ----------
def filetime_to_dt(us):
    """Edge/Chrome History 的 last_visit_time -> datetime(UTC+8)"""
    if not us:
        return None
    try:
        sec = (int(us) - 11644473600000000) / 1e6
        return dt.datetime.fromtimestamp(sec, dt.timezone(dt.timedelta(hours=8)))
    except Exception:
        return None


def ms_to_dt(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone(dt.timedelta(hours=8))) if ms else None


def iso(x):
    return x.strftime("%Y-%m-%d %H:%M:%S") if x else None


def mtime(p):
    return dt.datetime.fromtimestamp(os.path.getmtime(p), dt.timezone(dt.timedelta(hours=8)))


# ---------- 路径解析 ----------
def resolve_awa(cli):
    return cli or os.environ.get("AWA_HOME") or os.path.join(os.path.expanduser("~"), ".agent-web-ai")


def resolve_profile(awa):
    """优先 edge，其次 chrome / chromium / brave，取第一个存在的 profile。"""
    root = os.path.join(awa, "profiles")
    if not os.path.isdir(root):
        return None, None
    for b in sorted(os.listdir(root)):
        d = os.path.join(root, b, "Default")
        if os.path.isdir(d):
            return b, d
    return None, None


def resolve_tool(cli):
    """工具目录。修复：原来只看 cwd/.tools 与 dirname(cwd)，漏了祖先目录下的
    .tools/，在产出目录里直接跑会找不到工具、静默降级成 sites=0。"""
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


def resolve_tasks(cli):
    """外包产出目录，支持逗号分隔多个目录（历史任务散在多个目录里）。"""
    return cli or os.environ.get("AWA_TASKS") or os.getcwd()


def split_dirs(value):
    return [t.strip() for t in str(value or "").split(",") if t.strip()]


def load_json(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


# ---------- 1. 站点清单 ----------
def load_providers(tool):
    cfg = load_json(os.path.join(tool, "config", "default.json")) if tool else {}
    out = []
    for pid, p in (cfg.get("providers") or {}).items():
        out.append({
            "id": pid,
            "name": p.get("displayName", pid),
            "url": p.get("url", ""),
            "requiresLogin": bool(p.get("requiresLogin")),
            "enabled": bool(p.get("enabled")),
            "note": p.get("note", ""),
        })
    return out


def host_of(url):
    m = re.match(r"https?://([^/]+)", url or "")
    return m.group(1) if m else ""


# ---------- 2. Cookies ----------
def load_cookies(profile):
    res = {}
    path = os.path.join(profile, "Network", "Cookies")
    if not os.path.exists(path):
        return res
    try:
        con = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"), uri=True)
        for hk, name in con.execute("select host_key, name from cookies"):
            res.setdefault(hk.lstrip("."), []).append(name)
        con.close()
    except sqlite3.Error:
        pass
    return res


# ---------- 3. localStorage 证据 ----------
TOKEN_KEYS = ("usertoken", "accesstoken", "id_token", "token", "sessionid", "auth")


def mask(value):
    """凭据只留长度 + 指纹，绝不落原文。"""
    return {
        "len": len(value),
        "sha256": hashlib.sha256(value.encode("latin-1")).hexdigest()[:12],
    }


def load_localstorage(profile):
    """
    返回 {host: {"present": bool, "tokens": {key: {"len":n,"sha256":...}}}}。

    浏览器的 localStorage 用前缀压缩的 leveldb 记录，key/value 边界不可靠，
    因此只做「证据级」粗解析：host 是否出现过 + 附近是否有高熵 token 串。
    """
    base = os.path.join(profile, "Local Storage", "leveldb")
    blob = b""
    if os.path.isdir(base):
        for f in sorted(os.listdir(base)):
            if f.endswith(".ldb") or f.endswith(".log"):
                try:
                    blob += open(os.path.join(base, f), "rb").read()
                except Exception:
                    pass
    out = {}
    for host in AI_HOSTS:
        host_b = host.encode()
        present = (b"_" + host_b) in blob or (b"://" + host_b) in blob or (b"." + host_b) in blob
        tokens = {}
        window = 6000
        positions = [m.start() for m in re.finditer(re.escape(host_b), blob)]
        for pos in positions[:6]:
            chunk = blob[max(0, pos - window): pos + window]
            for tk in TOKEN_KEYS:
                for tm in re.finditer(re.escape(tk.encode()), chunk, re.I):
                    tail = chunk[tm.start(): tm.start() + 200]
                    v = re.search(rb"[A-Za-z0-9+/=_\-]{32,}", tail)
                    if v:
                        s = v.group(0).decode("latin-1")
                        if tokens.get(tk, {}).get("len", 0) < len(s):
                            tokens[tk] = mask(s)
        out[host] = {"present": present, "tokens": tokens}
    return out


# ---------- 4. 浏览历史 -> 对话 ----------
CONV_PATTERNS = {
    "deepseek": re.compile(r"^https://chat\.deepseek\.com/a/chat/s/([0-9a-f\-]{8,})"),
    "qwen": re.compile(r"^https://chat\.qwen\.ai/c/([0-9a-zA-Z\-_]{6,})"),
    "chatgpt": re.compile(r"^https://chatgpt\.com/c/([0-9a-zA-Z\-_]{6,})"),
    "grok": re.compile(r"^https://grok\.com/c/([0-9a-zA-Z\-_]{6,})"),
    "gemini": re.compile(r"^https://gemini\.google\.com/app/([0-9a-zA-Z\-_]{6,})"),
    "duckai": re.compile(r"^https://duck\.ai/\?.*(?:q=|chat)"),
}


def load_history(profile):
    path = os.path.join(profile, "History")
    convs, visits = {}, {}
    if not os.path.exists(path):
        return convs, visits
    try:
        con = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"), uri=True)
    except sqlite3.Error:
        return convs, visits
    first = {}
    try:
        for uid, t in con.execute("select url, min(visit_time) from visits where visit_time > 0 group by url"):
            first[uid] = filetime_to_dt(t)
    except sqlite3.Error:
        pass
    try:
        rows = list(con.execute("select id, url, title, visit_count, last_visit_time from urls"))
    except sqlite3.Error:
        rows = []
    con.close()

    for uid, url, title, cnt, lvt in rows:
        if not url or not url.startswith("http"):
            continue
        host = host_of(url)
        for h in AI_HOSTS:
            if host == h or host.endswith("." + h) or (h.endswith(".com") and host.startswith(h)):
                v = visits.setdefault(h, {"count": 0, "first": None, "last": None})
                v["count"] += int(cnt or 1)
                t = filetime_to_dt(lvt)
                if t:
                    v["first"] = min(v["first"], t) if v["first"] else t
                    v["last"] = max(v["last"], t) if v["last"] else t
        for pid, pat in CONV_PATTERNS.items():
            m = pat.match(url)
            if not m:
                continue
            c = convs.setdefault(url, {
                "provider": pid, "url": url, "title": (title or "").strip(),
                "visits": 0, "firstVisit": None, "lastVisit": None,
            })
            c["visits"] += int(cnt or 1)
            c["firstVisit"] = first.get(uid) or c["firstVisit"]
            # 站点的「新建对话 / 游客」入口页不是真实会话
            c["kind"] = "entry" if re.search(r"/(c/)?(new|new-chat|guest|new_chat)$", url) else "chat"
            t = filetime_to_dt(lvt)
            if t:
                c["lastVisit"] = max(c["lastVisit"], t) if c["lastVisit"] else t
            if not c["title"] and title:
                c["title"] = title.strip()
    for c in convs.values():
        c["title"] = re.sub(r"\s*-\s*(DeepSeek|Qwen|Qwen Studio|ChatGPT|Grok|Gemini|Duck\.ai.*)$",
                            "", c["title"]).strip() or "(无标题)"
        c["firstVisit"] = iso(c["firstVisit"])
        c["lastVisit"] = iso(c["lastVisit"])
    for v in visits.values():
        v["first"] = iso(v["first"])
        v["last"] = iso(v["last"])
    return convs, visits


# ---------- 5. 会话登记簿 / 配额 ----------
def load_chats(awa):
    return load_json(os.path.join(awa, "chats.json"), {})


def load_throttle(awa, browser):
    p = os.path.join(awa, "profiles", browser or "edge", "throttle.json")
    return load_json(p).get("providers", {})


# ---------- 6. 调用记录 ----------
def read_text(p):
    try:
        return open(p, encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def load_calls(tasks):
    if not os.path.isdir(tasks):
        return []
    jsons, prompts = [], []
    for f in os.listdir(tasks):
        full = os.path.join(tasks, f)
        if f.endswith(".json"):
            jsons.append((f, full))
        elif f.endswith(".txt") and ("prompt" in f or f.startswith("req_")):
            prompts.append((f, full))

    calls = []
    for fname, full in jsons:
        d = load_json(full)
        if not isinstance(d, dict) or "meta" not in d:
            continue
        meta = d.get("meta", {}) or {}
        started = meta.get("startedAt")
        st = dt.datetime.fromisoformat(started.replace("Z", "+00:00")) if started else None
        if st:
            st = st.astimezone(dt.timezone(dt.timedelta(hours=8)))
        ans = d.get("answer") or ""
        det = d.get("details") if isinstance(d.get("details"), dict) else {}
        calls.append({
            "id": fname[:-5],
            "file": fname,
            "provider": d.get("provider") or (meta.get("model") or "").lower(),
            "model": meta.get("model"),
            "status": d.get("status"),
            "error": det.get("message") or d.get("error"),
            "chars": meta.get("chars", len(ans)),
            "elapsedMs": meta.get("elapsedMs"),
            "cached": meta.get("cached", False),
            "chatUrl": meta.get("url"),
            "startedAt": iso(st),
            "artifacts": os.path.basename(meta.get("artifacts") or "") or None,
            "promptFile": None,
            "prompt": None,
            "answerHead": re.sub(r"\s+", " ", ans[:160]),
            "source": "cli-json",
        })

    pm = [(f, mtime(full)) for f, full in prompts]
    for c in calls:
        hit = match_prompt(c["id"], c["startedAt"], pm)
        if hit:
            for f, full in prompts:
                if f == hit:
                    c["promptFile"] = f
                    c["prompt"] = read_text(full).strip()
                    break

    calls.sort(key=lambda x: x["startedAt"] or "")
    return calls


def match_prompt(call_id, started_at_txt, pm):
    """优先级：精确同名 > 变体(ReqId/patchN) > 前缀包含 > 时间就近。"""
    names = [f for f, _ in pm]
    cands = ["%s_prompt.txt" % call_id, "%s.txt" % call_id, "req_%s.txt" % call_id]
    m = re.match(r"^([a-zA-Z]+?)(\d+)$", call_id)
    if m:
        stem, num = m.group(1), m.group(2)
        cands += ["%s_prompt%s.txt" % (stem, num), "%s_prompt_%s.txt" % (stem, num)]
    for c in cands:
        if c in names:
            return c
    for f in names:
        base = f[:-4]
        if call_id in base or base.rstrip("_prompt").replace("req_", "") == call_id:
            return f
    if started_at_txt:
        st = dt.datetime.strptime(started_at_txt, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=dt.timezone(dt.timedelta(hours=8)))
        best, gap = None, None
        for f, mt in pm:
            d = abs((st - mt).total_seconds())
            if mt <= st and (gap is None or d < gap) and d < 1800:
                best, gap = f, d
        return best
    return None


# ---------- 7. 本地产出 ----------
def load_outputs(tasks):
    if not os.path.isdir(tasks):
        return []
    out = []
    for f in sorted(os.listdir(tasks)):
        if f.endswith(".html"):
            full = os.path.join(tasks, f)
            out.append({"dir": tasks, "file": f, "size": os.path.getsize(full),
                        "mtime": iso(mtime(full))})
    return out


def load_task_notes(tasks):
    """早期调用只留了文本型结果（CLI 还没加 --json），单独登记。"""
    items = []
    for f, label in [("gen_result.txt", "整文件生成 v1"), ("mod_result.txt", "整文件改版 v2")]:
        full = os.path.join(tasks, f)
        if os.path.exists(full):
            items.append({"dir": tasks, "file": f, "note": label,
                          "size": os.path.getsize(full), "mtime": iso(mtime(full))})
    return items


def guess_url(items, conv_list, pid="deepseek"):
    """文本型结果没有记录 URL，用『产出时间最接近的会话』推断归属。"""
    def parse(s):
        return dt.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=dt.timezone(dt.timedelta(hours=8))) if s else None

    for it in items:
        mt = parse(it["mtime"])
        best = None
        for c in conv_list:
            if c["provider"] != pid:
                continue
            t = parse(c["firstVisit"]) or parse(c["lastVisit"])
            if not t or not mt:
                continue
            d = abs((t - mt).total_seconds())
            if best is None or d < best[0]:
                best = (d, c)
        if best and best[0] <= 900:
            it["chatUrl"] = best[1]["url"]
            it["conversation"] = best[1]["title"]
        else:
            it["chatUrl"] = None
            it["conversation"] = None
    return items


# ---------- 组装 ----------
def build(args):
    awa = resolve_awa(args.awa)
    browser, profile = resolve_profile(awa)
    tool = resolve_tool(args.tool)
    task_dirs = split_dirs(resolve_tasks(args.tasks))
    tasks = ",".join(task_dirs)
    if not profile:
        sys.exit("未找到浏览器 profile：%s/profiles/<browser>/Default —— 用 --awa 指定数据目录" % awa)

    providers = load_providers(tool)
    cookies = load_cookies(profile)
    ls = load_localstorage(profile)
    convs, visits = load_history(profile)
    chats = load_chats(awa)
    throttle = load_throttle(awa, browser)
    calls, outputs, notes = [], [], []
    for td in task_dirs:
        calls += load_calls(td)
        outputs += load_outputs(td)
        notes += load_task_notes(td)
    seen_calls, uniq = set(), []
    for c in calls:
        k = (c["id"], c["startedAt"])
        if k not in seen_calls:
            seen_calls.add(k)
            uniq.append(c)
    calls = uniq

    url2session = {}
    for name, info in chats.items():
        if isinstance(info, dict) and info.get("url"):
            url2session[info["url"]] = {"name": name, "updatedAt": info.get("updatedAt"),
                                        "provider": info.get("provider")}

    call_stat = {}
    for c in calls:
        c["session"] = (url2session.get(c.get("chatUrl") or "") or {}).get("name")
        s = call_stat.setdefault(c.get("chatUrl") or "", {"n": 0, "ok": 0, "chars": 0, "ms": 0})
        s["n"] += 1
        if c["status"] == "success":
            s["ok"] += 1
        s["chars"] += c.get("chars") or 0
        s["ms"] += c.get("elapsedMs") or 0

    conv_list = sorted(convs.values(), key=lambda x: x["lastVisit"] or "", reverse=True)
    notes = guess_url(notes, conv_list)
    for c in conv_list:
        sess = url2session.get(c["url"])
        c["session"] = sess["name"] if sess else None
        st = call_stat.get(c["url"], {"n": 0, "ok": 0, "chars": 0, "ms": 0})
        c["calls"] = st["n"]
        c["okCalls"] = st["ok"]
        c["answerChars"] = st["chars"]
        c["avgSec"] = round(st["ms"] / 1000 / st["n"], 1) if st["n"] else None

    for p in providers:
        h = host_of(p["url"])
        ck = []
        for dk, names in cookies.items():
            if dk == h or h.endswith(dk) or dk.endswith(h):
                ck.extend(names)
        lsinfo = ls.get(h, {"present": False, "tokens": {}})
        vis = visits.get(h, {})
        pv = {"cookies": sorted(set(ck)), "lsPresent": lsinfo.get("present", False),
              "tokens": lsinfo.get("tokens", {}), "visits": vis.get("count", 0),
              "lastVisit": vis.get("last"), "firstVisit": vis.get("first")}
        pv["conversations"] = len([c for c in conv_list if c["provider"] == p["id"]])
        pv["calls"] = len([c for c in calls if (c.get("chatUrl") or "").find(h) >= 0
                           or (c.get("provider") or "") == p["id"]])
        has_token = bool(pv["tokens"])
        if not pv["visits"] and not pv["cookies"]:
            pv["loginState"] = "unused"
        elif has_token:
            pv["loginState"] = "signed-in"
        elif not p["requiresLogin"]:
            pv["loginState"] = "anonymous"
        else:
            pv["loginState"] = "not-signed-in"
        pv["evidence"] = []
        if pv["cookies"]:
            pv["evidence"].append("Cookie %d 项：%s" % (len(pv["cookies"]), ", ".join(pv["cookies"][:6])))
        if pv["lsPresent"]:
            pv["evidence"].append("localStorage 中有本站记录")
        for tk, tv in pv["tokens"].items():
            pv["evidence"].append("检测到登录凭据 %s（%d 字符，已脱敏）" % (tk, tv.get("len", 0)))
        if pv["visits"]:
            pv["evidence"].append("历史访问 %d 次，最近 %s" % (pv["visits"], pv["lastVisit"]))
        if not pv["evidence"]:
            pv["evidence"].append("本 profile 无任何访问痕迹")
        p.update(pv)

    sessions = []
    for name, info in chats.items():
        if not isinstance(info, dict):
            continue
        c = next((x for x in conv_list if x["url"] == info.get("url")), None)
        sessions.append({
            "name": name, "url": info.get("url"), "provider": info.get("provider"),
            "updatedAt": info.get("updatedAt"),
            "title": c["title"] if c else None,
            "calls": c["calls"] if c else 0,
        })

    quota = []
    for pid, t in (throttle or {}).items():
        hist = (t or {}).get("history", [])
        quota.append({
            "provider": pid, "calls": len(hist),
            "dailyQuota": 40,
            "lastCallAt": iso(ms_to_dt(t.get("lastCallAt"))),
            "history": [iso(ms_to_dt(x)) for x in hist],
        })

    return {
        "generatedAt": iso(dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))),
        "sources": {"profile": os.path.join(awa, "profiles", browser or "edge"),
                    "tool": tool or "", "tasks": tasks},
        "providers": providers,
        "conversations": conv_list,
        "sessions": sessions,
        "calls": calls,
        "quota": quota,
        "outputs": outputs,
        "notes": notes,
        "totals": {
            "sites": len(providers),
            "sitesUsed": len([p for p in providers if p["visits"] > 0]),
            "signedIn": len([p for p in providers if p["loginState"] == "signed-in"]),
            "conversations": len(conv_list),
            "sessions": len(sessions),
            "calls": len(calls),
            "okCalls": len([c for c in calls if c["status"] == "success"]),
            "answerChars": sum(c.get("chars") or 0 for c in calls),
            "avgSec": round(sum(c.get("elapsedMs") or 0 for c in calls) / 1000 / max(1, len(calls)), 1),
        },
    }


def write_db(data, db_path=None):
    """把本次扫描结果**增量**写进 SQLite 库（不覆盖历史，只补全 / 更新）。"""
    import store
    con = store.connect(db_path)
    n = {
        "providers": store.upsert_providers(con, data["providers"]),
        "conversations": store.upsert_conversations(con, data["conversations"]),
        "sessions": store.upsert_sessions(con, data["sessions"]),
        "calls": store.upsert_calls(con, data["calls"]),
        "artifacts": store.upsert_artifacts(con, data["outputs"], data["notes"]),
        "quota": store.upsert_quota(con, data["quota"]),
    }
    store.set_meta(con, "last_scan_at", data["generatedAt"])
    stamps = [c["startedAt"] for c in data["calls"] if c.get("startedAt")]
    if stamps:
        cur = store.get_meta(con, "last_call_at") or ""
        store.set_meta(con, "last_call_at", max(max(stamps), cur))
    for k in ("profile", "tool", "tasks"):
        store.set_meta(con, k, (data.get("sources") or {}).get(k, ""))
    con.commit()
    con.close()
    return n


def main():
    ap = argparse.ArgumentParser(description="扫描本机 web-AI 站点登录态 / 历史对话 / 调用记录")
    ap.add_argument("--out", help="输出 data.json 路径（默认当前目录 data.json）")
    ap.add_argument("--awa", help="~/.agent-web-ai 等价的数据目录（环境变量 AWA_HOME）")
    ap.add_argument("--tool", help="ask-web-ai 工具目录（含 config/default.json，环境变量 AWA_TOOL）")
    ap.add_argument("--tasks", help="外包产出目录，可逗号分隔多个（环境变量 AWA_TASKS）")
    ap.add_argument("--to-db", action="store_true", help="把结果增量写入 SQLite 库（看板的持久数据层）")
    ap.add_argument("--db", help="SQLite 库路径（默认与本脚本同级 web-ai.db）")
    args = ap.parse_args()

    data = build(args)
    out = args.out or os.path.join(os.getcwd(), "data.json")
    json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    t = data["totals"]
    print("sites=%(sites)d used=%(sitesUsed)d signedIn=%(signedIn)d convs=%(conversations)d calls=%(calls)d" % t)
    print("written:", out)

    if args.to_db:
        n = write_db(data, args.db)
        print("db:", " ".join("%s=%d" % kv for kv in n.items()))


if __name__ == "__main__":
    main()
