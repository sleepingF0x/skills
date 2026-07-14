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
| [microsoft/playwright-cli](https://github.com/microsoft/playwright-cli)（1，Apache-2.0） | `playwright` |

`.skill-lock.json` 是 `npx skills` 安装器的状态文件，记录第三方 skill 装自哪里，已清理掉指向早年删除 skill 的死条目。它覆盖 30 个由安装器装的 skill；三个自建的本来就不归它管，另外三个（`humanizer-zh` `playwright` `resolving-merge-conflicts`）没走安装器，所以也不在里面。全量跟踪之后它不再是恢复的必要条件，留着只作参考。

mattpocock 上游在 2026-07 把 skill 按用途分了桶，路径从 `skills/<name>/` 变成 `skills/<bucket>/<name>/`（`engineering` `productivity` `in-progress` `misc` `personal` `deprecated`）。我这边一律平铺在 `skills/` 下，手动 vendor 时注意换算路径。只跟 `engineering` 和 `productivity` 两个桶。

## 新机器怎么装

```bash
git clone https://github.com/sleepingF0x/skills.git ~/.agents

# Claude Code：三个自建 skill 都要
for s in implement-codex accept-issue land-issue; do
  ln -sfn ~/.agents/skills/$s ~/.claude/skills/$s
done

# Codex：只要验收和收尾两个。implement-codex 是让 Claude 委派给 Codex 的，
# Codex 自己拿到它就成了自己委派自己，所以不链。
for s in accept-issue land-issue; do
  ln -sfn ~/.agents/skills/$s ~/.codex/skills/$s
done
```

第三方 skill 同理软链，或者用 `npx skills add <source>` 从上游重装一份，那样拿到的是最新版。

注意 `npx skills`（1.5.16 起）是直接把 skill **拷贝**进 agent 目录，不再存到 `~/.agents/skills` 再软链。所以每次 `skills add` 之后都要确认 `~/.claude/skills/<name>` 还是软链：变成实体目录就说明这个 skill 漂到版本控制外面去了，得挪回 `~/.agents/skills` 再软链回来。
