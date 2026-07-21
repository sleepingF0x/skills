# skills

我在用的 agent skill，全量同步，方便多台机器保持一致。仓库根即 `~/.agents`，skill 都在 `skills/` 下。

`~/.claude/skills` 和 `~/.codex/skills` 里的条目是指向这里的 symlink，所以 Claude Code 和 Codex 共用同一份实体文件。

配套的工作流写在这里：[把 AI 编程从对话变成流程](https://foxden.vault2049.xyz/tech/agent-workflow/)。

## 自建

这三个是我自己写的，其余都是第三方的。

| skill | 作用 |
|---|---|
| `implement-codex` | 实现一个 issue：Claude 钉 spec、选推理档、委派 Codex 写代码、自己验证和复审。改自 Matt Pocock 的 `implement` |
| `accept-issue` | 验收已实现的 issue，必须在新会话里跑：Codex 当法官逐条裁决留证据，Claude 当书记员只查形式 |
| `land-issue` | 收尾已验收的 issue：preflight、push、留摘要、close |

## 第三方

下面 33 个不是我的作品，原样收录只是为了多机同步。版权归各自作者，随各自的许可证分发。要用请去上游仓库，那里才有更新。有上游的一律跟上游走：上游改了就同步，上游删了就删。

| 来源 | skill |
|---|---|
| [mattpocock/skills](https://github.com/mattpocock/skills)（22） | `ask-matt` `code-review` `codebase-design` `diagnosing-bugs` `domain-modeling` `grill-me` `grill-with-docs` `grilling` `handoff` `implement` `improve-codebase-architecture` `prototype` `research` `resolving-merge-conflicts` `setup-matt-pocock-skills` `tdd` `teach` `to-spec` `to-tickets` `triage` `wayfinder` `writing-great-skills` |
| [tw93/Waza](https://github.com/tw93/Waza)（8） | `check` `health` `hunt` `learn` `read` `think` `ui` `write` |
| [tw93/kami](https://github.com/tw93/kami)（1） | `kami` |
| [blader/humanizer](https://github.com/blader/humanizer)（1，MIT） | `humanizer-zh`，歸藏的中文译本 |
| [microsoft/playwright-cli](https://github.com/microsoft/playwright-cli)（1，Apache-2.0） | `playwright-cli`，附 `LICENSE.txt` 和 `NOTICE.txt` |

## 用法

装、更新、删、软链，全在 `scripts/sync-skills.py` 里，不需要 `npx skills`。

依赖两样：`python3`（只用标准库）和 [`gh` CLI](https://cli.github.com)（`brew install gh && gh auth login`）。脚本靠 `gh` 打 GitHub API，认证和速率限制都由它接管。

### 日常

```bash
scripts/sync-skills.py            # 体检：只报告，什么都不动
scripts/sync-skills.py --apply    # 拉上游改动，并把软链修到位
```

不带参数跑，就是一次完整体检：内容漂了、上游新增了、上游删了、软链断了、该链的没链、哪个 skill 被拷成了实体目录——全报出来，一个字节都不动。**有任何问题 exit 1**，所以可以直接挂进 cron 或 CI。

`--apply` 一定会顺带把软链修到位。这不是顺手，是必须：skill 被删掉、软链却还指着它，那是断链，是坏状态，不是可以留给下一条命令的选项。

### 看有哪些

```bash
scripts/sync-skills.py list       # 列出所有 skill：各自的来源，和软链现状
```

一屏看全：每个本地 skill 归哪个上游（`不跟上游` 的自建和手工跟的会标出原因，本地独有的标 `上游已无`），以及它在 Claude / Codex 两边的软链状态（`✓` 已连 `✗` 缺 `−` 有意排除 `?` agent 目录不在）。来源靠向每个上游要一次 git tree 得出，只看目录结构、不下载文件内容。末尾还会列出上游有、本地还没装的。

### 装新 skill

```bash
scripts/sync-skills.py add tw93/Waza                # 先看看这仓库里有哪些 skill
scripts/sync-skills.py add tw93/Waza check health   # 装其中几个
scripts/sync-skills.py add owner/repo --all         # 整个仓库都跟
```

`add` 全仓库扫一遍，**任何含 `SKILL.md` 的目录都是候选**，不预设它藏在哪个桶里。选好之后它做三件事：写进 `skills/`、把来源登记进 `upstream.json`、建好两边的软链。

登记这一步是关键——从此它归版本控制管，也从此**每次同步都会被检查**。安装器的做法是把文件拷进 agent 目录，那等于一装进来就漂在版本控制外面。

写了具体 skill 名，就记一条 `only`，只跟这几个；`--all` 不记，以后那个仓库**新增的 skill 也会自动被发现**。名字和本地已有的撞车，或者上游根本没这个 skill，它都会拒绝并告诉你实情。

### 删 skill

```bash
scripts/sync-skills.py --apply --prune    # 上游已经删掉的，跟着删
```

上游"删掉"一个 skill 往往其实是**改了名**（Waza 把 `design` 改成了 `ui`），这时该做的是同时删旧的、加新的。所以 `--prune` 是单独的开关，这个判断留给人——脚本会把它同时报成「上游已无」和「上游新增」两条。

手动删一个：`git rm -r skills/<name>`，再从 `upstream.json` 拿掉对应的 source（或从 `only` 里划掉），然后跑一次 `--link`，软链会自己被收走。

### 别的

```bash
scripts/sync-skills.py --link     # 只修软链，不碰文件
```

有两类问题脚本**故意不修**，只警告：agent 目录里出现了实体目录/普通文件（不是软链），或者指向本仓库之外的软链。它们可能装着别处没有的东西，不归脚本删。但它们会**永远让体检失败**——因为那意味着有 skill 漂在版本控制外面。

## 它怎么工作

向 GitHub 要 git tree（一个上游一次调用），拿到每个文件的 **blob SHA 和文件模式**，再拿**本地磁盘上的文件**按 git 同样的算法算 SHA，逐一比对。有差异的文件才去取内容。日常没变化的话，一次同步就是几个 HTTP 请求，一个字节的文件内容都不下载。

mode 必须一起比：blob SHA 只覆盖内容。Waza 有 14 个脚本上游是 `100755`、本地是 `644`，第一版脚本对此完全瞎，一直报"完全一致"。上游若启用了 Git LFS，tree API 拿回来的是**指针文件**而不是内容，脚本会直接报错退出，绝不把假文件写下去。

`upstream.json` 是真相来源：每个 source 声明去哪个仓库、在哪几个根目录下找 skill。**凡是含 `SKILL.md` 的子目录就算一个 skill**——所以上游的新增和删除都能自己浮出来，既不用手写 skill 名单，也不依赖任何"当初安装时记下的状态"。上游的目录结构（mattpocock 分了桶、kami 的本体在 `plugins/` 下）和软链策略（`links`）也都封在那里。

所有写入都落在 `skills/` 里，所以 review 就是 `git diff`，回滚就是 `git revert`。

## 为什么不用 npx skills

差别在**跟谁比**。`npx skills update` 比的是上游的 folder hash 和 **lock 里当初安装时记下的 hash**，从不看磁盘。

| | `npx skills update` | 本脚本 |
|---|---|---|
| 上游内容变了 | 能 | 能 |
| **本地被私改或 fork 了** | **看不见**——lock 记的 hash 还等于上游的，所以报"已是最新" | 能 |
| **上游新增了 skill** | **看不见**——它只遍历 lock 里已有的条目 | 能 |
| 文件模式变了 | 能（它 git clone，clone 会还原 mode） | 能 |
| 上游删了 | 能，但只在交互模式下问一句；`-y` 直接跳过 | `--prune` |
| 上游改名/移动 | 判成"删了"（旧路径没了），点头就误删一个活着的 skill | 报成「上游已无」+「上游新增」，人来判断 |
| 没走安装器装的 skill | 看不见 | 能 |
| 装完落在哪 | 拷进 agent 目录，漂在版本控制外 | 写进仓库，再软链 |

第二行是 `playwright` 那个 fork 能藏住的原因，第三行是 `resolving-merge-conflicts` 一直没被发现的原因。至于 `design`：Waza 在 2026-06-27 把它改名成 `ui`（理由正是它遮蔽了 Claude Code 自带的 `/design`），`npx skills update` 其实**会**提示删除——但只问一句，没人点头它就继续活着，一活六周，一直在遮蔽。

`npx skills` 还剩一个本脚本没有的能力：`find`，在注册表里**搜索**你还不知道的 skill。那是发现问题，不是安装问题——知道了仓库名，`add` 接得住。

## 新机器怎么装

```bash
git clone https://github.com/sleepingF0x/skills.git ~/.agents
mkdir -p ~/.claude/skills ~/.codex/skills
~/.agents/scripts/sync-skills.py --apply
```

软链策略写在 `upstream.json` 的 `links` 里：Claude 拿全部，Codex 除了 `implement-codex` 都拿——那个是让 Claude 委派给 Codex 的，Codex 自己拿到它就成了自己委派自己。
