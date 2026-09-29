# patches/

> **推荐先试这条**：`python scripts/setup.py` —— 从仓库自带的 `vendor/*.zip` 快照安装
> （含 `node_modules`，**不需要外网、不需要 npm，上游删库也能用**）。
> 下面的补丁是给"想自己从上游源码构建"的人准备的备选路径。

## `free-web-ai-worker-session.patch`

本 skill（见上层 `SKILL.md`）需要一个**支持 `--session` 命名对话**的 `ask-web-ai`。

上游 [free-web-ai-worker](https://github.com/augustlies/free-web-ai-worker) **尚未提供**该能力，
因此本补丁在上游基础上补齐它（并附带少量健壮性修复与附件支持）。

**基线**：上游 **v0.2.0**（快照日期 2026-09-20）。上游后续若有改动，本补丁可能无法干净应用——
这也是仓库自带 `vendor/` 快照的原因。

### 应用

```bash
git clone https://github.com/augustlies/free-web-ai-worker
cd free-web-ai-worker

# 用 git 应用
git apply -p1 /path/to/free-web-ai-worker-session.patch
# 或用 GNU patch
patch -p1 < /path/to/free-web-ai-worker-session.patch

npm install                      # 安装 playwright-core
node bin/ask-web-ai.js --help    # 自检

# 一次性登录，把登录态落盘，之后复用
node bin/ask-web-ai.js login --provider deepseek
```

随后把该目录路径作为 skill 里的 `$AWA` 即可。

### 改了什么

- **`--session <name>` / `--chat-url <url>`** + 对话登记簿（`~/.agent-web-ai/chats.json`），
  让后续调用**回到同一个对话**续聊，无需重传上下文。
- 全局超时预算（浏览器启动 + 导航 + 等答案共用一份）、状态文件原子写、更严格的输入/发送校验。
- **`--attach <path>` 附件上传**；并修复"续聊已有对话时误取上一轮旧答案"的问题。
- 部分 provider 选择器更新（DeepSeek composer 定位、发送后校验等）。

### 许可

上游为 **MIT** 协议；本补丁同样以 MIT 条款提供。使用前请遵守各网页版 AI 站点的服务条款。
