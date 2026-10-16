# skills

我在用的 agent skill，全量同步，方便多台机器保持一致。仓库根即 `~/.agents`，skill 都在 `skills/` 下。

`~/.claude/skills`、`~/.codex/skills` 和 `~/.pi/agent/skills` 里的条目是指向这里的 symlink，所以 Claude Code、Codex 和 Pi 共用同一份实体文件。

配套的工作流写在这里：[把 AI 编程从对话变成流程](https://foxden.vault2049.xyz/tech/agent-workflow/)。

较大更新及更新后的具体用法见 [CHANGELOG.md](CHANGELOG.md)。

## 自建

这三个是我自己写的，其余都是第三方的。

| skill | 作用 |
|---|---|
| `implement-codex` | 实现一个 issue：Claude 钉 spec、选推理档、委派 Codex 写代码、自己验证和复审。改自 Matt Pocock 的 `implement` |
| `accept-issue` | 验收已实现的 issue，必须在新会话里跑：Codex 当法官逐条裁决留证据，Claude 当书记员只查形式 |
| `land-issue` | 收尾已验收的 issue：preflight、push、留摘要、close |

## 第三方

下面 59 个不是我的作品，原样收录只是为了多机同步。版权归各自作者，随各自的许可证分发。要用请去上游仓库，那里才有更新。有上游的一律跟上游走：上游改了就同步，已确认删除或弃用的技能移除旧入口，改名则迁移到新入口。

| 来源 | skill |
|---|---|
| [mattpocock/skills](https://github.com/mattpocock/skills)（27） | `ask-matt` `code-review` `codebase-design` `diagnosing-bugs` `domain-modeling` `grill-me` `grill-with-docs` `grilling` `handoff` `implement` `implement-spec` `improve-codebase-architecture` `pr` `prototype` `research` `retro` `setup-matt-pocock-skills` `tdd` `teach` `to-questionnaire` `to-spec` `to-tickets` `triage` `wait-what` `wayfinder` `wizard` `writing-for-agents` |
| [tw93/Waza](https://github.com/tw93/Waza)（8） | `check` `health` `hunt` `learn` `read` `think` `ui` `write` |
| [tw93/kami](https://github.com/tw93/kami)（1） | `kami` |
| [blader/humanizer](https://github.com/blader/humanizer)（1，MIT） | `humanizer-zh`，歸藏的中文译本 |
| [microsoft/playwright-cli](https://github.com/microsoft/playwright-cli)（1，Apache-2.0） | `playwright-cli`，附 `LICENSE.txt` 和 `NOTICE.txt` |
| [herdrdev/herdr](https://github.com/herdrdev/herdr)（1，Apache-2.0） | `herdr` |
| [Agents365-ai/365-skills](https://github.com/Agents365-ai/365-skills)（1） | `excalidraw-skill` |
| [cloudflare/skills](https://github.com/cloudflare/skills)（19） | `agents-sdk` `basin` `cf-cli` `cloudflare` `cloudflare-email-service` `cloudflare-one` `cloudflare-one-migrations` `durable-objects` `gateway-workers` `k2` `nextjs-on-cloudflare` `sandbox-migrate-to-next` `sandbox-next` `sandbox-stable` `turnstile-spin` `web-perf` `workers-best-practices` `workers-profiling` `wrangler` |

另外保留本机安装的 16 个 `dingtalk-*` 技能，均在 `upstream.json` 的 `untracked` 中登记，由本脚本维护三端软链接，内容不跟随上述上游更新。旧的 `dws` 技能目录已不存在；泛称钉钉操作时用 `dingtalk-shared`，明确产品时用对应的 `dingtalk-*` 技能。迁移示例见 [CHANGELOG.md](CHANGELOG.md)。

## 用法

装、更新、删、软链，全在 `scripts/sync-skills.py` 里，不需要 `npx skills`。

已有安装器生成的 `.skill-lock.json` 仅作本机安装记录，已被 Git 忽略；受管来源及同步范围以 `upstream.json` 为准。不要同时用另一套安装器覆盖已纳管的技能。

离线建链（`--link`）只需要 `python3`，使用标准库。体检、`list`、升级上游和 `add` 还需要已登录的 [`gh` CLI](https://cli.github.com)（macOS 可用 `brew install gh && gh auth login`），脚本靠它访问 GitHub API。

先分清谁动磁盘：

| 命令 | 磁盘 | 做什么 |
|---|---|---|
| `scripts/sync-skills.py` | 只读 | 完整体检；有需要修复的问题就 exit 1 |
| `scripts/sync-skills.py list` | 只读 | 列出本地 skill 的来源和软链现状 |
| `scripts/sync-skills.py --link` | 创建目标目录、维护软链及其恢复副本 | 离线补缺、摘受管断链；不查询上游，不碰 `skills/` 文件 |
| `scripts/sync-skills.py --apply` | 写 `skills/`、软链；必要时改 `upstream.json` | 跟上游；改写整棵时把旧树放进恢复区 |
| `scripts/sync-skills.py --apply --prune` | 上者 + **移出** skill 目录 | 裁掉有 `managed` 归属、上游已删除且工作树干净的 skill；保留恢复副本 |
| `scripts/sync-skills.py add …` | 写 `skills/`、`upstream.json`、软链 | 接入一个新来源 |

### 新机器

```bash
git clone https://github.com/sleepingF0x/skills.git ~/.agents
cd ~/.agents
python3 scripts/sync-skills.py --link
```

克隆得到的是仓库已提交的版本。`--link` 按当前机器的仓库路径和用户主目录建立链接，自动创建 `links` 中配置的缺失目录，不需要 `gh` 或网络。不要把另一台机器的绝对路径软链接直接复制过来。

软链策略在 `upstream.json` 的 `links` 里，各 agent 的 `exclude` 决定哪些 skill 不建链接。只使用部分 agent 时，可以在本机配置中移除不需要的项。新版 Codex 和 Pi 也能直接读取 `~/.agents/skills/`；此处保留各自的链接以兼容现有设置。参考 [OpenAI 的 skill 目录说明](https://learn.chatgpt.com/docs/build-skills)。

### 多台机器同步仓库版本

在更新的机器上先检查改动、提交并推送；其他机器再执行：

```bash
cd ~/.agents
git pull --ff-only
python3 scripts/sync-skills.py --link
```

未提交、未推送和被 Git 忽略的文件不会随仓库同步。拉取遇到本地改动或分叉时，先处理 Git 状态，不要用强制覆盖。`--link` 可重复执行，已有正确链接保持原样。

`git pull` 同步已经确认的仓库版本；`--apply` 则查询并升级到上游版本。想让多台机器保持一致，在一台机器升级、检查并提交推送，再让其他机器拉取即可。

### 定期维护与 Git 同步

本机已在 Codex 中设置每日 09:00（Asia/Taipei）维护：核对远端仓库和所有受管上游，尤其是 Matt 的更新；同步技能，核实并清理弃用入口、过期登记和三端软链接，补充 changelog，验证后提交并推送到 `origin/main`。该定时任务保存在本机 Codex 中，克隆仓库不会自动创建它。

执行顺序为：核对 Git 状态与本地编辑，安全同步远端，体检上游，应用更新和已确认的裁剪，再检查技能加载、软链接与测试。网络失败不等于上游删除，来源未知的目录先确认归属；自建或手工维护内容按清单保留。遇到其他工作的未提交改动、冲突或推送失败时，保留现状并报告阻塞。

只提交本轮维护的文件，恢复副本和安装器缓存不入库；没有变化时不创建空提交。有更新或需要处理的问题时通知，状态未变时保持安静。

### 升级上游：先体检，再应用

```bash
scripts/sync-skills.py            # 只读体检，什么都不动
scripts/sync-skills.py --apply    # 写入上游改动，并修好软链
```

每次同步后检查行为变化。新增或移除技能、调用方式变化、工作流变化、文件约定迁移、依赖或交付要求变化，都要在 [CHANGELOG.md](CHANGELOG.md) 新增有日期的记录，交付前写清：

- 改了什么、影响哪些用法，并标明上游版本或提交。
- 更新后需要准备的输入和依赖、可直接套用的指令或命令、预期产物。
- 旧用法如何迁移，废弃入口如何处理，以及适用的 Codex / Claude / Pi 调用方式。
- 实际验证结果和仍需用户完成的步骤，区分技能文件更新与外部 CLI、运行时的升级。

只有措辞或内部整理的小改动可以合并简述；较大更新不能只写「已同步」或罗列文件名。

不带参数就是完整体检：内容漂移、上游新增或删除、本地缺失、未登记、软链断了/缺了/不该有、目标目录缺失或链接位置被占用，全报出来，**一个字节都不动**。发现需要修复的内容、登记或软链问题就 **exit 1**，可直接挂 cron 或 CI；`only` 外的可选 skill 和不冲突的外部目录只作提示，不影响退出状态。

上游没有的 `__pycache__/` 内文件及 `.pyc`、`.pyo` 文件不计为内容漂移；上游同名文件仍正常比较。这个排除仅影响差异报告：完整基线、安全检查和写入前的 Git 状态保护仍包含缓存。若需要替换的 skill 含本地缓存或其他未提交内容，`--apply` 仍会拒绝覆盖。

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

只读。每个本地 skill 的来源（自建/手工跟标 `不跟上游`，未知标 `未登记`；还有上游已删、被 `only` 排除、登记冲突等）和 Claude / Codex / Pi 软链状态（`✓` 已连 `✗` 缺 `−` 有意排除 `?` agent 目录不在）。末尾列出：上游有、本地还没装的；以及 `only` 外已发现、但不会自动装的可选 skill。

### 装新 skill

```bash
scripts/sync-skills.py add owner/repo                  # 先列出候选
scripts/sync-skills.py add owner/repo foo bar          # 装其中几个
scripts/sync-skills.py add owner/repo --all            # 整个仓库都跟
scripts/sync-skills.py add --ref main owner/repo foo   # 指定 ref（默认 HEAD）
```

`add` 会联网并写入。全仓库扫一遍，**任何含 `SKILL.md` 的目录都是候选**，不预设藏在哪个桶。选好后做三件事：写进 `skills/`、把来源和 `managed` 登记进 `upstream.json`、建好配置中各 agent 的软链。

登记是关键。从此归版本控制管，也从此**每次同步都会被检查**。安装器的做法是拷进 agent 目录，一装进来就漂在版本控制外面。

- 写了具体名字：记一条 `only`，只自动跟这几个；仓库后来增加的其他 skill 仍会列在「`only` 外的远端 skill」，但不自动安装
- `--all`：不记 `only`；以后配置的 `roots` 下**新增的 skill 也会被发现**，`--apply` 装成功后自动追加到 `managed`
- 名字和本地已有的撞车、上游没有这个 skill、或同一 `repo@ref` 已登记过：拒绝并说明原因。来源已有 `only` 就先改 `only`；整仓跟随的来源直接跑 `--apply`

不写 skill 名、也不带 `--all` 时，只列出候选然后退出，不写磁盘。装完自己 `git diff`，再提交。

### 删 skill

```bash
scripts/sync-skills.py --apply --prune    # 同步，并裁剪有归属、上游已删除且干净的 skill
```

每次同步都要处理已确认删除或弃用的 skill：移除有效 `skills/` 目录中的旧入口，清理相关来源登记及 Codex、Claude、Pi 的旧软链接，并在 [CHANGELOG.md](CHANGELOG.md) 写明替代入口或迁移用法。交付前核对三个方面：上游是否明确删除或弃用、是否存在改名或拆分关系、三端是否还残留旧入口或断链。

上游「删掉」一个 skill 往往其实是**改了名**（Waza 把 `design` 改成了 `ui`）。脚本会同时报「上游已删除」和「上游新增」，维护时先核对上游记录；改名或拆分时先接好新入口，再移除旧入口。`--prune` 是单独开关，且**必须配合 `--apply`**；只写 `--prune` 只会提醒，不会删。未处理的「上游已删除」会让体检一直 exit 1。

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

单独执行 `--link` 完全离线，不依赖 `gh`，不检查上游版本，也不改 `skills/` 或来源登记。它只按本地目录和 `links` 创建缺失的 agent 目录、补链接，并隔离本脚本拥有的断链和不该存在的链。正确链接无需重建。

只要链接维护成功就 exit 0；同名占用、不安全 skill、目标路径不是可用目录、外部断链等问题仍 exit 1，并保留冲突内容。与 `--apply` 合用时按在线升级流程执行；不能与 `list` / `add` 合用，`--link --prune` 也必须带 `--apply`。

### 它故意不碰的

- agent 目录里的**实体目录 / 普通文件**（不是软链）：保留。不占所需链接位置（如 Claude 的 `synced/`）时仅提示；同名占用仍报错
- 指向本仓库 `skills/<同名>` 之外的软链（别名、交叉链、仓库外）：保留。有效且不冲突时仅提示；断链或同名占用仍报错。本脚本拥有的精确断链先移到 agent 目录内的 `.sync-skills-recovery/`；若隔离后发现已被并发替换为别的内容，就保留并报出恢复路径
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
