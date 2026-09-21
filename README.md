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

下面 38 个不是我的作品，原样收录只是为了多机同步。版权归各自作者，随各自的许可证分发。要用请去上游仓库，那里才有更新。有上游的一律跟上游走：上游改了就同步，上游删了经确认再删。

| 来源 | skill |
|---|---|
| [mattpocock/skills](https://github.com/mattpocock/skills)（25） | `ask-matt` `code-review` `codebase-design` `diagnosing-bugs` `domain-modeling` `grill-me` `grill-with-docs` `grilling` `handoff` `implement` `improve-codebase-architecture` `prototype` `research` `resolving-merge-conflicts` `setup-matt-pocock-skills` `tdd` `teach` `to-questionnaire` `to-spec` `to-tickets` `triage` `wait-what` `wayfinder` `wizard` `writing-for-agents` |
| [tw93/Waza](https://github.com/tw93/Waza)（8） | `check` `health` `hunt` `learn` `read` `think` `ui` `write` |
| [tw93/kami](https://github.com/tw93/kami)（1） | `kami` |
| [blader/humanizer](https://github.com/blader/humanizer)（1，MIT） | `humanizer-zh`，歸藏的中文译本 |
| [microsoft/playwright-cli](https://github.com/microsoft/playwright-cli)（1，Apache-2.0） | `playwright-cli`，附 `LICENSE.txt` 和 `NOTICE.txt` |
| [herdrdev/herdr](https://github.com/herdrdev/herdr)（1，Apache-2.0） | `herdr` |
| [Agents365-ai/excalidraw-skill](https://github.com/Agents365-ai/excalidraw-skill)（1） | `excalidraw-skill` |

## 用法

装、更新、删、软链，全在 `scripts/sync-skills.py` 里，不需要 `npx skills`。

依赖两样：`python3`（只用标准库）和 [`gh` CLI](https://cli.github.com)（`brew install gh && gh auth login`）。脚本靠 `gh` 打 GitHub API，认证和速率限制都由它接管。

先分清谁动磁盘：

| 命令 | 磁盘 | 做什么 |
|---|---|---|
| `scripts/sync-skills.py` | 只读 | 完整体检；有需要修复的问题就 exit 1 |
| `scripts/sync-skills.py list` | 只读 | 列出本地 skill 的来源和软链现状 |
| `scripts/sync-skills.py --link` | 只改软链 | 补缺、摘断链；不碰 `skills/` 文件 |
| `scripts/sync-skills.py --apply` | 写 `skills/`、软链；必要时改 `upstream.json` | 跟上游；改写整棵时把旧树放进恢复区 |
| `scripts/sync-skills.py --apply --prune` | 上者 + **移出** skill 目录 | 裁掉有 `managed` 归属、上游已删除且工作树干净的 skill；保留恢复副本 |
| `scripts/sync-skills.py add …` | 写 `skills/`、`upstream.json`、软链 | 接入一个新来源 |

### 新机器

```bash
git clone https://github.com/sleepingF0x/skills.git ~/.agents
mkdir -p ~/.claude/skills ~/.codex/skills
# 若还没有：brew install gh && gh auth login
~/.agents/scripts/sync-skills.py --apply
```

`--apply` 会按 `upstream.json` 把缺的装齐，并建好两边软链。软链策略在 `links` 里：Claude 拿全部；Codex 除了 `implement-codex` 都拿。那个是让 Claude 委派给 Codex 的，Codex 自己拿到就成了自己委派自己。

### 日常：先体检，再同步

```bash
scripts/sync-skills.py            # 只读体检，什么都不动
scripts/sync-skills.py --apply    # 写入上游改动，并修好软链
```

不带参数就是完整体检：内容漂移、上游新增或删除、本地缺失、未登记、软链断了/缺了/不该有、agent 目录里被拷成实体目录，全报出来，**一个字节都不动**。发现需要修复的内容、登记或软链问题就 **exit 1**，可直接挂 cron 或 CI；`only` 外的可选 skill 只作提示，不影响退出状态。

`--apply` 会做这些事：

- 把漂移写回 `skills/`（改内容、补缺失文件、删本地多出来的文件）
- 安装「上游新增」和「受管但本地缺失」的 skill
- 本地字节与上游完全一致、只是漏了登记的，补进 `managed`（不改内容）
- **一定**顺带修软链。skill 没了，软链还指着它，是坏状态，不是可选项

它**不会**自动删「上游已删除」的 skill，那要显式加 `--prune`。需要改写的受管目录只要有本地改动、未跟踪文件或忽略文件，`--apply` 就拒绝写入，避免盖掉你的活。

下面这些会**阻断** `--apply`，得先按报告处理：名字撞车、`upstream.json` 登记错误、不安全路径（软链/非普通文件）、`keep` 文件缺失、上游新增与未登记本地目录同名。

### 查看现状

```bash
scripts/sync-skills.py list
```

只读。每个本地 skill 的来源（自建/手工跟标 `不跟上游`，未知标 `未登记`；还有上游已删、被 `only` 排除、登记冲突等）和 Claude / Codex 软链状态（`✓` 已连 `✗` 缺 `−` 有意排除 `?` agent 目录不在）。末尾列出：上游有、本地还没装的；以及 `only` 外已发现、但不会自动装的可选 skill。

### 装新 skill

```bash
scripts/sync-skills.py add owner/repo                  # 先列出候选
scripts/sync-skills.py add owner/repo foo bar          # 装其中几个
scripts/sync-skills.py add owner/repo --all            # 整个仓库都跟
scripts/sync-skills.py add --ref main owner/repo foo   # 指定 ref（默认 HEAD）
```

`add` 会联网并写入。全仓库扫一遍，**任何含 `SKILL.md` 的目录都是候选**，不预设藏在哪个桶。选好后做三件事：写进 `skills/`、把来源和 `managed` 登记进 `upstream.json`、建好两边软链。

登记是关键。从此归版本控制管，也从此**每次同步都会被检查**。安装器的做法是拷进 agent 目录，一装进来就漂在版本控制外面。

- 写了具体名字：记一条 `only`，只自动跟这几个；仓库后来增加的其他 skill 仍会列在「`only` 外的远端 skill」，但不自动安装
- `--all`：不记 `only`；以后配置的 `roots` 下**新增的 skill 也会被发现**，`--apply` 装成功后自动追加到 `managed`
- 名字和本地已有的撞车、上游没有这个 skill、或同一 `repo@ref` 已登记过：拒绝并说明原因。来源已有 `only` 就先改 `only`；整仓跟随的来源直接跑 `--apply`

不写 skill 名、也不带 `--all` 时，只列出候选然后退出，不写磁盘。装完自己 `git diff`，再提交。

### 删 skill

```bash
scripts/sync-skills.py --apply --prune    # 同步，并裁剪有归属、上游已删除且干净的 skill
```

上游「删掉」一个 skill 往往其实是**改了名**（Waza 把 `design` 改成了 `ui`）。脚本会同时报「上游已删除」和「上游新增」，删不删留给人。所以 `--prune` 是单独开关，且**必须配合 `--apply`**；只写 `--prune` 只会提醒你，不会删。未处理的「上游已删除」会让体检一直 exit 1。

`--prune` 只认 `managed` 历史归属。未登记目录只报警、绝不移；受管目录有本地改动、未跟踪、忽略文件，或 Git 隐藏的 `skip-worktree` / `assume-unchanged` 状态，也拒绝。目录会先原子移到 `.sync-skills-recovery/` 再核对完整基线；本次运行不永久删除恢复副本。

更新整棵 skill 和改写 `upstream.json` 时也会把旧版放进同一恢复区，manifest 发布还使用 compare-and-swap，并发保存只会让脚本报冲突，不会被 stale 内存覆盖。这些副本是为了保住编辑器已经打开旧文件后可能晚到的写入；有限次「删除前再检查」无法从 POSIX 文件系统上消除这个窗口。确认不需要恢复时，用 `open .sync-skills-recovery` 在 Finder 里把选定的旧副本移到废纸篓。该目录已被 Git 忽略。

手动卸一个**上游还在**的 skill：

```bash
git rm -r skills/<name>
# 同时从该 source 的 managed 和 only 里拿掉它
# 若该 source 没有 only（整仓跟随），先改成明确的 only 清单，
# 否则下次 --apply 会当「上游新增」装回来
scripts/sync-skills.py --link
```

`managed` 里还挂着、却被 `only` 排除的 skill，不更新也不删除，但会让体检一直失败。要么从 `managed` 拿掉，要么放回 `only`。

### 只修软链

```bash
scripts/sync-skills.py --link
```

不碰 `skills/` 里的文件，只按 `links` 补缺、移除断链和不该存在的链。仍会先跑一遍上游比对并报告；内容有漂移的话照样 exit 1，只是不动那些文件。

### 它故意不碰的

- agent 目录里的**实体目录 / 普通文件**（不是软链）：可能装着别处没有的东西，不删；只要还在，体检就失败
- 指向本仓库 `skills/<同名>` 之外的软链（别名、交叉链、仓库外）：只警告，不删。精确的断链也是先移到 agent 目录内的 `.sync-skills-recovery/`；若隔离后发现已被并发替换为别的内容，就保留并报出恢复路径
- `skills/` 下来源未登记的目录：`--apply` / `--prune` 都不碰；先确认来源并显式登记，本地独有就写进 `upstream.json` 的 `untracked`。`add` 不会覆盖同名目录
- 声明在 `untracked` 里的（自建、手工跟的译本等）：不跟上游
- 工作树不干净、又需要改写或删除的受管目录：拒绝覆盖，也拒绝 `--prune`

## 它怎么工作

向 GitHub 要 git tree（一个上游一次调用），拿到每个文件的 **blob SHA 和文件模式**，再拿**本地磁盘上的文件**按 git 同样的算法算 SHA，逐一比对。无漂移时只查 tree，一个 blob 也不下载；某个 skill 一旦有漂移，则先把它的远端载荷全部取回并组装新树，复核本地基线后再整棵替换。这样断网不会留下半更新状态。

mode 必须一起比：blob SHA 只覆盖内容。Waza 有 14 个脚本上游是 `100755`、本地是 `644`，第一版脚本对此完全瞎，一直报"完全一致"。上游若启用了 Git LFS，tree API 拿回来的是**指针文件**而不是内容，脚本会直接报错退出，绝不把假文件写下去。

`upstream.json` 是真相来源：每个 source 的 `roots` 用来扫描当前上游，`managed` 记录本脚本过去已经接纳的 skill。**凡是含 `SKILL.md` 的子目录就算一个 skill**。当前扫描能发现新增；`managed - 当前扫描` 才能证明删除。来源未知的本地目录不能仅凭“当前已配置仓库里没找到”就判成上游删除。上游目录结构和软链策略（`links`）也都封在这里。

本地一旦出现软链载荷、特殊文件，或受影响 skill 里有未提交/未跟踪/忽略内容，`--apply` 会在写入前拒绝：不跟随软链，也不会悄悄删掉 Git 无法恢复的文件。skill 内容和来源登记只写进 `skills/` 与 `upstream.json`，agent 目录只维护软链。所以内容 review 就是 `git diff`；已提交内容可用 `git revert` 回滚，新 skill 则会作为完整目录出现在 `git status`。

## 为什么不用 npx skills

差别在**跟谁比**。`npx skills update` 比的是上游的 folder hash 和 **lock 里当初安装时记下的 hash**，从不看磁盘。

| | `npx skills update` | 本脚本 |
|---|---|---|
| 上游内容变了 | 能 | 能 |
| **本地被私改或 fork 了** | **看不见**。lock 记的 hash 还等于上游的，所以报"已是最新" | 能 |
| **上游新增了 skill** | **看不见**。它只遍历 lock 里已有的条目 | 能 |
| 文件模式变了 | 能（它 git clone，clone 会还原 mode） | 能 |
| 上游删了 | 能，但只在交互模式下问一句；`-y` 直接跳过 | `--prune` |
| 上游改名/移动 | 判成"删了"（旧路径没了），点头就误删一个活着的 skill | 在配置的 `roots` 内报成「上游已删除」+「上游新增」，人来判断 |
| 没走安装器装的 skill | 看不见 | 能 |
| 装完落在哪 | 拷进 agent 目录，漂在版本控制外 | 写进仓库，再软链 |

第二行是 `playwright` 那个 fork 能藏住的原因，第三行是 `resolving-merge-conflicts` 一直没被发现的原因。至于 `design`：Waza 在 2026-06-27 把它改名成 `ui`（理由正是它遮蔽了 Claude Code 自带的 `/design`），`npx skills update` 其实**会**提示删除，但只问一句，没人点头它就继续活着，一活六周，一直在遮蔽。

`npx skills` 还剩一个本脚本没有的能力：`find`，在注册表里**搜索**你还不知道的 skill。那是发现问题，不是安装问题。知道了仓库名，`add` 接得住。
