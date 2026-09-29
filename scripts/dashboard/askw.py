# -*- coding: utf-8 -*-
"""
askw.py —— 外包调用的"带看护、带记账"入口（ask-web-ai 的包装器）

三件事：
  1. 转发：参数原样传给 free-web-ai-worker 的 bin/ask-web-ai.js，stdout 原样输出
     （所以 `... > 结果.json` 的老用法不受影响）。
  2. 实时看护：调用**进行中**周期性处置 + 取证 ——
       · 处置：发现拦路弹窗（年龄确认 / 欢迎层 / Cookie 同意）当场点掉；
       · 取证：截图留底，失败时归档。
     重点是"当场解决"，不是等它超时关闭、事后分析、再重跑一遍。
  3. 记账：把这次调用的元数据（站点 / 会话 / 状态 / 耗时 / 字数 / 对话 URL /
     现场截图 / 页面文字 / 看护动作）写进 SQLite 库 web-ai.db。

另外两个子命令：
  · shot     抓一张当前浏览器画面
  · compact  会话熔断：让**在线 AI 自己**把上下文整理成「接手说明」，存库 + 落盘

用法：
    python askw.py ask -p deepseek --session mytask --file 需求.txt --timeout 180 --no-cache > 结果.json
    python askw.py shot --out 现场.png
    python askw.py compact --session mytask

可选：
    --db <path>        指定库文件（默认同目录 web-ai.db）
    --no-record        只转发、不记账
    --no-capture       调用中不截图
    --no-care          调用中不自动处置弹窗
    --capture-sec <n>  看护间隔秒数（默认 4）
"""

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import store  # noqa: E402

DEFAULT_NODE = r"C:\Users\admin\.workbuddy\binaries\node\versions\22.22.2-3\node.exe"
SHOT_MJS = os.path.join(HERE, "shot.mjs")
CDP_EVAL_MJS = os.path.join(HERE, "cdp-eval.mjs")
DISMISS_JS = os.path.join(HERE, "dismiss-popup.js")
SHOTS_DIR = os.path.join(HERE, "shots")
SUMMARIES_DIR = os.path.join(HERE, "summaries")
LATEST_SHOT = os.path.join(SHOTS_DIR, ".latest.png")
AWA_HOME = os.environ.get("AWA_HOME") or os.path.join(os.path.expanduser("~"), ".agent-web-ai")
PROFILE_DIR = os.path.join(AWA_HOME, "profiles", "edge")

# 会话熔断阈值：超过就建议压缩后换新对话
TURN_LIMIT = 8
CHAR_LIMIT = 60000

WALL_RE = re.compile(r"验证码|人机验证|滑动验证|请稍后|稍后再试|too many requests|rate limit|安全验证|访问受限|操作频繁", re.I)


TAIL_NOISE = ("自动", "深度思考", "智能搜索", "联网搜索", "复制", "下载", "重新生成",
              "分享", "停止生成", "发送")


def _clean_tail(text):
    """剥掉页面页脚与按钮文字（兜底提取时必然带一点页面杂讯）。"""
    for marker in ("人工智能生成的内容可能不准确", "，即表示你同意", "内容由 AI 生成"):
        idx = text.find(marker)
        if idx > len(text) * 0.5:
            text = text[:idx]
    for _ in range(6):
        t = text.rstrip()
        hit = False
        for w in TAIL_NOISE:
            if t.endswith(w):
                t = t[:-len(w)].rstrip()
                hit = True
        text = t
        if not hit:
            break
    return text.strip()


def extract_answer_from_page(body, prompt_text=""):
    """
    从现场页面文字里抠出答案：定位需求结尾，取它之后的内容。
    实测场景：Qwen 把 8 条建议完整答在页面上，工具却判超时取不到——
    这种"取件失败"可以直接从现场把答案捞回来，不用白跑一轮。
    """
    if not body:
        return ""
    anchor = (prompt_text or "").strip()[-40:].strip()
    if anchor:
        idx = body.find(anchor)
        if idx >= 0:
            tail = body[idx + len(anchor):].strip()
            if len(tail) > 200:
                return _clean_tail(tail)
    return _clean_tail(body)


def find_node():
    for cand in (os.environ.get("AWA_NODE"), DEFAULT_NODE):
        if cand and os.path.exists(cand):
            return cand
    return shutil.which("node") or "node"


def take_opt(argv, names):
    out, val, i = [], None, 0
    while i < len(argv):
        a = argv[i]
        hit = None
        for n in names:
            if a == n and i + 1 < len(argv):
                hit = argv[i + 1]
                i += 2
                break
            if a.startswith(n + "="):
                hit = a.split("=", 1)[1]
                i += 1
                break
        if hit is not None:
            val = hit
            continue
        out.append(a)
        i += 1
    return val, out


def peek_opt(argv, names):
    for i, a in enumerate(argv):
        for n in names:
            if a == n and i + 1 < len(argv):
                return argv[i + 1]
            if a.startswith(n + "="):
                return a.split("=", 1)[1]
    return None


def absolutize(argv, names):
    """文件类参数里的相对路径转绝对（转发时 cwd 会切到工具目录）。"""
    out = list(argv)
    for i, a in enumerate(out):
        for n in names:
            if a == n and i + 1 < len(out):
                v = out[i + 1]
                if v and not os.path.isabs(v):
                    out[i + 1] = os.path.abspath(v)
                break
            if a.startswith(n + "="):
                v = a.split("=", 1)[1]
                if v and not os.path.isabs(v):
                    out[i] = n + "=" + os.path.abspath(v)
                break
    return out


def read_head(path, limit=3000):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()[:limit].strip()
    except Exception:
        return None


# ---------- 浏览器侧动作 ----------
def _node_run(args, timeout=20):
    try:
        r = subprocess.run([find_node()] + args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return json.loads(r.stdout or "{}")
    except Exception as e:
        return {"ok": False, "error": str(e)}


def grab(out_path, keyword=""):
    """抓一张当前浏览器画面。"""
    info = _node_run([SHOT_MJS, out_path, keyword])
    return bool(info.get("ok")), info


def eval_js(js_arg, keyword=""):
    """在页面里执行 JS（js_arg 可以是代码，或 @文件路径）。"""
    info = _node_run([CDP_EVAL_MJS, js_arg, keyword])
    return bool(info.get("ok")), info


class WatchdogLoop:
    """
    调用进行中的实时看护：先处置（点掉拦路弹窗），再取证（截图）。
    价值：Qwen 那次弹窗挡住了输入框，白等 150 秒超时才失败——
         看护循环在第 30 秒就能把它点掉，那一轮本来是可以跑通的。
    """

    def __init__(self, keyword="", interval=4.0, care=True, capture=True):
        self.keyword = keyword or ""
        self.interval = max(2.0, float(interval))
        self.care = care
        self.capture = capture
        self.actions = []
        self.got_any = False
        self.last_url = ""
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if not (self.care or self.capture):
            return
        if self.care and not os.path.exists(CDP_EVAL_MJS):
            self.care = False
        if self.capture and not os.path.exists(SHOT_MJS):
            self.capture = False
        if not (self.care or self.capture):
            return
        os.makedirs(SHOTS_DIR, exist_ok=True)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while not self._stop.is_set():
            try:
                if self.care:
                    ok, info = eval_js("@" + DISMISS_JS, self.keyword)
                    r = info.get("result") if ok else None
                    if r and r != "none":
                        self.actions.append((time.strftime("%H:%M:%S"), str(r)[:60]))
                if self.capture:
                    ok, info = grab(LATEST_SHOT, self.keyword)
                    if ok:
                        self.got_any = True
                        self.last_url = info.get("url") or ""
            except Exception:
                pass
            if self._stop.wait(self.interval):
                return

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def note(self):
        if not self.actions:
            return None
        counts = {}
        for _, a in self.actions:
            key = a.split(":", 1)[-1].strip()
            counts[key] = counts.get(key, 0) + 1
        return "；".join("%s×%d" % (k, v) for k, v in counts.items())

    def archive_last(self, session, tag="fail"):
        if not (self.got_any and os.path.exists(LATEST_SHOT)):
            return None
        os.makedirs(SHOTS_DIR, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        sid = re.sub(r"[^\w\-]+", "_", session or "call")
        dest = os.path.join(SHOTS_DIR, "%s-%s-%s.png" % (stamp, sid, tag))
        try:
            shutil.copy2(LATEST_SHOT, dest)
            return dest
        except Exception:
            return None

    def cleanup(self):
        try:
            os.remove(LATEST_SHOT)
        except Exception:
            pass


# ---------- 失败现场 ----------
def latest_tool_artifact(since_ts, profile_dir=None):
    """本次调用期间工具自己写的失败工件目录。"""
    root = os.path.join(profile_dir or PROFILE_DIR, "artifacts")
    if not os.path.isdir(root):
        return None
    best = None
    for name in os.listdir(root):
        p = os.path.join(root, name)
        try:
            mt = os.path.getmtime(p)
        except OSError:
            continue
        if mt >= since_ts - 5 and (best is None or mt > best[0]):
            best = (mt, p)
    return best[1] if best else None


def collect_failure_scene(session, since_ts, dog):
    """
    失败现场，按可靠性取：
      1) 工具自带 artifacts —— 失败瞬间的截图 + 完整 DOM + 页面文字（最准）
      2) 看护循环的最后一张抓拍（兜底）
    另外把页面文字**全文落盘**：很多"失败"其实是"取件失败"，
    答案完整躺在页面文字里（实测 Qwen 就是这样）。
    """
    os.makedirs(SHOTS_DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    sid = re.sub(r"[^\w\-]+", "_", session or "call")
    shot, art_dir, body = None, None, ""

    art_dir = latest_tool_artifact(since_ts)
    if art_dir:
        sp = os.path.join(art_dir, "summary.json")
        if os.path.exists(sp):
            try:
                with open(sp, encoding="utf-8") as fh:
                    body = (json.load(fh).get("bodyText") or "").strip()
            except Exception:
                pass
        png = os.path.join(art_dir, "screenshot.png")
        if os.path.exists(png):
            dest = os.path.join(SHOTS_DIR, "%s-%s-tool.png" % (stamp, sid))
            try:
                shutil.copy2(png, dest)
                shot = dest
            except Exception:
                shot = None

    if not shot:
        shot = dog.archive_last(session)

    page_file, suspect = None, False
    if body:
        page_file = os.path.join(SHOTS_DIR, "%s-%s-page.txt" % (stamp, sid))
        try:
            with open(page_file, "w", encoding="utf-8") as fh:
                fh.write(body)
        except Exception:
            page_file = None

    return {"shot": shot, "art_dir": art_dir, "body": body, "stamp": stamp, "sid": sid,
            "page_file": page_file, "suspect_answer": suspect}


# ---------- 执行 + 记账（main 与 compact 共用） ----------
def run_ask(argv, *, db_path=None, session=None, provider=None, prompt_file=None,
             care=True, capture=True, capture_sec=4.0, record=True, source="askw"):
    """转发一次调用，做实时看护，然后把结果记账。返回结果字典。"""
    tool = store.resolve_tool()
    if not tool:
        return {"rc": 3, "error": "找不到 free-web-ai-worker 工具目录（设置 AWA_TOOL）",
                "out": "", "err": ""}
    entry = os.path.join(tool, "bin", "ask-web-ai.js")
    if not os.path.exists(entry):
        return {"rc": 3, "error": "缺少入口 %s" % entry, "out": "", "err": ""}

    cmd = [find_node(), entry] + argv
    dog = WatchdogLoop(keyword=provider or "", interval=capture_sec,
                       care=care, capture=capture)
    dog.start()
    t0 = time.time()
    try:
        proc = subprocess.Popen(cmd, cwd=tool, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", errors="replace")
        out, err = proc.communicate()
        rc = proc.returncode
    finally:
        dog.stop()

    out, err = out or "", err or ""
    data = {}
    if out.strip().startswith("{"):
        try:
            data = json.loads(out)
        except Exception:
            data = {}
    meta = data.get("meta") or {}
    answer = data.get("answer") or ""
    det = data.get("details") if isinstance(data.get("details"), dict) else {}
    status = data.get("status") or ("success" if rc == 0 else "error")
    error_text = det.get("message") or data.get("error")
    wd_note = dog.note()
    scene = {}

    fallback_text, fallback_file = "", None
    if status != "success" or not answer:
        scene = collect_failure_scene(session, t0, dog)
        body = scene.get("body") or ""
        prompt_text = ""
        if prompt_file:
            try:
                with open(prompt_file, encoding="utf-8", errors="replace") as fh:
                    prompt_text = fh.read()
            except Exception:
                prompt_text = ""
        # B：答案很可能已经生成在页面上，只是工具没取到 → 直接捞回来，别白跑一轮
        if body and not WALL_RE.search(body[:600]) and len(body) > max(800, len(prompt_text) + 400):
            fallback_text = extract_answer_from_page(body, prompt_text)
        if fallback_text:
            scene["suspect_answer"] = True
            fallback_file = os.path.join(SHOTS_DIR, "%s-%s-answer.md" % (
                scene.get("stamp"), scene.get("sid")))
            try:
                with open(fallback_file, "w", encoding="utf-8") as fh:
                    fh.write(fallback_text)
            except Exception:
                fallback_file = None
        if body:
            error_text = "%s ｜ 现场页面文字：%s" % (error_text or "调用未成功",
                                                     re.sub(r"\s+", " ", body)[:160])
        if fallback_text:
            error_text = "%s ｜ 已从现场兜底提取答案（%d 字）" % (error_text or "", len(fallback_text))
        if wd_note:
            error_text = "%s ｜ 看护处置：%s" % (error_text or "", wd_note)

    if record:
        try:
            con = store.connect(db_path)
            store.record_call(
                con,
                provider=data.get("provider") or provider,
                model=meta.get("model"),
                status=status,
                error=error_text,
                chars=(meta.get("chars", len(answer)) if answer
                       else (len(fallback_text) or meta.get("chars"))),
                elapsed_ms=meta.get("elapsedMs"),
                chat_url=meta.get("url"),
                session=session,
                prompt_file=os.path.basename(prompt_file) if prompt_file else None,
                prompt=read_head(prompt_file) if prompt_file else None,
                answer_head=re.sub(r"\s+", " ", (answer or fallback_text)[:160]),
                cached=bool(meta.get("cached")),
                artifact=os.path.basename(meta.get("artifacts") or "") or None,
                shot=os.path.relpath(scene["shot"], HERE).replace("\\", "/") if scene.get("shot") else None,
                page_text=(scene.get("body") or None),
                watchdog=wd_note,
                source=source,
            )
            store.set_meta(con, "tool", tool)
            con.commit()
            con.close()
        except Exception as e:
            print("[askw] 记账失败（不影响本次调用）：%s" % e, file=sys.stderr)

    dog.cleanup()
    return {
        "rc": rc, "out": out, "err": err, "status": status, "answer": answer,
        "error": error_text, "session": session, "provider": data.get("provider") or provider,
        "chat_url": meta.get("url"), "watchdog": wd_note,
        "shot": scene.get("shot"), "page_file": scene.get("page_file"),
        "suspect_answer": scene.get("suspect_answer", False),
        "fallback_text": fallback_text, "fallback_file": fallback_file,
    }


# ---------- 子命令 ----------
def cmd_shot(argv):
    out, rest = take_opt(argv, ["--out", "-o"])
    keyword, rest = take_opt(rest, ["--match"])
    out = os.path.abspath(out or os.path.join(SHOTS_DIR, "manual-%s.png" % time.strftime("%Y%m%d-%H%M%S")))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    ok, info = grab(out, keyword or "")
    print(json.dumps(info, ensure_ascii=False))
    return 0 if ok else 1


COMPACT_PROMPT = """把这次会话的上下文整理成一份「接手说明」，只输出这份说明本身，不要客套、不要复述我的要求：
1) 任务目标
2) 已达成的结论 / 采用的方案要点
3) 遗留问题与下一步
4) 必须遵守的约束（技术栈、格式、不能碰的东西）
"""


def cmd_compact(argv):
    """会话熔断：让在线 AI 自己产出「接手说明」，供下一轮新对话续接。"""
    session, rest = take_opt(argv, ["--session", "-s"])
    db_path, rest = take_opt(rest, ["--db"])
    provider, rest = take_opt(rest, ["-p", "--provider"])
    next_name, rest = take_opt(rest, ["--next"])
    if not session:
        print("[askw] compact 需要 --session <会话名>", file=sys.stderr)
        return 2
    provider = provider or "deepseek"
    os.makedirs(SUMMARIES_DIR, exist_ok=True)
    req = os.path.join(SUMMARIES_DIR, "_compact_req.txt")
    with open(req, "w", encoding="utf-8") as fh:
        fh.write(COMPACT_PROMPT)

    print("[askw] 让 %s 在会话「%s」里生成接手说明（这一轮会回同一个对话）…" % (provider, session),
          file=sys.stderr)
    res = run_ask(["ask", "-p", provider, "--session", session, "--file", req,
                   "--timeout", "180", "--no-cache"],
                  db_path=db_path, session=session, provider=provider,
                  prompt_file=req, source="compact")
    text = (res.get("answer") or "").strip()
    if not text and res.get("suspect_answer"):
        text = "[兜底提取自失败现场页面文字，可能含页面杂讯]\n\n" + (
            open(res["page_file"], encoding="utf-8").read() if res.get("page_file") else "")
    if not text:
        print("[askw] 摘要生成失败：%s" % (res.get("error") or res.get("status")), file=sys.stderr)
        if res.get("page_file"):
            print("[askw] 现场页面文字在：%s" % res["page_file"], file=sys.stderr)
        return 1

    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(SUMMARIES_DIR, "%s-%s.md" % (re.sub(r"[^\w\-]+", "_", session), stamp))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# 任务接手说明 · %s\n\n> 由 %s 在会话「%s」内生成于 %s\n\n%s\n"
                 % (session, provider, session, stamp, text))
    try:
        con = store.connect(db_path)
        store.set_session_summary(con, session, text)
        con.commit()
        con.close()
    except Exception as e:
        print("[askw] 写库失败：%s" % e, file=sys.stderr)

    nxt = next_name or (session + "-v2")
    print("[askw] 接手说明已生成：%s" % path)
    print("[askw] 已存库（会话历史里可查）")
    print("[askw] 下一步：把这份摘要贴在需求文件开头，用 --session %s 开新对话续写" % nxt)
    return 0


# ---------- 主流程 ----------
def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == "shot":
        return cmd_shot(argv[1:])
    if argv[0] == "compact":
        return cmd_compact(argv[1:])

    db_path, argv = take_opt(argv, ["--db"])
    no_record, argv = take_opt(argv, ["--no-record"])
    no_capture, argv = take_opt(argv, ["--no-capture"])
    no_care, argv = take_opt(argv, ["--no-care"])
    capture_sec, argv = take_opt(argv, ["--capture-sec"])
    argv = absolutize(argv, ["--file", "--text-file", "--attach"])

    session = peek_opt(argv, ["--session"])
    provider = peek_opt(argv, ["-p", "--provider"])
    prompt_file = peek_opt(argv, ["--file", "--text-file"])
    if prompt_file:
        prompt_file = os.path.abspath(prompt_file)

    # A：派发前做会话用量检查，超阈值提醒压缩（压缩交给在线 AI 做）
    if session and not no_record:
        try:
            con = store.connect(db_path)
            u = store.session_usage(con, session)
            con.close()
            if u["turns"] >= TURN_LIMIT or u["chars"] >= CHAR_LIMIT:
                print("[askw] 注意：会话「%s」已 %d 轮 / 累计 %s 字，上下文偏重"
                      "（建议上限 %d 轮 / %d 字）" % (session, u["turns"], u["chars"],
                                                    TURN_LIMIT, CHAR_LIMIT), file=sys.stderr)
                print("[askw]   老对话聊久了网页 AI 会变笨/变慢，建议先熔断：\n"
                      "[askw]   %s compact --session %s" % (os.path.basename(sys.argv[0]), session),
                      file=sys.stderr)
        except Exception:
            pass

    res = run_ask(argv, db_path=db_path, session=session, provider=provider,
                  prompt_file=prompt_file, care=not no_care, capture=not no_capture,
                  capture_sec=capture_sec or 4.0, record=not no_record)

    sys.stdout.write(res.get("out") or "")
    if res.get("err"):
        sys.stderr.write(res["err"])

    if res.get("watchdog"):
        print("[askw] 看护处置：%s" % res["watchdog"], file=sys.stderr)
    if res.get("shot"):
        print("[askw] 调用未成功，已归档现场截图：%s" % res["shot"], file=sys.stderr)
    if res.get("page_file"):
        print("[askw] 现场页面文字已存：%s" % res["page_file"], file=sys.stderr)
    if res.get("fallback_file"):
        print("[askw] 工具没取到答案，但页面里其实已经答完 —— 已兜底提取：%s"
              % res["fallback_file"], file=sys.stderr)
    if res.get("status") != "success" and not res.get("shot"):
        print("[askw] 没抓到浏览器画面（浏览器已关闭或调试端口未开）", file=sys.stderr)

    return res.get("rc", 1)


if __name__ == "__main__":
    sys.exit(main())
