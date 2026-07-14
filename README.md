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

## 同步

```bash
scripts/sync-skills.py                  # 只报告，不动文件（有漂移则 exit 1）
scripts/sync-skills.py --apply --link   # 拉上游改动，顺手修软链
scripts/sync-skills.py --apply --prune  # 连"上游已删"的 skill 一起删
```

不走 `npx skills`。脚本直接向 GitHub 要 git tree，拿每个文件的 blob SHA，跟本地按同样算法算出的 SHA 逐一比对。这样能看见三件事，而安装器只能看见第一件：

- **内容漂了** —— SHA 不同
- **上游新增** —— 上游有、本地没有
- **上游删了或改名了** —— 本地有、上游没有

第三种是安装器的盲区：它只记得"我装过什么"，没有"上游把它删了"这个概念。Waza 在 2026-06-27 把 `design` 改名成 `ui`（理由是它遮蔽了 Claude Code 自带的 `/design`），本地那份旧的就这么多活了六周，还一直在遮蔽。

`upstream.json` 是真相来源：每个 source 声明去哪个仓库、在哪几个根目录下找 skill。**凡是含 `SKILL.md` 的子目录就算一个 skill** —— 所以上游新增和删除都能自动发现，不用在这里手写 skill 名单。上游的目录结构（mattpocock 分了桶、kami 的本体在 `plugins/` 下）也一并封在那里。

`--prune` 是单独的开关，因为上游"删掉"一个 skill 往往其实是改了名，这时该做的是同时删旧的、加新的。这个判断留给人。

所有写入都落在 `skills/` 里，所以 review 就是 `git diff`，回滚就是 `git revert`。

## 新机器怎么装

```bash
git clone https://github.com/sleepingF0x/skills.git ~/.agents
mkdir -p ~/.claude/skills ~/.codex/skills
~/.agents/scripts/sync-skills.py --apply --link
```

软链策略写在 `upstream.json` 的 `links` 里：Claude 拿全部，Codex 除了 `implement-codex` 都拿——那个是让 Claude 委派给 Codex 的，Codex 自己拿到它就成了自己委派自己。

脚本还会盯着一个坑：`npx skills`（1.5.16 起）是直接把 skill **拷贝**进 agent 目录，不再软链。所以 `~/.claude/skills/<name>` 一旦变成实体目录，就说明它漂到版本控制外面去了——脚本会警告，但不会替你动它。
