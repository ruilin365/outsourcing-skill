#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup.py —— 从本仓库自带的快照安装 ask-web-ai

为什么有它：
    本 skill 需要一个**支持 `--session` 命名对话**的 ask-web-ai，
    而上游 free-web-ai-worker 并未提供该能力（差异见 `patches/`）。
    为了让"拉取本仓库即可使用"成立、且**不依赖外网与上游仓库是否还在**，
    仓库自带一份自包含快照（`vendor/*.zip`，内含 node_modules / 系统 Edge 驱动配置）。

用法：
    python scripts/setup.py                  # 解压到 ~/.tools/ 并自检（推荐）
    python scripts/setup.py --dest D:/tools  # 指定安装目录
    python scripts/setup.py --check          # 只做环境自检，不写磁盘
    python scripts/setup.py --force          # 目标已存在时覆盖安装

装完只需再登录一次（登录态无法随包分发，每台机器都要做）：
    node <安装目录>/bin/ask-web-ai.js login --provider deepseek
"""

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
VENDOR = REPO / "vendor"
EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_snapshot():
    if not VENDOR.is_dir():
        return None
    zips = sorted(VENDOR.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    return zips[0] if zips else None


def node_version():
    node = shutil.which("node") or os.environ.get("AWA_NODE")
    if not node or not Path(node).exists():
        return None, None
    try:
        out = subprocess.run([node, "-v"], capture_output=True, text=True, timeout=10)
        return node, (out.stdout or "").strip()
    except Exception:
        return node, None


def edge_path():
    for p in EDGE_PATHS:
        if Path(p).exists():
            return p
    return None


def install(zip_path, dest, force):
    target = Path(dest) / "free-web-ai-worker-patched"
    if target.exists() and not force:
        print("[skip] 目标已存在：%s（要覆盖请加 --force）" % target)
        return target
    dest.mkdir(parents=True, exist_ok=True)
    print("[unzip] %s -> %s" % (zip_path.name, dest))
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)
    print("[ok] 已解压到 %s" % target)
    return target


def selfcheck(target=None):
    print("\n=== 环境自检 ===")
    ok = True

    node, ver = node_version()
    if not node:
        print("[X] 找不到 Node —— 需要 Node 20+（或设 AWA_NODE 指向 node.exe）")
        ok = False
    else:
        major = 0
        try:
            major = int((ver or "").lstrip("v").split(".")[0])
        except Exception:
            pass
        if major >= 20:
            print("[ok] Node %s -> %s" % (ver, node))
        else:
            print("[X] Node 版本过低：%s（需要 >= 20）" % ver)
            ok = False

    e = edge_path()
    if e:
        print("[ok] 浏览器：%s" % e)
    else:
        print("[!] 未在常见路径找到 Edge —— ask-web-ai 依赖本机已装的 Edge/Chrome")
        ok = False

    if target:
        tp = Path(target)
        for rel, label in (("bin/ask-web-ai.js", "入口"),
                           ("node_modules/playwright-core/package.json", "依赖 playwright-core"),
                           ("LICENSE", "上游 MIT 许可")):
            if (tp / rel).exists():
                print("[ok] %s：%s" % (label, rel))
            else:
                print("[X] 缺少 %s：%s" % (label, rel))
                ok = False
    else:
        print("[!] 未指定安装目录，跳过文件校验（用 --check 时给出 --dest 可校验）")

    return ok, node


def main():
    ap = argparse.ArgumentParser(description="从仓库自带快照安装 ask-web-ai")
    ap.add_argument("--dest", default=os.path.join(os.path.expanduser("~"), ".tools"),
                    help="安装目录（默认 ~/.tools/，会被自动探测到）")
    ap.add_argument("--check", action="store_true", help="只自检，不解压")
    ap.add_argument("--force", action="store_true", help="目标已存在时覆盖")
    args = ap.parse_args()

    print("本仓库: %s" % REPO)
    snap = find_snapshot()
    if not snap:
        print("[X] 找不到 vendor/*.zip —— 请确认仓库完整（见 README 的安装章节）")
        return 2
    print("快照  : %s (%.1f MB)" % (snap.name, snap.stat().st_size / 1048576))

    target = None
    if args.check:
        guess = Path(args.dest) / "free-web-ai-worker-patched"
        target = str(guess) if guess.exists() else None
    else:
        target = str(install(snap, Path(args.dest), args.force))

    ok, node = selfcheck(target)

    print("\n=== 下一步 ===")
    if target:
        print("1) 登录一次（登录态无法随包分发，每台机器都要做）：")
        print('   node "%s/bin/ask-web-ai.js" login --provider deepseek' % target)
        print("2) 让 askw.py 找到它（放在 ~/.tools/ 下会被自动探测，否则显式指定）：")
        print('   set AWA_TOOL=%s' % target)
        print("3) 自检整体链路：")
        print('   python "%s" ask -p deepseek --timeout 180 --file 你的需求.txt > 结果.json'
              % (HERE / "dashboard" / "askw.py"))
    print("\n结果：%s" % ("环境就绪" if ok else "还有项目需要处理（见上面的 [X] / [!]）"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
