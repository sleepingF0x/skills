# agent-skills

自建 agent skill 的实体仓库，仓库根即 `~/.agents`。

- `skills/` 下只有**自建** skill 进版本库（见 `.gitignore` 白名单）；其余由 `npx skills` 安装器管理，不跟踪。
- `~/.claude/skills` 与 `~/.codex/skills` 里全是指向这里的 symlink。

## 当前自建 skill

| skill | 装到哪 | 作用 |
|---|---|---|
| `land-issue` | Claude + Codex | 收尾已验收的 issue：preflight → push → 留摘要 → close |
| `accept-issue` | Claude + Codex（必须新会话，不得复用实现会话） | 验收已实现的 issue：verify → 实测行为 → 逐条裁决留证据 → 通过接 land-issue / 不通过退回 |

## 新机器恢复

```bash
git clone <this-repo> ~/.agents-tmp && cp -R ~/.agents-tmp/skills/* ~/.agents/skills/ # 或直接 clone 成 ~/.agents
ln -sfn ~/.agents/skills/land-issue ~/.claude/skills/land-issue
ln -sfn ~/.agents/skills/land-issue ~/.codex/skills/land-issue
ln -sfn ~/.agents/skills/accept-issue ~/.claude/skills/accept-issue
ln -sfn ~/.agents/skills/accept-issue ~/.codex/skills/accept-issue
```

配套工作流见 [spec-flow](https://github.com/sleepingF0x/spec-flow) 的 README。
