English | [简体中文](./README-zh.md)

# Outsourcing Skill · Supervisor Mode

> A skill that **outsources the heavy writing (HTML / code / text) to a web-based AI** while the agent acts as a **supervisor**: send a concise requirement, review the result, request concise fixes, and finally integrate and deliver.

```
User ──"outsource"──▶ Supervisor (Agent) ──concise req.──▶ Web AI (DeepSeek…)
                          ▲                                    │
                          │◀──────────── result ───────────────┘
                     review / rework
                          │
                    integrate ──▶ deliver
```

## Highlights

| Highlight | What it means |
| --- | --- |
| **Supervisor mode** | The agent only *distills the requirement, dispatches, reviews, requests rework, integrates*. The heavy generation is done by the web AI — fewer tokens, and the decisions stay with you |
| **Live watchdog** | While a call is running, every 4 seconds it dismisses blocking pop-ups (age gate / welcome layer / cookie consent) and keeps a screenshot. **Not "analyze after it times out and run it again"** — that round could have succeeded |
| **Failure ≠ no answer** | Most web-AI "failures" are actually *pickup failures*: the answer was fully generated on the page, the tool just couldn't read it. The skill extracts and stores it automatically |
| **Local persistent store + offline dashboard** | Calls, daily quota, conversations and artifacts all live in SQLite; the dashboard is a single offline HTML file that only reads and renders — no full rescan each time |
| **Session breaker + hand-over by the web AI itself** | Long threads make web AIs forgetful and slow. Past a threshold it warns you, and one command makes the **web AI write its own hand-over note** for a fresh thread |
| **Zero dependencies** | All scripts are pure standard library (Python) plus Node's built-in `WebSocket` for CDP — no third-party packages |

## What it solves

- Offloads the "typing / coding" compute to a **free web AI**; the main model only **distills requirements, reviews, and decides**, saving time and tokens.
- Prompts stay **deliberately short**: one line of requirement + one line of output spec. All the parsing/wiring is handled by local scripts.

## Core principles

1. **A supervisor makes decisions, not the deliverable**: distill requirement → dispatch → review → request rework → integrate & deliver.
2. **Keep prompts short** — long prompts are an anti-pattern.
3. **Prefer continuing the same conversation** (context helps); **open a new one when it is contaminated or simply too long** (web AIs have no cross-conversation memory — they only see the attachment).
4. **Small edits → "before/after" patches; large edits / additions / refactors / reskins → full file.** Web AIs cannot quote source verbatim, so "addition" patches always fail to anchor.
5. **Every full-file round must carry a "must-keep" checklist**, verified item by item.
6. **On failure, look at the scene before re-running**: fallback answer → page text → screenshot → DOM. Only re-run when it is genuinely dead.

> Full decision rules and pitfalls: [`SKILL.md`](./SKILL.md).

## Quick start

```bash
AWA=/path/to/free-web-ai-worker      # a build that supports --session
DASH=<skill>/scripts/dashboard       # this skill's scripts

# 1) First outsourcing round: let the web AI produce a full file
#    (--session remembers this conversation for later rounds)
python "$DASH/askw.py" ask -p deepseek --session my-task \
  --file requirement.txt --timeout 180 --no-cache > result.json 2> result.err
python <skill>/scripts/extract.py result.json target.html

# 2) Follow-up edit: resume the SAME conversation, change only one part (cheaper)
python "$DASH/askw.py" ask -p deepseek --session my-task \
  --file requirement.txt --timeout 180 --no-cache > reply.json 2> reply.err
python <skill>/scripts/apply_patch.py reply.json target.html
```

`askw.py` is an equivalent wrapper around `bin/ask-web-ai.js` (stdout passed through untouched, so old commands still work) that adds three things: **① live watchdog during the call ② instant bookkeeping into SQLite ③ failure-scene archiving with fallback answer extraction.**

> You can skip `askw.py` and call `node "$AWA/bin/ask-web-ai.js"` directly — you just lose bookkeeping and the watchdog.

## Dashboard & data layer

### One-time setup

```bash
python "$DASH/collect.py" --to-db --tasks "out-dir-A,out-dir-B"   # scan this machine -> SQLite
python "$DASH/render.py"                                          # render the dashboard from the DB
```

Dashboard preview (the "Sites & sign-in state" tab):

![Web AI outsourcing dashboard: sites and sign-in state](docs/dashboard-overview.png)

A single offline file with four tabs: sites & sign-in state (with evidence and today's quota), past conversations, call timeline (with links to failure screenshots), and local artifacts.

### Making it live

Opening `dashboard.html` by double-click gives you a baked snapshot. For **manual refresh / 30-second auto-refresh / rescan the browser / edit quota in the page**, start the local service:

```bash
python "$DASH/serve.py"        # -> http://127.0.0.1:8787/dashboard.html
```

Bound to `127.0.0.1` only. The toolbar holds two groups of "button + auto toggle": **Refresh page** (milliseconds, reads the DB) with auto-30s, and **Rescan browser profile** (~1-2 s, reads cookies / sign-in state / history) with auto-5min.

### How data flows

```
Browser profile ──rescan──▶ ┐
                            ├──▶ SQLite web-ai.db ──refresh / auto-refresh──▶ Dashboard
Each outsourcing call ──────▶ ┘
      (written on the spot by askw.py)
```

**The call log does not depend on any button** — `askw.py` writes each call the moment it happens; buttons only decide *when it gets painted*.

## Failure scene: look first, don't re-run

| Scene | Location | Contents |
| --- | --- | --- |
| Native tool artifacts | `~/.agent-web-ai/profiles/edge/artifacts/<ts>-<provider>/` | `screenshot.png` + `page.html` (full DOM) + `summary.json` (visible page text) |
| Archived screenshot | `scripts/dashboard/shots/<ts>-<session>-tool.png` | Linked from the dashboard's call timeline |
| **Fallback answer** | `scripts/dashboard/shots/<ts>-<session>-answer.md` | **The answer that was already finished on the page but not picked up by the tool** |

> Measured: Qwen was reported as a timeout, yet a complete 2697-character answer was sitting on the page. Such *pickup failures* are detected and extracted automatically — **check for `-answer.md` before re-running**.

## Session breaker + hand-over

Long threads make web AIs forgetful, slow, or outright refusing. Checked before every dispatch: **8 turns or 60k characters** triggers a warning.

```bash
python "$DASH/askw.py" compact --session my-task
# -> the web AI writes its own hand-over note (goal / conclusions / open issues / constraints)
# -> saved to summaries/my-task-<ts>.md and stored in the DB
# -> paste it at the top of the requirement, then continue with --session my-task-v2
```

**The summary is written by the web AI, not assembled locally** — nobody knows what that thread was about better than it does.

## Version history

| Version | Date | Highlights |
| --- | --- | --- |
| **v1.0** | 2026-09-24 | Supervisor workflow: concise dispatch, review/rework loop, named-conversation resume (`--session`), "before/after" surgical replacement, full-file extraction |
| **v1.1** | 2026-09-25 | Offline dashboard: read-only scan of the local profile — sites & sign-in state / conversations / call timeline / artifacts |
| **v2.0** | 2026-09-29 | Persistence rework: `data.json` → **SQLite store**; `askw.py` books every call instantly; local service for refresh / auto-refresh / rescan / in-page quota editing |
| **v2.1** | 2026-09-29 | Layout polish: buttons grouped with their auto toggles, 4-column stat cards, today's quota counted per day (resets at midnight) |
| **v2.2** | 2026-09-29 | Failure scenes: on failure, auto-archive screenshot + visible page text, clickable from the dashboard |
| **v3.0** | 2026-09-29 | **Live watchdog** (dismisses blocking pop-ups mid-call, replacing "analyze later and re-run"); **fallback answer extraction**; **session breaker with web-AI-written hand-over notes** |

## Requirements

- **`ask-web-ai`**: a build of **free-web-ai-worker** that supports **`--session`** (named conversations). Referred to below as `$AWA`.
- **Node** (to run it, plus the CDP screenshot scripts) and **Python 3** (for `scripts/`).
- A **logged-in** web AI account (DeepSeek recommended: supports attachments and vision).

> **A bundled snapshot of `ask-web-ai` ships with this repo — clone and go.** Audited: it performs no update check, has no telemetry, never touches the npm registry; at runtime it only talks to the local CDP endpoint (`127.0.0.1`) to drive the browser; the browser is your **installed Edge** (it never downloads Chromium); and its single npm dependency, `playwright-core`, is included in the snapshot's `node_modules/`. So after `python scripts/setup.py` you need **no internet, no npm, and no upstream repo**. The only thing each machine must do itself is **log in** (sessions can't be redistributed).

## Install

### 1. Get `ask-web-ai` (bundled — no internet needed)

This skill needs an `ask-web-ai` that supports **`--session`** named conversations, which **upstream does not provide** (that is this project's patch, see `patches/`). So that nothing depends on the upstream repo still existing — or on the internet or npm — this repository bundles a **self-contained snapshot** (`vendor/*.zip`, including `node_modules/`):

```bash
python scripts/setup.py                      # extract to ~/.tools/ and self-check (recommended; auto-detected)
python scripts/setup.py --dest D:/tools      # or pick an install dir
python scripts/setup.py --check              # check only, write nothing
```

It verifies Node ≥ 20, that Edge is installed, that the entry point and `playwright-core` are in place, then prints the next commands.

> Prefer building from upstream? (**Requires internet, and breaks if upstream disappears.**) See [`patches/README.md`](./patches/README.md).

### 2. Deploy this skill

Put this directory into your skills folder, e.g. `~/.workbuddy/skills/外包skill/`.

### 3. Log in once (**required on every machine**)

```bash
node <install-dir>/bin/ask-web-ai.js login --provider deepseek
```

The session lives in `~/.agent-web-ai/` and **contains your account cookies — it cannot be distributed with the package**, so a new machine must log in once. This is the only step that cannot be "clone and go".

### 4. Smoke-test the whole chain

```bash
python scripts/dashboard/askw.py ask -p deepseek --session smoke --file requirement.txt --timeout 180 --no-cache > result.json
```

## Repository layout

```
.
├── SKILL.md                 # Supervisor workflow + decision rules + pitfalls
├── README.md                # English (this file)
├── README-zh.md             # 简体中文说明
├── LICENSE                  # Apache-2.0
├── NOTICE
├── scripts/
│   ├── setup.py             # Install ask-web-ai from the vendor/ snapshot + environment self-check
│   ├── extract.py           # Extract a full file from the AI's reply
│   ├── apply_patch.py       # Apply "before/after" snippets as exact replacements
│   └── dashboard/
│       ├── askw.py          # Entry point: forward + live watchdog + bookkeeping + failure scene
│       ├── store.py         # SQLite layer (schema / incremental upsert / dashboard data / CSV export)
│       ├── collect.py       # Scan this machine: sites / conversations / artifacts -> incremental upsert
│       ├── render.py        # Render the offline single-file dashboard.html + checklist.md from the DB
│       ├── serve.py         # Local service: refresh / rescan / in-page quota editing
│       ├── shot.mjs         # Screenshot over CDP (Node built-in WebSocket, zero deps)
│       ├── cdp-eval.mjs     # Evaluate arbitrary JS over CDP (one-off pop-ups, inspection)
│       ├── dismiss-popup.js # Ready-made "dismiss blocking pop-ups" script
│       └── make_demo.py     # Generates examples/dashboard-demo.html (fictional data)
├── docs/
│   └── dashboard-overview.png  # Dashboard screenshot
├── patches/
│   └── free-web-ai-worker-session.patch  # Diff against upstream (the build-it-yourself path)
├── vendor/
│   └── free-web-ai-worker-patched-v0.2.0-*.zip  # Self-contained snapshot (incl. node_modules), installed by setup.py
└── examples/
    └── dashboard-demo.html  # Sample dashboard — all data fictional, just open it
```

Runtime artifacts of the dashboard (`web-ai.db` / `shots/` / `summaries/` / `*.csv`) are not committed — see `.gitignore`.

Want to see it before scanning your own machine? Just open **[`examples/dashboard-demo.html`](examples/dashboard-demo.html)** — a sample dashboard whose data is **entirely fictional** (marked at the top), safe to share. Regenerate it with `python scripts/dashboard/make_demo.py`.

## Security note

Outsourced content passes through a **third-party site** (DeepSeek, etc.). **Do not outsource confidential material.**
The local service binds to `127.0.0.1` only; credentials are recorded as **length + fingerprint only, never in plaintext**.

## Acknowledgements

The **idea** comes from the open-source project **[free-web-ai-worker](https://github.com/augustlies/free-web-ai-worker)** by [@augustlies](https://github.com/augustlies) (MIT) — it pioneered the pattern of "letting an agent outsource plain-text subtasks to a free web AI" and provides the CLI that drives the web AI.

This skill builds on it by packaging a **supervisor workflow**: concise requirement dispatch, review-and-rework loop, named-conversation resume (`--session`), "before/after" surgical replacement — plus the later dashboard, persistent store, live watchdog and failure-scene recovery. Thanks to the original author for the exploration and for sharing it.

> This is an **independent project** and is not affiliated with the repository above. Please review each web AI site's terms of service before use.

## License

[Apache-2.0](./LICENSE)
