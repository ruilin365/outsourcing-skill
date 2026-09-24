#!/usr/bin/env python3
"""从网页端 AI 的返回中抽取内容。

输入可以是:
  - CLI 的 JSON 结果 (含 answer / meta.url)  -> 取 answer 抽取 HTML, 并打印对话URL;
  - 纯文本返回                                -> 直接抽取。

HTML 抽取策略: 代码块 ```html ... ``` -> <!DOCTYPE html>..</html> -> 整段。
用法:
  python extract.py <结果文件> <输出html>     # 抽取 HTML 落盘
  python extract.py <结果文件>                # 只打印 meta + answer 文本(探针)
"""
import json, re, sys

src = sys.argv[1]
dst = sys.argv[2] if len(sys.argv) > 2 else None

raw = open(src, encoding="utf-8").read()
chat_url = None

text = raw
try:
    obj = json.loads(raw)
    if isinstance(obj, dict) and "answer" in obj:
        text = obj.get("answer") or ""
        meta = obj.get("meta") or {}
        chat_url = meta.get("url")
        print(f"[meta] status={obj.get('status')} provider={obj.get('provider')} "
              f"chars={meta.get('chars')} url={chat_url}")
        if obj.get("status") != "success":
            print(f"[meta] ERROR code={obj.get('code')} error={obj.get('error')}", file=sys.stderr)
except (json.JSONDecodeError, ValueError):
    pass

if dst is None:  # 只做探针展示, 不写盘
    print("----- ANSWER TEXT -----")
    print(text.strip())
    sys.exit(0)

def save(html):
    html = html.strip()
    with open(dst, "w", encoding="utf-8") as f:
        f.write(html + "\n")
    print(f"OK bytes={len(html.encode('utf-8'))} -> {dst}")

m = re.search(r"```(?:html)?\s*(.*?)```", text, re.S | re.I)
if m:
    body = re.sub(r"^\s*(复制|下载|运行|copy|download|run)\b.*$", "", m.group(1), flags=re.I | re.M)
    save(body)
    sys.exit(0)

start = re.search(r"<!DOCTYPE\s+html", text, re.I) or re.search(r"<html[\s>]", text, re.I)
if start:
    end = text.rfind("</html>")
    if end != -1:
        save(text[start.start():end + len("</html>")])
        sys.exit(0)

save(text)
