# -*- coding: utf-8 -*-
"""
serve.py —— 看板的本地服务（让"刷新"和"改配额"真正生效）

为什么需要它：
    看板是离线单文件，双击打开只能看到烘焙进去的那一份快照——
    此时点"刷新"没有任何新数据可拉，改配额也存不下来。
    用这个服务打开，页面就能：
      · 手动刷新 / 每 30 秒自动刷新 —— 每次都从 SQLite 拉最新数据
      · 在页面上直接改每日配额 —— 写回库里，永久生效

用法：
    <py> serve.py                 # 默认 http://127.0.0.1:8787
    <py> serve.py --port 9000     # 换端口
    <py> serve.py --no-browser    # 不自动开浏览器

只监听 127.0.0.1（本机），不对外网暴露；数据全部在本地。
"""

import argparse
import datetime as dt
import http.server
import json
import os
import subprocess
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import store  # noqa: E402


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def log_message(self, fmt, *args):  # 静音访问日志
        pass

    def end_headers(self):
        # 统一禁用缓存：否则改完看板，浏览器会拿旧副本
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    # ---------- 工具 ----------
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---------- GET ----------
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html", "/dashboard.html"):
            self.path = "/dashboard.html"
            return super().do_GET()
        if path == "/api/data":
            return self._data()
        if path == "/api/scan":
            return self._scan()
        if path == "/api/ping":
            return self._json({"ok": True, "db": store.DEFAULT_DB,
                               "serverTime": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        return super().do_GET()

    # ---------- POST ----------
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path != "/api/quota":
            return self._json({"ok": False, "error": "not found"}, 404)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._json({"ok": False, "error": "bad request: %s" % e}, 400)
        provider = (payload.get("provider") or "").strip()
        con = None
        try:
            con = store.connect()
            v = store.set_quota(con, provider, payload.get("dailyQuota"))
            return self._json({"ok": True, "provider": provider, "dailyQuota": v})
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 400)
        finally:
            if con:
                con.close()

    # ---------- 业务 ----------
    def _data(self):
        con = None
        try:
            con = store.connect()
            data = store.build_data(con)
            data["live"] = True
            return self._json(data)
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 500)
        finally:
            if con:
                con.close()

    def _scan(self):
        """触发一次增量扫描（站点 / 登录态 / 历史对话），调用记录不受影响。"""
        con = None
        try:
            con = store.connect()
            tasks = store.get_meta(con, "tasks") or ""
            tool = store.get_meta(con, "tool") or ""
            con.close()
            con = None
            cmd = [sys.executable, os.path.join(HERE, "collect.py"), "--to-db"]
            if tasks:
                cmd += ["--tasks", tasks]
            if tool:
                cmd += ["--tool", tool]
            p = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=180)
            lines = [x for x in (p.stdout or "").strip().splitlines() if x.strip()]
            return self._json({"ok": p.returncode == 0, "output": lines[-3:]})
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 500)
        finally:
            if con:
                con.close()


def main():
    ap = argparse.ArgumentParser(description="看板本地服务")
    ap.add_argument("--port", type=int, default=8787, help="端口（默认 8787）")
    ap.add_argument("--host", default="127.0.0.1", help="监听地址（默认仅本机）")
    ap.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    a = ap.parse_args()

    store.connect().close()  # 确保库和表已建好
    httpd = http.server.ThreadingHTTPServer((a.host, a.port), Handler)
    url = "http://%s:%d/dashboard.html" % (a.host, a.port)
    print("看板服务已启动：", url)
    print("数据库：", store.DEFAULT_DB)
    print("按 Ctrl+C 停止")
    if not a.no_browser:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
