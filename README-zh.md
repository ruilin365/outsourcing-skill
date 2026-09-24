[English](./README.md) | 简体中文

# 外包skill · 监工模式

> 一个把「写 / 改 HTML、代码、文本」这类重产出**外包给网页版 AI** 的技能：Agent 退居**监工**——只发简洁需求、验收、催返工，达标后再整合交付。

```
用户 ──「外包」──▶ 监工(Agent) ──简洁需求──▶ 网页版 AI(DeepSeek…)
                        ▲                          │
                        │◀──── 结果 ───────────────┘
                    验收 / 催返工
                        │
                     整合 ──▶ 交付
```

## 它解决什么

- 把"码字/写代码"的算力外包给**免费的网页版 AI**，主模型只负责**提炼需求、验收、决策**，省时间与 token。
- 提示词刻意**保持极短**：一句需求 + 一句输出要求；解析/拼接等技术活全部放本地脚本。

## 核心原则

1. **监工只做决策，不亲自写主要产出**：提需求 → 派发 → 验收 → 催返工 → 整合交付。
2. **提示词要短**：长提示词是反模式。
3. **能续聊就续聊**（同一对话有上下文）；**被污染就开新对话并附权威文件**（网页 AI 无跨对话记忆，只认附件）。
4. **小改走补丁、大改/新增走整文件**：网页 AI 无法逐字复述源码，"新增类"补丁必然对不上。
5. **整文件必带"必须保留"清单**，并按清单逐项验收。

> 完整的决策规则与踩坑记录见 [`SKILL.md`](./SKILL.md)。

## 依赖

- **`ask-web-ai`**：`free-web-ai-worker` 的、支持 **`--session` 命名对话** 的版本（本文用 `$AWA` 指代其目录）。
- **Node**（跑上面这个工具）、**Python 3**（跑 `scripts/`）。
- 一个**已登录**的网页版 AI（推荐 DeepSeek：支持附件与视觉）。

## 安装

1. 把本目录放进你的技能目录，例如 `~/.workbuddy/skills/外包skill/`。
2. 确保 `ask-web-ai` 可用，并记下它的目录（下文 `$AWA`）。
3. 首次运行前，对目标站点跑一次登录命令，把登录态落盘到 `~/.agent-web-ai/`。

## 目录结构

```
.
├── SKILL.md                 # 技能说明：监工流程 + 决策规则 + 踩坑
├── README.md                # English（GitHub 落地页）
├── README-zh.md             # 简体中文说明（本文件）
├── LICENSE                  # Apache-2.0
├── NOTICE
├── scripts/
│   ├── extract.py           # 从 AI 返回中抽取「完整文件」
│   └── apply_patch.py       # 把「改前/改后」片段「精确替换」进本地文件
└── examples/
    └── todo-app-demo.html   # 由本流程产出的示例（单文件待办 App）
```

## 快速开始

```bash
AWA=/path/to/free-web-ai-worker

# 1) 首次外包：让网页 AI 产出完整文件（--session 记住这次对话）
node "$AWA/bin/ask-web-ai.js" ask -p deepseek --session my-task \
  --file 需求.txt --timeout 180 --no-cache > 结果.json 2> 结果.err
python scripts/extract.py 结果.json 目标.html

# 2) 续改：回到同一对话，只让它改一段（省 token）
node "$AWA/bin/ask-web-ai.js" ask -p deepseek --session my-task \
  --file 需求.txt --timeout 180 --no-cache > 返回.json 2> 返回.err
python scripts/apply_patch.py 返回.json 目标.html
```

`extract.py` / `apply_patch.py` 均为纯标准库 Python，无需安装依赖。

## 安全提示

外包内容会经过**第三方站点**（DeepSeek 等）。**涉密材料不要外包。**

## 致谢

本项目的**思路**来自开源项目 **[free-web-ai-worker](https://github.com/augustlies/free-web-ai-worker)**（作者 [@augustlies](https://github.com/augustlies)，MIT 协议）——它提出了「让 Agent 把纯文本子任务外包给网页版免费 AI」的做法，并提供了驱动网页版 AI 的 CLI。

本 skill 在此基础上聚焦封装**「监工工作流」**：简洁需求派发、结果验收与返工循环、命名对话续聊（`--session`）、「改前/改后」局部替换与版本管理等。谨向原作者的探索与分享致谢。

> 本项目为独立项目，与上述原仓库无隶属关系；使用前请自行确认各网页版 AI 站点的服务条款。

## License

[Apache-2.0](./LICENSE) © 2026 ruilin365
