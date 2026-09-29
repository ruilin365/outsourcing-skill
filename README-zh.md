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

## 亮点（先看这里）

| 亮点 | 说明 |
| --- | --- |
| **监工模式** | Agent 只做「提需求 → 派发 → 验收 → 催返工 → 整合」，主要产出交给网页 AI。省 token，决策权仍在自己手里 |
| **实时看护** | 调用**进行中**每 4 秒自动处置拦路弹窗（年龄确认 / 欢迎层 / Cookie 同意）并截图留底。**不是等超时关闭后事后分析**——那一轮本来就能跑通 |
| **失败 ≠ 没答案** | 网页 AI 的"失败"多半是"**取件失败**"：答案已完整生成在页面上，只是工具没取到。本技能会自动抠出答案并存档 |
| **本地持久库 + 离线看板** | 调用流水、每日配额、对话、产出全部落 SQLite；看板是离线单文件 HTML，只读渲染，不再每次重扫 |
| **会话熔断 + 在线 AI 交接** | 老对话聊久了网页 AI 会变笨/变慢；超阈值自动告警，一条命令让**在线 AI 自己**产出「接手说明」，换新对话续接 |
| **零依赖** | 所有脚本纯标准库（Python）+ Node 原生 `WebSocket`（CDP），不需要装任何第三方包 |

## 它解决什么

- 把"码字/写代码"的算力外包给**免费的网页版 AI**，主模型只负责**提炼需求、验收、决策**，省时间与 token。
- 提示词刻意**保持极短**：一句需求 + 一句输出要求；解析/拼接等技术活全部放本地脚本。

## 核心原则

1. **监工只做决策，不亲自写主要产出**：提需求 → 派发 → 验收 → 催返工 → 整合交付。
2. **提示词要短**：长提示词是反模式。
3. **能续聊就续聊**（同一对话有上下文）；**被污染或聊太久就开新对话**（网页 AI 无跨对话记忆，只认附件）。
4. **小改走补丁、大改/新增走整文件**：网页 AI 无法逐字复述源码，"新增类"补丁必然对不上。
5. **整文件必带"必须保留"清单**，并按清单逐项验收。
6. **失败先看现场再重跑**：先翻兜底答案 → 页面文字 → 截图 → DOM，确认真的没救再重来。

> 完整的决策规则与踩坑记录见 [`SKILL.md`](./SKILL.md)。

## 快速开始

```bash
AWA=/path/to/free-web-ai-worker      # 支持 --session 的版本
DASH=<skill>/scripts/dashboard       # 本技能的脚本目录

# 1) 首次外包：让网页 AI 产出完整文件（--session 记住这次对话）
python "$DASH/askw.py" ask -p deepseek --session my-task \
  --file 需求.txt --timeout 180 --no-cache > 结果.json 2> 结果.err
python <skill>/scripts/extract.py 结果.json 目标.html

# 2) 续改：回到同一对话，只让它改一段（省 token）
python "$DASH/askw.py" ask -p deepseek --session my-task \
  --file 需求.txt --timeout 180 --no-cache > 返回.json 2> 返回.err
python <skill>/scripts/apply_patch.py 返回.json 目标.html
```

`askw.py` 是 `bin/ask-web-ai.js` 的等价包装（stdout 原样输出，老命令照旧可用），额外做三件事：
**① 调用中实时看护 ② 结果当场记账入库 ③ 失败自动留现场并兜底提取答案。**

> 不用 `askw.py` 也能跑——直接调 `node "$AWA/bin/ask-web-ai.js"` 即可，只是丢掉记账与看护。

## 看板与数据层

### 一次性配置

```bash
python "$DASH/collect.py" --to-db --tasks "产出目录A,产出目录B"   # 扫描本机 -> SQLite
python "$DASH/render.py"                                          # 从库渲染看板
```

看板效果（「站点与登录态」页签）：

![Web AI 外包看板：站点与登录态](docs/dashboard-overview.png)

离线单文件，四个页签：站点与登录态（含判定证据与今日配额）、历史对话、调用流水（含失败现场截图链接）、本地产出。

### 让它"活"起来

直接双击 `dashboard.html` 只是离线快照。要**手动刷新 / 30 秒自动刷新 / 重新扫描浏览器 / 页面内改配额**，起本地服务：

```bash
python "$DASH/serve.py"        # -> http://127.0.0.1:8787/dashboard.html
```

只监听 `127.0.0.1`；页面工具栏是两组「按钮 + 自动开关」：**刷新页面**（毫秒级，只读库）+ 自动 30s、**重新扫描浏览器 profile**（约 1-2 秒，读 Cookie/登录态/浏览历史）+ 自动 5min。

### 数据怎么流动

```
浏览器 profile ──重新扫描──▶ ┐
                            ├──▶ SQLite 库 web-ai.db ──刷新/自动刷新──▶ 看板
每次外包调用 ──askw 当场写──▶ ┘
```

**调用流水不靠按钮**——`askw.py` 每次调用当场写库，按钮只决定"什么时候画到页面上"。

## 失败现场：先看，别急着重跑

| 现场 | 位置 | 里面有什么 |
| --- | --- | --- |
| 工具原生工件 | `~/.agent-web-ai/profiles/edge/artifacts/<时间>-<provider>/` | `screenshot.png` + `page.html`（完整 DOM）+ `summary.json`（页面可见文字） |
| 归档截图 | `scripts/dashboard/shots/<时间>-<会话>-tool.png` | 看板「调用流水」有「查看失败现场截图」链接 |
| **兜底答案** | `scripts/dashboard/shots/<时间>-<会话>-answer.md` | **工具没取到、但页面已经答完的答案** |

> 实测：Qwen 判超时失败，页面上却躺着 2697 字的完整回答。这类"取件失败"会被自动识别并捞回——**先看有没有 `-answer.md`，再考虑重跑**。

## 会话熔断 + 在线 AI 交接

老对话聊久了网页 AI 会变笨、变慢甚至拒答。派发前自动检查：超 **8 轮 / 6 万字** 即告警。

```bash
python "$DASH/askw.py" compact --session my-task
# → 让在线 AI 自己产出「接手说明」（目标/结论/遗留问题/约束）
# → 存 summaries/my-task-<时间>.md 并入库
# → 把摘要贴在需求开头，用 --session my-task-v2 开新对话
```

**摘要由在线 AI 生成，不是本地拼的**——它比谁都清楚自己刚才在聊什么。

## 版本迭代

| 版本 | 日期 | 内容 |
| --- | --- | --- |
| **v1.0** | 2026-09-24 | 监工工作流：简洁需求派发、验收/返工循环、`--session` 命名对话续聊、「改前/改后」精确替换、整文件抽取 |
| **v1.1** | 2026-09-25 | 离线看板：只读扫描本机 profile，展示站点登录态 / 历史对话 / 调用流水 / 本地产出 |
| **v2.0** | 2026-09-29 | 持久化重构：`data.json` → **SQLite 持久库**；`askw.py` 调用当场记账；本地服务提供刷新 / 自动刷新 / 重新扫描 / 页面内改配额 |
| **v2.1** | 2026-09-29 | 排版优化：按钮与自动开关成组、统计卡 4 列、今日配额按天实时统计（跨天归零） |
| **v2.2** | 2026-09-29 | 失败留现场：调用失败自动归档截图 + 页面文字，看板可直接点开 |
| **v3.0** | 2026-09-29 | **实时看护**（调用中自动点掉拦路弹窗，取代"事后分析再重跑"）；**失败兜底提取**；**会话熔断 + 在线 AI 生成接手说明** |

## 依赖

- **`ask-web-ai`**：`free-web-ai-worker` 的、支持 **`--session` 命名对话** 的版本（下文用 `$AWA` 指代其目录）。
- **Node**（跑上面这个工具 + CDP 截图脚本）、**Python 3**（跑 `scripts/`）。
- 一个**已登录**的网页版 AI（推荐 DeepSeek：支持附件与视觉）。

> **本仓库自带 `ask-web-ai` 快照，拉取即可使用。** 实测审计：它不做更新检查、无遥测、不访问 npm 注册表；运行时只连本机 CDP（`127.0.0.1`）驱动浏览器；浏览器用的是**系统已装的 Edge**（不会下载 Chromium）；唯一 npm 依赖 `playwright-core` 已随快照附带在 `node_modules/`。也就是说 `python scripts/setup.py` 之后**不需要外网、不需要 npm、也不需要上游仓库还在**。唯一必须各自完成的是**登录**（登录态不能分发）。

## 安装

### 1. 拿到 `ask-web-ai`（仓库自带，无需外网）

本 skill 需要一个**支持 `--session` 命名对话**的 `ask-web-ai`，而上游**并未提供**该能力（差异见 `patches/`，80 KB）。为了**不依赖上游是否还在、也不依赖外网与 npm**，本仓库自带一份自包含快照（`vendor/*.zip`，含 `node_modules/`）：

```bash
python scripts/setup.py                      # 解压到 ~/.tools/ 并自检（推荐，该目录会被自动探测）
python scripts/setup.py --dest D:/tools      # 或指定安装目录
python scripts/setup.py --check              # 只自检环境，不写磁盘
```

脚本会校验 Node ≥ 20、Edge 是否已装、入口与 `playwright-core` 是否就位，并打印后续命令。

> 想自己从上游构建（**需要外网，且上游若下线就不可用**）：见 [`patches/README.md`](./patches/README.md)。

### 2. 部署本 skill

把本目录放进你的技能目录，例如 `~/.workbuddy/skills/外包skill/`。

### 3. 登录一次（**每台机器都要做**）

```bash
node <安装目录>/bin/ask-web-ai.js login --provider deepseek
```

登录态落在 `~/.agent-web-ai/`，**里面是你的账号 Cookie，不能随包分发**——所以换机器要重新登录一次，这是唯一无法"拉取即用"的一步。

### 4. 自检整条链路

```bash
python scripts/dashboard/askw.py ask -p deepseek --session smoke --file 需求.txt --timeout 180 --no-cache > 结果.json
```

## 目录结构

```
.
├── SKILL.md                 # 技能说明：监工流程 + 决策规则 + 踩坑
├── README.md                # English（GitHub 落地页）
├── README-zh.md             # 简体中文说明（本文件）
├── LICENSE                  # Apache-2.0
├── NOTICE
├── scripts/
│   ├── setup.py             # 从 vendor/ 快照安装 ask-web-ai + 环境自检
│   ├── extract.py           # 从 AI 返回中抽取「完整文件」
│   ├── apply_patch.py       # 把「改前/改后」片段「精确替换」进本地文件
│   └── dashboard/
│       ├── askw.py          # 外包入口：转发 + 实时看护 + 记账 + 失败留现场
│       ├── store.py         # SQLite 持久层（建表/增量 upsert/组装看板数据/导出 CSV）
│       ├── collect.py       # 扫描本机：站点登录态 / 历史对话 / 产出 -> 增量入库
│       ├── render.py        # 从库渲染离线单文件看板 dashboard.html + checklist.md
│       ├── serve.py         # 本地服务：刷新 / 重新扫描 / 页面内改配额
│       ├── shot.mjs         # 经 CDP 截图（Node 原生 WebSocket，零依赖）
│       ├── cdp-eval.mjs     # 经 CDP 执行任意 JS（处理一次性弹窗等）
│       ├── dismiss-popup.js # 现成的「点掉拦路弹窗」脚本
│       └── make_demo.py     # 生成 examples/dashboard-demo.html（虚构数据）
├── docs/
│   └── dashboard-overview.png  # 看板截图
├── patches/
│   └── free-web-ai-worker-session.patch  # 与上游的差异（自建时的路径）
├── vendor/
│   └── free-web-ai-worker-patched-v0.2.0-*.zip  # 自包含快照（含 node_modules），由 setup.py 安装
└── examples/
    └── dashboard-demo.html  # 示例看板（数据全部虚构，双击即可看效果）
```

看板的运行时产物（`web-ai.db` / `shots/` / `summaries/` / `*.csv`）默认不提交，见 `.gitignore`。

不想先扫描本机也能看效果：直接打开 **[`examples/dashboard-demo.html`](examples/dashboard-demo.html)**，那是一份**数据全部虚构**的示例（页顶带「示例数据 · 全部虚构」标记）。要重新生成：`python scripts/dashboard/make_demo.py`。

## 安全提示

外包内容会经过**第三方站点**（DeepSeek 等）。**涉密材料不要外包。**
本地服务只监听 `127.0.0.1`；登录凭据**只记录长度与指纹，不落明文**。

## 致谢

本项目的**思路**来自开源项目 **[free-web-ai-worker](https://github.com/augustlies/free-web-ai-worker)**（作者 [@augustlies](https://github.com/augustlies)，MIT 协议）——它提出了「让 Agent 把纯文本子任务外包给网页版免费 AI」的做法，并提供了驱动网页版 AI 的 CLI。

本 skill 在此基础上聚焦封装**「监工工作流」**：简洁需求派发、结果验收与返工循环、命名对话续聊（`--session`）、「改前/改后」局部替换，以及后续的看板、持久库、实时看护与失败兜底提取。谨向原作者的探索与分享致谢。

> 本项目为独立项目，与上述原仓库无隶属关系；使用前请自行确认各网页版 AI 站点的服务条款。

## License

[Apache-2.0](./LICENSE) © 2026 ruilin365
