#!/usr/bin/env python3
"""把网页端 AI 返回的「局部改动」精确应用到本地文件。

支持的返回形态：
  A) 标记式：<<<REPLACE>>> 旧 <<<WITH>>> 新 <<<END>>>（可多组）
  B) 「改前 / 改后」标签式：每处改动先给"改前"、再给"改后"，
     中间是代码（DeepSeek 会把 ``` 渲染成 js/复制/下载 行，这里一并清掉）。

匹配（从严到宽）：
  1) 精确逐字符匹配，唯一命中才替换；
  2) 空白容忍匹配（折叠空白定位后映射回原文区间），并用原文首行的缩进给
     新片段重排缩进（AI 常把缩进压平）。
命中 >1 处则跳过并报告，绝不误替换。

用法: python apply_patch.py <AI结果(JSON或文本)> <目标文件> [输出文件]
"""
import json, re, sys

res, path = sys.argv[1], sys.argv[2]
out = sys.argv[3] if len(sys.argv) > 3 else path

raw = open(res, encoding="utf-8").read()
text = raw
try:
    o = json.loads(raw)
    if isinstance(o, dict) and "answer" in o:
        text = o.get("answer") or ""
        print(f"[meta] status={o.get('status')} provider={o.get('provider')} "
              f"url={(o.get('meta') or {}).get('url')}")
except (json.JSONDecodeError, ValueError):
    pass

doc = open(path, encoding="utf-8").read()

NOISE = {"复制", "下载", "运行", "copy", "download", "run"}
LANG = re.compile(r"^\s*(js|javascript|html|css|json|jsx|ts|typescript|vue|bash|sh|python|py)\s*$", re.I)
HEADING = re.compile(r"^\s*[（(]?\s*\d+\s*[.、)）]")


def strip_noise(s: str) -> str:
    lines = s.split("\n")
    while lines and (not lines[-1].strip() or HEADING.match(lines[-1]) or lines[-1].strip() in NOISE):
        lines.pop()
    while lines and (not lines[0].strip() or lines[0].strip() in NOISE):
        lines.pop(0)
    if lines and LANG.match(lines[0]):
        lines.pop(0)
    while lines and not lines[0].strip():
        lines.pop(0)
    return "\n".join(lines)


def clean_fence(s: str) -> str:
    s = s.strip("\n")
    s = re.sub(r"^\s*```[a-zA-Z]*\s*\n", "", s)
    s = re.sub(r"\n```\s*$", "", s)
    return s


# --- 解析成 (旧, 新) 对 ---
MARK = re.compile(
    r"<<<\s*REPLACE\s*>>>\s*\n?(.*?)\n?\s*<<<\s*WITH\s*>>>\s*\n?(.*?)\n?\s*<<<\s*END\s*>>>", re.S)
m = MARK.findall(text)

if m:
    pairs = [(clean_fence(a), clean_fence(b)) for a, b in m]
    mode = "标记式"
else:
    # 去掉整行 UI 噪声后，按「改前/改后」切分
    kept = [ln for ln in text.split("\n") if ln.strip() not in NOISE]
    parts = re.split(r"(改\s*前|改\s*后|更改\s*前|更改\s*后)", "\n".join(kept))
    pairs, before = [], None
    for k in range(1, len(parts) - 1, 2):
        label, content = parts[k], parts[k + 1]
        body = strip_noise(content)
        if re.search("前", label):
            before = body
        elif before is not None:
            pairs.append((before, body))
            before = None
    mode = f"改前/改后标签式({len(pairs)}组)"

if not pairs:
    print("NO_PATCH_FOUND")
    print("--- 原始返回前 1200 字 ---")
    print(text[:1200])
    sys.exit(1)
print(f"解析方式: {mode}")


def norm_map(s):
    chars, idx, prev_ws = [], [], False
    for i, ch in enumerate(s):
        if ch.isspace():
            if not prev_ws:
                chars.append(" "); idx.append(i); prev_ws = True
        else:
            chars.append(ch); idx.append(i); prev_ws = False
    return "".join(chars), idx


def line_indent_before(s: str, pos: int) -> str:
    start = s.rfind("\n", 0, pos) + 1
    return re.match(r"[ \t]*", s[start:]).group(0)


def reindent(new: str, indent: str) -> str:
    if not indent:
        return new
    lines = new.split("\n")
    return lines[0] + "\n" + "\n".join((indent + ln) if ln.strip() else ln for ln in lines[1:])


ok = fail = 0
for i, (old, new) in enumerate(pairs, 1):
    n = doc.count(old)
    if n == 1:
        indent = line_indent_before(doc, doc.find(old))
        doc = doc.replace(old, reindent(new, indent), 1)
        ok += 1
        print(f"[{i}] OK(精确)  {len(old)}→{len(new)} 字符")
        continue

    nd, idmap = norm_map(doc)
    no = norm_map(old)[0].strip()
    hit = nd.find(no)
    dup = nd.find(no, hit + 1) if hit != -1 else -1
    if hit != -1 and dup == -1:
        start = idmap[hit]; end = idmap[hit + len(no) - 1] + 1
        indent = line_indent_before(doc, start)
        doc = doc[:start] + reindent(new, indent).lstrip() + doc[end:]
        ok += 1
        print(f"[{i}] OK(空白容忍)  {len(old)}→{len(new)} 字符")
        continue

    fail += 1
    print(f"[{i}] 失败 精确{n}处，跳过。旧片段前 90 字: {old[:90]!r}")

open(out, "w", encoding="utf-8").write(doc)
print(f"--- 成功 {ok} / 失败 {fail} ---  写出 {out} ({len(doc.encode('utf-8'))} 字节)")
