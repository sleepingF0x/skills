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

下面 33 个不是我的作品，原样收录只是为了多机同步。版权归各自作者，随各自的许可证分发。要用请去上游仓库，那里才有更新。

| 来源 | skill |
|---|---|
| [mattpocock/skills](https://github.com/mattpocock/skills)（21） | `ask-matt` `code-review` `codebase-design` `diagnosing-bugs` `domain-modeling` `grill-me` `grill-with-docs` `grilling` `handoff` `implement` `improve-codebase-architecture` `prototype` `research` `setup-matt-pocock-skills` `tdd` `teach` `to-spec` `to-tickets` `triage` `wayfinder` `writing-great-skills` |
| [tw93/Waza](https://github.com/tw93/Waza)（9） | `check` `design` `health` `hunt` `learn` `read` `think` `ui` `write` |
| [tw93/kami](https://github.com/tw93/kami)（1） | `kami` |
| [blader/humanizer](https://github.com/blader/humanizer)（1，MIT） | `humanizer-zh`，歸藏的中文译本 |
| [microsoft/playwright-cli](https://github.com/microsoft/playwright-cli)（1，Apache-2.0） | `playwright` |

`.skill-lock.json` 是 `npx skills` 安装器的状态文件，记录第三方 skill 装自哪里，已清理掉指向早年删除 skill 的死条目。它只覆盖 29 个由安装器装的 skill；三个自建的本来就不归它管，另外四个（`to-spec` `to-tickets` `humanizer-zh` `playwright`）当初没走安装器，所以也不在里面。全量跟踪之后它不再是恢复的必要条件，留着只作参考。

## 新机器怎么装

```bash
git clone https://github.com/sleepingF0x/skills.git ~/.agents

# 把需要的 skill 软链进 Claude Code 和 Codex
for s in implement-codex accept-issue land-issue; do
  ln -sfn ~/.agents/skills/$s ~/.claude/skills/$s
  ln -sfn ~/.agents/skills/$s ~/.codex/skills/$s
done
```

第三方 skill 同理软链，或者用 `npx skills add <source>` 从上游重装一份，那样拿到的是最新版。
