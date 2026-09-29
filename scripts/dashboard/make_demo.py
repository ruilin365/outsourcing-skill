# -*- coding: utf-8 -*-
"""
生成 examples/dashboard-demo.html —— 一份「全部虚构」的示例看板。

用途：给人看效果用。真实看板含本机路径、个人对话标题与调用记录，
不适合进公开仓库；示例看板的数据全部是编的，随手传看都没问题。

用法： python make_demo.py [输出.html]
默认输出到 <仓库根>/examples/dashboard-demo.html
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render as R  # noqa: E402

D = "https://chat.deepseek.com/a/chat/s/"
Q = "https://chat.qwen.ai/"


def uid(n):
    """形如真实 UUID，但明显可辨认是编的。"""
    return "0demo000-0000-4000-8000-%012d" % n


# 示例「失败现场截图」文件名（与 demo 同目录，由 build_demo_failure_png() 生成）
FAIL_SHOT = "dashboard-demo-failure.png"


C1 = D + uid(1)   # 首版生成
C2 = D + uid(2)   # 深色主题
C3 = D + uid(3)   # 移动端适配
C4 = D + uid(4)   # 导出按钮疑问

DEMO = {
    "demo": True,
    "generatedAt": "2026-03-18 22:15:02",
    "sources": {
        "profile": "C:\\Users\\demo\\.agent-web-ai\\profiles\\edge",
        "tool": "C:\\tools\\free-web-ai-worker",
        "tasks": "C:\\demo\\html-tasks\\ledger",
    },
    "providers": [
        {
            "id": "duckai", "name": "Duck.ai", "url": "https://duck.ai/",
            "requiresLogin": False, "enabled": True,
            "note": "Default. No account needed, fastest in testing (~9s).",
            "cookies": [], "lsPresent": True, "tokens": {},
            "visits": 2, "lastVisit": "2026-03-17 21:12:18",
            "firstVisit": "2026-03-17 21:12:18",
            "conversations": 0, "calls": 1, "loginState": "anonymous",
            "evidence": ["localStorage 中有本站记录",
                         "历史访问 2 次，最近 2026-03-17 21:12:18"],
        },
        {
            "id": "qwen", "name": "Qwen Chat", "url": "https://chat.qwen.ai/",
            "requiresLogin": False, "enabled": True,
            "note": "Guest mode verified; signing in raises rate limits.",
            "cookies": [], "lsPresent": True, "tokens": {},
            "visits": 1, "lastVisit": "2026-03-18 20:05:31",
            "firstVisit": "2026-03-18 20:05:31",
            "conversations": 1, "calls": 1, "loginState": "anonymous",
            "evidence": ["localStorage 中有本站记录",
                         "历史访问 1 次，最近 2026-03-18 20:05:31"],
        },
        {
            "id": "deepseek", "name": "DeepSeek", "url": "https://chat.deepseek.com/",
            "requiresLogin": True, "enabled": True, "note": "",
            "cookies": [".thumbcache_1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d",
                        "HWWAFSESID", "HWWAFSESTIME", "ds_session_id"],
            "lsPresent": True,
            "tokens": {"usertoken": {"len": 64, "sha256": "0d3f8a1c7b52"},
                       "token": {"len": 64, "sha256": "0d3f8a1c7b52"}},
            "visits": 41, "lastVisit": "2026-03-18 21:20:10",
            "firstVisit": "2026-03-17 21:30:02",
            "conversations": 4, "calls": 9, "loginState": "signed-in",
            "evidence": [
                "Cookie 4 项：.thumbcache_1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d, "
                "HWWAFSESID, HWWAFSESTIME, ds_session_id",
                "localStorage 中有本站记录",
                "检测到登录凭据 usertoken（64 字符，已脱敏）",
                "检测到登录凭据 token（64 字符，已脱敏）",
                "历史访问 41 次，最近 2026-03-18 21:20:10"],
        },
        {
            "id": "chatgpt", "name": "ChatGPT", "url": "https://chatgpt.com/",
            "requiresLogin": True, "enabled": True, "note": "",
            "cookies": [], "lsPresent": False, "tokens": {},
            "visits": 0, "lastVisit": None, "firstVisit": None,
            "conversations": 0, "calls": 0, "loginState": "unused",
            "evidence": ["本 profile 无任何访问痕迹"],
        },
        {
            "id": "grok", "name": "Grok", "url": "https://grok.com/",
            "requiresLogin": True, "enabled": True, "note": "",
            "cookies": [], "lsPresent": False, "tokens": {},
            "visits": 2, "lastVisit": "2026-03-18 20:58:04",
            "firstVisit": "2026-03-18 20:58:04",
            "conversations": 0, "calls": 0, "loginState": "not-signed-in",
            "evidence": ["有访问记录但未发现 Cookie / localStorage 登录凭据",
                         "历史访问 2 次，最近 2026-03-18 20:58:04"],
        },
        {
            "id": "gemini", "name": "Google Gemini",
            "url": "https://gemini.google.com/app",
            "requiresLogin": True, "enabled": False,
            "note": "EXPERIMENTAL: selectors were written against the published DOM; "
                    "enable only after verifying by hand.",
            "cookies": [], "lsPresent": False, "tokens": {},
            "visits": 0, "lastVisit": None, "firstVisit": None,
            "conversations": 0, "calls": 0, "loginState": "unused",
            "evidence": ["本 profile 无任何访问痕迹"],
        },
    ],
    "conversations": [
        {
            "provider": "deepseek", "url": C1, "title": "记账小工具首版生成",
            "visits": 3, "firstVisit": "2026-03-17 21:33:40",
            "lastVisit": "2026-03-17 22:19:05", "kind": "chat",
            "session": "ledger-app", "calls": 3, "okCalls": 3,
            "answerChars": 38172, "avgSec": 47.0,
        },
        {
            "provider": "deepseek", "url": C3, "title": "记账本移动端布局适配",
            "visits": 3, "firstVisit": "2026-03-18 20:22:11",
            "lastVisit": "2026-03-18 21:05:44", "kind": "chat",
            "session": "ledger-mobile", "calls": 2, "okCalls": 2,
            "answerChars": 19600, "avgSec": 50.1,
        },
        {
            "provider": "deepseek", "url": C2, "title": "记账本深色主题调整",
            "visits": 2, "firstVisit": "2026-03-17 22:31:52",
            "lastVisit": "2026-03-17 22:58:36", "kind": "chat",
            "session": "ledger-dark", "calls": 2, "okCalls": 2,
            "answerChars": 14200, "avgSec": 40.5,
        },
        {
            "provider": "deepseek", "url": C4, "title": "记账本导出按钮的疑问",
            "visits": 1, "firstVisit": "2026-03-18 21:41:07",
            "lastVisit": "2026-03-18 21:47:29", "kind": "chat",
            "session": None, "calls": 2, "okCalls": 1,
            "answerChars": 3910, "avgSec": 28.7,
        },
        {
            "provider": "qwen", "url": Q, "title": "Qwen Chat 首页",
            "visits": 1, "firstVisit": "2026-03-18 20:05:31",
            "lastVisit": "2026-03-18 20:05:31", "kind": "entry",
            "session": None, "calls": 1, "okCalls": 1,
            "answerChars": 1180, "avgSec": 9.8,
        },
    ],
    "sessions": [
        {"name": "ledger-app", "url": C1, "provider": "deepseek",
         "updatedAt": "2026-03-17T14:19:05.221Z", "title": "记账小工具首版生成", "calls": 3},
        {"name": "ledger-dark", "url": C2, "provider": "deepseek",
         "updatedAt": "2026-03-17T14:58:36.508Z", "title": "记账本深色主题调整", "calls": 2},
        {"name": "ledger-mobile", "url": C3, "provider": "deepseek",
         "updatedAt": "2026-03-18T13:05:44.907Z", "title": "记账本移动端布局适配", "calls": 2},
    ],
    "calls": [
        {"id": "probe", "file": "probe.json", "provider": "deepseek", "model": "DeepSeek",
         "status": "success", "error": None, "chars": 92, "elapsedMs": 41230,
         "cached": False, "chatUrl": C1, "startedAt": "2026-03-17 21:36:12",
         "artifacts": None, "promptFile": "probe_prompt.txt",
         "prompt": "我们刚在同一个对话里做过一个「单文件记账小工具」HTML。只回答两点，不要输出代码：\n\n"
                   "1. 当前主题色是什么？给出十六进制值。\n2. 底部有没有「导出 CSV」按钮？\n\n"
                   "如果看不到上一版内容，请直接说明。",
         "answerHead": "我看不到你提到的上一版 HTML 内容，因此无法确定主题色的十六进制值，"
                       "也无法确认底部是否有「导出 CSV」按钮。",
         "source": "cli-json"},
        {"id": "gen1", "file": "gen1.json", "provider": "deepseek", "model": "DeepSeek",
         "status": "success", "error": None, "chars": 18960, "elapsedMs": 68520,
         "cached": False, "chatUrl": C1, "startedAt": "2026-03-17 21:41:50",
         "artifacts": None, "promptFile": "req_gen1.txt",
         "prompt": "请帮我写一个单文件 HTML 记账小工具，要求：\n"
                   "1. 纯前端、单文件、零依赖，双击就能用；\n"
                   "2. 能记一笔（金额、分类、备注、日期），列表按日期倒序；\n"
                   "3. 顶部显示本月支出合计，右下角有「+」浮动按钮；\n"
                   "4. 数据存 localStorage，刷新不丢；\n"
                   "5. 手机和电脑都要好看。\n\n"
                   "只输出完整 HTML 文件，不要解释。",
         "answerHead": "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"UTF-8\">"
                       "\n<title>记账本</title>\n<style>:root{--bg:#f7f8fb;...",
         "source": "cli-json"},
        {"id": "gen2", "file": "gen2.json", "provider": "deepseek", "model": "DeepSeek",
         "status": "success", "error": None, "chars": 19120, "elapsedMs": 31240,
         "cached": False, "chatUrl": C1, "startedAt": "2026-03-17 21:58:03",
         "artifacts": None, "promptFile": "req_gen2.txt",
         "prompt": "这一版不错。再加两点：\n"
                   "1. 分类用下拉选择（餐饮 / 交通 / 购物 / 其他），每类配一个颜色圆点；\n"
                   "2. 列表项左滑（手机上）/ 悬停（电脑上）出现删除按钮。\n\n"
                   "给我完整文件，不要省略。",
         "answerHead": None, "source": "cli-json"},
        {"id": "dark", "file": "dark.json", "provider": "deepseek", "model": "DeepSeek",
         "status": "success", "error": None, "chars": 8260, "elapsedMs": 44810,
         "cached": False, "chatUrl": C2, "startedAt": "2026-03-17 22:34:19",
         "artifacts": None, "promptFile": "req_dark.txt",
         "prompt": "把这份记账本改成支持深色模式：跟随系统设置自动切换，"
                   "右上角再给一个手动切换按钮，记住用户的选择。\n\n"
                   "改动不大，请只给出需要替换的片段，用「改前 / 改后」两个代码块标出来。",
         "answerHead": "下面是需要替换的片段。\n\n改前：\n:root{--bg:#f7f8fb;--text:#1a1d24}",
         "source": "cli-json"},
        {"id": "dark2", "file": "dark2.json", "provider": "deepseek", "model": "DeepSeek",
         "status": "success", "error": None, "chars": 5940, "elapsedMs": 36120,
         "cached": False, "chatUrl": C2, "startedAt": "2026-03-17 22:45:11",
         "artifacts": None, "promptFile": "req_dark2.txt",
         "prompt": "深色下金额数字对比度偏低，把支出用浅红、收入用浅绿，"
                   "但不要刺眼。同样给「改前 / 改后」片段。",
         "answerHead": None, "source": "cli-json"},
        {"id": "mob1", "file": "mob.json", "provider": "deepseek", "model": "DeepSeek",
         "status": "success", "error": None, "chars": 12340, "elapsedMs": 52960,
         "cached": False, "chatUrl": C3, "startedAt": "2026-03-18 20:26:38",
         "artifacts": None, "promptFile": "req_mobile.txt",
         "prompt": "手机上顶部的月份合计会换行、浮动按钮挡住列表最后一项。\n"
                   "请修一下：小屏时合计改成一行可横滑，列表底部留出 72px 安全间距。\n\n"
                   "给「改前 / 改后」片段。",
         "answerHead": "改前：\n.summary{display:flex;gap:12px}\n\n改后：\n"
                       ".summary{display:flex;gap:12px;overflow-x:auto}",
         "source": "cli-json"},
        {"id": "mob2", "file": "mob2.json", "provider": "deepseek", "model": "DeepSeek",
         "status": "success", "error": None, "chars": 7260, "elapsedMs": 47330,
         "cached": False, "chatUrl": C3, "startedAt": "2026-03-18 20:58:52",
         "artifacts": None, "promptFile": "req_mobile2.txt",
         "prompt": "「+」按钮在 iPhone 的 Safari 上会被底部工具栏挡一半，"
                   "改成用 env(safe-area-inset-bottom) 定位。给替换片段。",
         "answerHead": None, "source": "cli-json"},
        {"id": "q1", "file": "q1.json", "provider": "deepseek", "model": "DeepSeek",
         "status": "success", "error": None, "chars": 3910, "elapsedMs": 28740,
         "cached": False, "chatUrl": C4, "startedAt": "2026-03-18 21:43:12",
         "artifacts": None, "promptFile": "req_export.txt",
         "prompt": "我想加一个「导出 CSV」按钮，但不确定中文表头在 Excel 里乱码该怎么处理。\n"
                   "直接告诉我应该怎么做就行，不用给完整文件。",
         "answerHead": "关键是在导出内容前面加 UTF-8 BOM（\\ufeff），"
                       "否则 Excel 会按 GBK 猜编码。可以用 Blob + TextEncoder 拼出来…",
         "source": "cli-json"},
        {"id": "q2", "file": "q2.json", "provider": "deepseek", "model": "DeepSeek",
         "status": "error",
         "error": "页面 60s 内未出现答案节点，已放弃（该会话可能触发了人机校验）。"
                  "配额已计入当日用量。",
         "chars": 0, "elapsedMs": None, "cached": False, "chatUrl": C4,
         "startedAt": "2026-03-18 21:46:55", "artifacts": None,
         "promptFile": "req_export2.txt",
         "prompt": "那就按你说的，给我把这个导出按钮完整实现出来，"
                   "并说明为什么 iOS 上点击可能没反应。",
         "answerHead": None, "source": "cli-json"},
        {"id": "qw1", "file": "qw1.json", "provider": "qwen", "model": "Qwen",
         "status": "success", "error": None, "chars": 1180, "elapsedMs": 9830,
         "cached": False, "chatUrl": Q, "startedAt": "2026-03-18 20:05:31",
         "artifacts": None, "promptFile": None,
         "prompt": "用一句话说明 localStorage 和 sessionStorage 的区别。",
         "answerHead": "localStorage 关掉浏览器也保留，sessionStorage 关掉标签页就清空。",
         "source": "cli-json"},
        {"id": "dk1", "file": "dk1.json", "provider": "duckai", "model": "GPT-4o mini",
         "status": "success", "error": None, "chars": 740, "elapsedMs": 8760,
         "cached": False, "chatUrl": None, "startedAt": "2026-03-17 21:12:18",
         "artifacts": None, "promptFile": None,
         "prompt": "HTML 里怎么让 input type=number 在手机上调出数字键盘？",
         "answerHead": "用 inputmode=\"numeric\" 或 type=\"tel\"，两者在 iOS 上都会调出数字键盘。",
         "source": "cli-json"},
    ],
    "quota": [
        {"provider": "duckai", "calls": 1, "dailyQuota": 40,
         "lastCallAt": "2026-03-17 21:12:18", "history": ["2026-03-17 21:12:18"]},
        {"provider": "qwen", "calls": 1, "dailyQuota": 40,
         "lastCallAt": "2026-03-18 20:05:31", "history": ["2026-03-18 20:05:31"]},
        {"provider": "deepseek", "calls": 9, "dailyQuota": 40,
         "lastCallAt": "2026-03-18 21:47:29",
         "history": ["2026-03-17 21:36:12", "2026-03-17 21:41:50", "2026-03-17 21:58:03",
                     "2026-03-17 22:34:19", "2026-03-17 22:45:11", "2026-03-18 20:26:38",
                     "2026-03-18 20:58:52", "2026-03-18 21:43:12", "2026-03-18 21:46:55"]},
    ],
    "outputs": [
        {"file": "ledger.html", "size": 41220, "mtime": "2026-03-18 22:14:07"},
        {"file": "ledger.v1.html", "size": 19124, "mtime": "2026-03-17 21:52:44"},
        {"file": "ledger.v2.html", "size": 20870, "mtime": "2026-03-17 22:03:58"},
        {"file": "ledger.v3.html", "size": 23112, "mtime": "2026-03-17 22:49:33"},
        {"file": "ledger.v4.html", "size": 35608, "mtime": "2026-03-18 20:59:41"},
    ],
    "notes": [
        {"file": "gen_result.txt", "note": "整文件生成 v1", "size": 19100,
         "mtime": "2026-03-17 21:52:44", "chatUrl": C1,
         "conversation": "记账小工具首版生成"},
        {"file": "dark_result.txt", "note": "深色模式改动片段", "size": 8310,
         "mtime": "2026-03-17 22:36:02", "chatUrl": C2,
         "conversation": "记账本深色主题调整"},
    ],
    "totals": {
        "sites": 6, "sitesUsed": 4, "signedIn": 1, "conversations": 5,
        "sessions": 3, "calls": 11, "okCalls": 10,
        "answerChars": 77802, "avgSec": 36.5,
    },
}


def derive(d):
    """
    把示例数据补齐成与真实 `store.build_data()` **同构**的结构。

    为什么必须补：看板前端对字段有依赖（今日调用、今日配额/历史累计、
    最近活动来源、失败现场截图、数据源信息…）。字段缺了，示例看板的界面
    就和真实的不一样——所以这里按真实逻辑把派生值算出来，而不是手写死值。
    以后真实看板再加字段，这里补一行即可跟上。
    """
    today = "2026-03-18"                      # 与 generatedAt 同一天
    calls = d["calls"]

    # totals：今日调用数
    d["totals"]["today"] = today
    d["totals"]["todayCalls"] = len(
        [c for c in calls if str(c.get("startedAt") or "").startswith(today)])

    # db：顶部「数据源 / 最后一次外包调用」那一行
    stamps_all = sorted([c["startedAt"] for c in calls if c.get("startedAt")])
    d["db"] = {
        "path": "web-ai.db",
        "lastCallAt": stamps_all[-1] if stamps_all else None,
        "lastScanAt": d["generatedAt"],
        "callCount": len(calls),
    }

    # providers：今日调用数 / 最近一次调用 / 最近活动来源
    for p in d["providers"]:
        mine = sorted([c["startedAt"] for c in calls
                       if c.get("provider") == p["id"] and c.get("startedAt")])
        p["todayCalls"] = len([s for s in mine if s.startswith(today)])
        p["lastCallAt"] = mine[-1] if mine else None
        p["browserLastVisit"] = p.get("lastVisit")
        if p["lastCallAt"] and (not p.get("lastVisit") or p["lastCallAt"] > p["lastVisit"]):
            p["lastVisit"], p["lastVisitSource"] = p["lastCallAt"], "外包调用"
        else:
            p["lastVisitSource"] = "浏览器访问" if p.get("lastVisit") else None
        p["updatedAt"] = d["generatedAt"]

    # calls：会话名 + 失败现场相关字段
    url2sess = {c["url"]: c.get("session") for c in d["conversations"]}
    for c in calls:
        c["session"] = url2sess.get(c.get("chatUrl"))
        c.setdefault("shot", None)
        c.setdefault("pageText", None)
        c.setdefault("watchdog", None)

    # 让示例里**出现一条**带失败现场的记录，否则「查看失败现场截图」这个界面
    # 在示例看板里永远看不见（真实环境需要真出一次错才会有）
    for c in calls:
        if c.get("status") != "success":
            c["shot"] = FAIL_SHOT
            c["watchdog"] = "text:继续×1"
            c["pageText"] = ("DeepSeek 探索未至之境 深度思考 智能搜索 请完成安全验证 "
                             "拖动滑块完成拼图 网络繁忙，请稍后再试")
            if not c.get("answerHead"):
                c["answerHead"] = ("（兜底提取）页面已经答完但工具没取到时的答案示例："
                                   "localStorage 关掉浏览器也保留，sessionStorage 关掉标签页就清空。")
            break

    # sessions：接手说明（会话熔断产物）
    for s in d["sessions"]:
        s.setdefault("summary", None)
    if d["sessions"]:
        d["sessions"][0]["summary"] = (
            "任务目标：把单文件记账小工具做完（增删改查 + 深色模式 + 移动端适配）。\n"
            "已达成：ledger.html 已可用，分类下拉与滑动删除已加；深色模式跟随系统。\n"
            "遗留：导出 CSV 的中文乱码问题待确认；iOS 上「+」按钮遮挡需回归一次。\n"
            "约束：纯前端、单文件、零依赖，不引入任何 CDN。")

    # quota：今日调用数（跨天归零）+ 历史累计
    for q in d["quota"]:
        mine = sorted([c["startedAt"] for c in calls
                       if c.get("provider") == q["provider"] and c.get("startedAt")])
        q["calls"] = len([s for s in mine if s.startswith(today)])
        q["totalCalls"] = len(mine)
        q["date"] = today
        q["toolHistory"] = q.pop("history", [])
        if mine:
            q["lastCallAt"] = mine[-1]

    return d


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(HERE), "..", "examples", "dashboard-demo.html")
    out = os.path.abspath(out)
    payload = json.dumps(derive(DEMO), ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    html = R.TPL.replace("__DATA__", payload)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(html)
    print("written:", out, os.path.getsize(out), "bytes")


if __name__ == "__main__":
    main()
