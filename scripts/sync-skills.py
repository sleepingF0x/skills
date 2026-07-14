#!/usr/bin/env python3
"""把 vendored 的 skill 跟上游对齐，并维护 Claude / Codex 的软链。

不走 `npx skills`。直接向 GitHub 要 git tree，拿每个文件的 blob SHA，和**本地
磁盘上的文件**按同样算法算出的 SHA 逐一比对：

    内容漂了      SHA 不同
    上游新增      上游有、本地没有
    上游删了/改名  本地有、上游没有

关键在"跟谁比"。`npx skills update` 比的是上游 folder hash 和 lock 里当初装的
时候记下的 hash，不看磁盘 —— 所以本地私改或 fork 过的 skill 它报"已是最新"
（playwright 就是这么藏了很久），上游新增的 skill 它也永远遍历不到（它只走
lock 里已有的条目）。它确实能发现上游删除，但只在交互模式下问一句就算完。

所有写入都落在 skills/ 里，所以 review 就是 `git diff`，回滚就是 `git revert`。

    scripts/sync-skills.py                  只报告，不动任何文件（有漂移则 exit 1）
    scripts/sync-skills.py --apply          把上游改动拉进 skills/
    scripts/sync-skills.py --link           重建软链
    scripts/sync-skills.py --apply --link   平时用这个
    scripts/sync-skills.py --apply --prune  连"上游已删"的 skill 一起删掉

--prune 是单独的开关：上游删掉一个 skill，往往是改了名（Waza 把 design 改成
了 ui），这时该做的是同时删旧的、加新的。自动删除的判断留给人。
"""

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
MANIFEST = ROOT / "upstream.json"

BOLD, DIM, RED, GREEN, YELLOW, CYAN, RESET = (
    "\033[1m", "\033[2m", "\033[31m", "\033[32m", "\033[33m", "\033[36m", "\033[0m"
)
if not sys.stdout.isatty():
    BOLD = DIM = RED = GREEN = YELLOW = CYAN = RESET = ""


def gh(path):
    """GET a GitHub API path via the gh CLI (uses its auth)."""
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"{RED}gh api {path} 失败{RESET}\n{r.stderr.strip()}")
    return json.loads(r.stdout)


def blob_sha(path: Path) -> str:
    """The same SHA-1 git computes for a blob, so it can be compared to a tree entry."""
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def fetch_blob(repo: str, sha: str) -> bytes:
    b = gh(f"repos/{repo}/git/blobs/{sha}")
    return base64.b64decode(b["content"])


def local_files(skill_dir: Path) -> dict:
    out = {}
    for dirpath, _, filenames in os.walk(skill_dir):
        for fn in filenames:
            fp = Path(dirpath) / fn
            out[str(fp.relative_to(skill_dir))] = blob_sha(fp)
    return out


def discover(source: dict) -> dict:
    """Map every upstream skill this source owns -> {relpath: blob sha}.

    A directory is a skill iff it sits directly under one of the declared roots
    and holds a SKILL.md. That definition is what makes upstream additions and
    deletions visible without a hand-maintained skill list.
    """
    repo, ref = source["repo"], source.get("ref", "HEAD")
    tree = gh(f"repos/{repo}/git/trees/{ref}?recursive=1")
    if tree.get("truncated"):
        sys.exit(f"{RED}{repo} 的 tree 被截断了，脚本没法保证完整比对{RESET}")

    blobs = {t["path"]: t["sha"] for t in tree["tree"] if t["type"] == "blob"}
    skills = {}
    for root in source["roots"]:
        prefix = f"{root}/" if root else ""
        for path in blobs:
            if not path.startswith(prefix):
                continue
            rest = path[len(prefix):]
            parts = rest.split("/")
            if len(parts) < 2:
                continue
            name = parts[0]
            if f"{prefix}{name}/SKILL.md" not in blobs:
                continue
            skills.setdefault(name, {})["/".join(parts[1:])] = blobs[path]
    return skills


def plan(manifest):
    """Compare every tracked skill against its upstream. Returns (index, report)."""
    index = {}          # skill -> (source, {relpath: sha})
    collisions = []
    for source in manifest["sources"]:
        for name, files in discover(source).items():
            if name in index:
                collisions.append((name, index[name][0]["repo"], source["repo"]))
            index[name] = (source, files)

    untracked = manifest["untracked"]
    local = sorted(p.name for p in SKILLS.iterdir() if p.is_dir())

    drift, added, gone, orphans = [], [], [], []

    for name in local:
        if name in untracked:
            continue
        if name not in index:
            orphans.append(name)
            continue
        source, up = index[name]
        keep = set(source.get("keep", {}).get(name, []))
        loc = local_files(SKILLS / name)
        for rel in sorted(set(up) | set(loc)):
            if rel in keep:
                continue
            u, l = up.get(rel), loc.get(rel)
            if u == l:
                continue
            kind = "新增" if l is None else ("多余" if u is None else "改动")
            drift.append((name, source["repo"], rel, kind, u))

    for name in sorted(index):
        if name not in local:
            added.append((name, index[name][0]["repo"]))

    return index, {
        "collisions": collisions,
        "drift": drift,
        "added": added,
        "orphans": orphans,
        "untracked": untracked,
    }


def apply_changes(index, report, prune):
    changed = 0
    for name, repo, rel, kind, sha in report["drift"]:
        target = SKILLS / name / rel
        if kind == "多余":
            target.unlink()
            print(f"  {RED}删除{RESET} {name}/{rel}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(fetch_blob(repo, sha))
            print(f"  {GREEN}写入{RESET} {name}/{rel}")
        changed += 1

    for name, repo in report["added"]:
        source, files = index[name]
        for rel, sha in sorted(files.items()):
            target = SKILLS / name / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(fetch_blob(repo, sha))
        print(f"  {GREEN}新建{RESET} {name}/  （{len(files)} 个文件，来自 {repo}）")
        changed += 1

    if prune:
        for name in report["orphans"]:
            shutil.rmtree(SKILLS / name)
            print(f"  {RED}删除{RESET} {name}/  （上游已无）")
            changed += 1
    elif report["orphans"]:
        print(f"  {YELLOW}跳过{RESET} {len(report['orphans'])} 个上游已无的 skill —— 要删加 --prune")

    # Empty dirs can survive a file-level delete.
    for d in sorted(SKILLS.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    return changed


def sync_links(manifest):
    wanted_all = sorted(p.name for p in SKILLS.iterdir() if p.is_dir())
    changed = 0
    for agent, cfg in manifest["links"].items():
        d = Path(os.path.expanduser(cfg["dir"]))
        if not d.is_dir():
            print(f"  {YELLOW}跳过{RESET} {agent}：{d} 不存在")
            continue
        wanted = {n for n in wanted_all if n not in cfg["exclude"]}

        for entry in sorted(d.iterdir()):
            if entry.name.startswith("."):
                continue
            if entry.is_symlink():
                dest = Path(os.path.realpath(entry))
                stale = dest.parent != SKILLS or entry.name not in wanted
                if stale or not dest.exists():
                    entry.unlink()
                    why = "断链" if not dest.exists() else "不该在这"
                    print(f"  {RED}移除{RESET} {agent}/{entry.name}  （{why}）")
                    changed += 1
            elif entry.is_dir():
                # npx skills copies rather than symlinks; a real dir here means the
                # skill has drifted outside version control.
                print(f"  {RED}警告{RESET} {agent}/{entry.name} 是实体目录，不是软链 —— "
                      f"它已经漂到版本控制外面了，我不会动它")

        for name in sorted(wanted):
            link = d / name
            if link.is_symlink() and Path(os.path.realpath(link)) == SKILLS / name:
                continue
            if link.exists() and not link.is_symlink():
                continue  # already warned
            link.unlink(missing_ok=True)
            link.symlink_to(SKILLS / name)
            print(f"  {GREEN}软链{RESET} {agent}/{name}")
            changed += 1
    return changed


def show(report):
    r = report
    if r["collisions"]:
        print(f"\n{RED}{BOLD}名字撞车{RESET}  同一个 skill 名出现在多个上游：")
        for name, a, b in r["collisions"]:
            print(f"  {name}: {a} 和 {b}")

    if r["orphans"]:
        print(f"\n{YELLOW}{BOLD}上游已无{RESET}  本地有，上游找不到 —— 多半是上游删了或改了名：")
        for name in r["orphans"]:
            print(f"  {name}")
        print(f"  {DIM}确认过就用 --prune 删掉。改名的话记得上游那个新名字会出现在下面「上游新增」里。{RESET}")

    if r["added"]:
        print(f"\n{CYAN}{BOLD}上游新增{RESET}  上游有，本地没有：")
        for name, repo in r["added"]:
            print(f"  {name}  {DIM}{repo}{RESET}")

    if r["drift"]:
        print(f"\n{BOLD}内容漂移{RESET}  {len(r['drift'])} 个文件：")
        by_skill = {}
        for name, _, rel, kind, _ in r["drift"]:
            by_skill.setdefault(name, []).append((kind, rel))
        for name, items in sorted(by_skill.items()):
            print(f"  {BOLD}{name}{RESET}")
            for kind, rel in sorted(items):
                colour = {"改动": YELLOW, "新增": GREEN, "多余": RED}[kind]
                print(f"    {colour}{kind}{RESET} {rel}")

    if r["untracked"]:
        print(f"\n{DIM}不跟上游（声明在 upstream.json 里）：{RESET}")
        for name, why in r["untracked"].items():
            print(f"  {DIM}{name} —— {why}{RESET}")


def main():
    ap = argparse.ArgumentParser(description="同步上游 skill，维护 Claude / Codex 软链")
    ap.add_argument("--apply", action="store_true", help="把上游改动写进 skills/")
    ap.add_argument("--link", action="store_true", help="重建软链")
    ap.add_argument("--prune", action="store_true", help="连上游已删的 skill 一起删（需配合 --apply）")
    args = ap.parse_args()

    if not shutil.which("gh"):
        sys.exit(f"{RED}需要 gh CLI（brew install gh && gh auth login）{RESET}")

    manifest = json.loads(MANIFEST.read_text())

    print(f"{BOLD}比对上游{RESET}  {DIM}{len(manifest['sources'])} 个仓库{RESET}")
    index, report = plan(manifest)
    show(report)

    dirty = bool(report["drift"] or report["added"] or report["orphans"] or report["collisions"])

    if args.apply:
        if dirty:
            print(f"\n{BOLD}应用{RESET}")
            apply_changes(index, report, args.prune)
        else:
            print(f"\n{GREEN}上游没有变化{RESET}")
    elif dirty:
        print(f"\n{DIM}以上只是报告。加 --apply 才会动文件。{RESET}")
    else:
        print(f"\n{GREEN}和上游完全一致{RESET}")

    if args.link:
        print(f"\n{BOLD}软链{RESET}")
        if sync_links(manifest) == 0:
            print(f"  {GREEN}都对{RESET}")

    if dirty and not args.apply:
        sys.exit(1)


if __name__ == "__main__":
    main()
