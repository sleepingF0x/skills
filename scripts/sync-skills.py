#!/usr/bin/env python3
"""管理 vendored 的 skill：装新的、跟上游对齐、维护 Claude / Codex 的软链。

    scripts/sync-skills.py                    体检：内容漂移 + 软链问题，什么都不动（有问题 exit 1）
    scripts/sync-skills.py --apply            拉上游改动，并把软链修到位
    scripts/sync-skills.py --link             只修软链，不碰文件
    scripts/sync-skills.py --apply --prune    连"上游已删"的 skill 一起删，软链跟着删
    scripts/sync-skills.py list               列出所有 skill：各自的来源，和软链现状
    scripts/sync-skills.py add <owner/repo> [skill...]   装一个新来源的 skill

不走 `npx skills`。直接向 GitHub 要 git tree，拿每个文件的 blob SHA 和 mode，跟
**本地磁盘上的文件**逐一比对。关键在"跟谁比"：`npx skills update` 比的是上游
folder hash 和 lock 里当初装的时候记下的 hash，不看磁盘 —— 所以本地私改或 fork
过的 skill 它报"已是最新"，上游新增的 skill 它也遍历不到（只走 lock 里已有的
条目）。这里没有"当初记下的状态"，每次都拿磁盘上的真实字节去碰上游。

`add` 把新来源写进 upstream.json 并装进 skills/，所以它从此归版本控制管，也从此
每次同步都会被检查 —— 而不是像安装器那样把文件拷进 agent 目录、漂在版本控制外面。

--prune 是单独的开关：上游删掉一个 skill，往往是改了名（Waza 把 design 改成了
ui），这时该做的是同时删旧的、加新的。自动删除的判断留给人。
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

# 差异种类。用符号而不是中文标签 —— 标签是拿来显示的，改文案不该改掉逻辑分支。
CHANGED, ADDED, EXTRA = "changed", "added", "extra"
LABEL = {CHANGED: "改动", ADDED: "新增", EXTRA: "多余"}

LFS_MAGIC = b"version https://git-lfs"

BOLD, DIM, RED, GREEN, YELLOW, CYAN, RESET = (
    "\033[1m", "\033[2m", "\033[31m", "\033[32m", "\033[33m", "\033[36m", "\033[0m"
)
if not sys.stdout.isatty():
    BOLD = DIM = RED = GREEN = YELLOW = CYAN = RESET = ""


def die(msg):
    sys.exit(f"{RED}{msg}{RESET}")


def gh(path):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if r.returncode != 0:
        die(f"gh api {path} 失败\n{r.stderr.strip()}")
    return json.loads(r.stdout)


def blob_sha(data: bytes) -> str:
    """git 给 blob 算的那个 SHA-1，所以能直接和 tree 里的条目比。"""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def local_state(skill_dir: Path) -> dict:
    """{relpath: (sha, mode)}。mode 只区分可执行与否，和 git 的语义对齐。"""
    out = {}
    for dirpath, _, filenames in os.walk(skill_dir):
        for fn in filenames:
            fp = Path(dirpath) / fn
            mode = "100755" if os.access(fp, os.X_OK) else "100644"
            out[str(fp.relative_to(skill_dir))] = (blob_sha(fp.read_bytes()), mode)
    return out


def fetch_blob(repo: str, sha: str, path: str) -> bytes:
    data = base64.b64decode(gh(f"repos/{repo}/git/blobs/{sha}")["content"])
    if data.startswith(LFS_MAGIC):
        die(f"{repo} 的 {path} 是 Git LFS 指针，不是真内容。\n"
            f"tree API 拿不到 LFS 的实体，写下去只会得到一个假文件。这个上游得改用 clone 来跟。")
    return data


def write_blob(target: Path, data: bytes, mode: str):
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    target.chmod(0o755 if mode == "100755" else 0o644)


def fetch_tree(repo: str, ref: str) -> dict:
    tree = gh(f"repos/{repo}/git/trees/{ref}?recursive=1")
    if tree.get("truncated"):
        die(f"{repo} 的 tree 被截断了，没法保证完整比对")
    return tree


def skill_paths(tree: dict, roots) -> dict:
    """{skill 名: 它在上游的目录路径}。含 SKILL.md 的目录就是一个 skill。"""
    paths = {t["path"] for t in tree["tree"] if t["type"] == "blob"}
    found = {}
    for root in roots:
        prefix = f"{root}/" if root else ""
        for p in paths:
            if not p.startswith(prefix):
                continue
            parts = p[len(prefix):].split("/")
            if len(parts) >= 2 and f"{prefix}{parts[0]}/SKILL.md" in paths:
                found[parts[0]] = f"{prefix}{parts[0]}"
    return found


def discover(source: dict) -> dict:
    """{skill 名: {relpath: (sha, mode)}}"""
    repo, ref = source["repo"], source.get("ref", "HEAD")
    tree = fetch_tree(repo, ref)
    only = source.get("only")

    for t in tree["tree"]:
        if t["type"] == "commit":
            print(f"  {YELLOW}注意{RESET} {repo} 有子模块 {t['path']}，脚本不跟子模块内容")

    out = {}
    for name, base in skill_paths(tree, source["roots"]).items():
        if only and name not in only:
            continue
        for t in tree["tree"]:
            if t["type"] == "blob" and t["path"].startswith(f"{base}/"):
                rel = t["path"][len(base) + 1:]
                out.setdefault(name, {})[rel] = (t["sha"], t["mode"])
    return out


# ---------------------------------------------------------------- 比对

def plan(manifest):
    index, collisions = {}, []
    for source in manifest["sources"]:
        for name, files in discover(source).items():
            if name in index:
                collisions.append((name, index[name][0]["repo"], source["repo"]))
            index[name] = (source, files)

    untracked = manifest["untracked"]
    local = sorted(p.name for p in SKILLS.iterdir() if p.is_dir())

    drift, added, gone, missing_keep = [], [], [], []

    for name in local:
        if name in untracked:
            continue
        if name not in index:
            gone.append(name)
            continue
        source, up = index[name]
        keep = source.get("keep", {}).get(name, [])
        loc = local_state(SKILLS / name)

        # keep 的文件上游没有（比如 Apache-2.0 要求随附的 LICENSE / NOTICE）。
        # 它们不参与漂移比对，但它们的"存在"必须被守住 —— 否则一次重建就悄悄丢了。
        for rel in keep:
            if rel not in loc:
                missing_keep.append((name, rel))

        for rel in sorted(set(up) | set(loc)):
            if rel in keep:
                continue
            u, l = up.get(rel), loc.get(rel)
            if u == l:
                continue
            kind = ADDED if l is None else (EXTRA if u is None else CHANGED)
            drift.append((name, source["repo"], rel, kind, u))

    for name in sorted(index):
        if name not in local:
            added.append(name)

    return index, {
        "collisions": collisions,
        "drift": drift,
        "added": added,
        "gone": gone,
        "missing_keep": missing_keep,
        "untracked": untracked,
    }


def apply_changes(index, report, prune):
    changed = 0
    for name, repo, rel, kind, up in report["drift"]:
        target = SKILLS / name / rel
        if kind == EXTRA:
            target.unlink()
            print(f"  {RED}删除{RESET} {name}/{rel}")
        else:
            sha, mode = up
            write_blob(target, fetch_blob(repo, sha, rel), mode)
            print(f"  {GREEN}写入{RESET} {name}/{rel}")
        changed += 1

    for name in report["added"]:
        source, files = index[name]
        repo = source["repo"]
        for rel, (sha, mode) in sorted(files.items()):
            write_blob(SKILLS / name / rel, fetch_blob(repo, sha, rel), mode)
        print(f"  {GREEN}新建{RESET} {name}/  （{len(files)} 个文件，来自 {repo}）")
        for rel in source.get("keep", {}).get(name, []):
            print(f"  {RED}注意{RESET} {name}/{rel} 上游没有，脚本造不出来 —— "
                  f"用 git restore 找回来")
        changed += 1

    if prune:
        for name in report["gone"]:
            shutil.rmtree(SKILLS / name)
            print(f"  {RED}删除{RESET} {name}/  （上游已无）")
            changed += 1
    elif report["gone"]:
        print(f"  {YELLOW}跳过{RESET} {len(report['gone'])} 个上游已无的 skill —— 要删加 --prune")

    for d in sorted(SKILLS.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()) and d.parent != SKILLS:
            d.rmdir()
    return changed


# ---------------------------------------------------------------- 软链

def sync_links(manifest, dry=False):
    """返回 (可修的问题数, 不敢碰的问题数)。"""
    wanted_all = sorted(p.name for p in SKILLS.iterdir() if p.is_dir())
    fixable = blocked = 0

    for agent, cfg in manifest["links"].items():
        d = Path(os.path.expanduser(cfg["dir"]))
        if not d.is_dir():
            print(f"  {YELLOW}跳过{RESET} {agent}：{d} 不存在")
            continue
        wanted = {n for n in wanted_all if n not in cfg["exclude"]}

        for entry in sorted(d.iterdir()):
            if entry.name.startswith("."):
                continue

            if not entry.is_symlink():
                # 实体目录或文件。可能装着别处没有的内容，绝不替用户删。
                what = "实体目录" if entry.is_dir() else "普通文件"
                print(f"  {RED}警告{RESET} {agent}/{entry.name} 是{what}，不是软链 —— "
                      f"它在版本控制外面，我不会动它")
                blocked += 1
                continue

            dest = Path(os.path.realpath(entry))
            if dest.parent != SKILLS:
                # 指向别的地方的软链。不是我建的，不归我删。
                print(f"  {YELLOW}警告{RESET} {agent}/{entry.name} 指向仓库外的 {dest} —— "
                      f"不是这个仓库建的，我不会动它")
                blocked += 1
                continue

            if entry.name not in wanted or not dest.exists():
                why = "断链" if not dest.exists() else "不该在这"
                print(f"  {RED}{'待移除' if dry else '移除'}{RESET} {agent}/{entry.name}  （{why}）")
                if not dry:
                    entry.unlink()
                fixable += 1

        for name in sorted(wanted):
            link = d / name
            if link.is_symlink() and Path(os.path.realpath(link)) == SKILLS / name:
                continue
            if link.exists() or link.is_symlink():
                continue  # 上面已经警告过了
            print(f"  {GREEN}{'待软链' if dry else '软链'}{RESET} {agent}/{name}")
            if not dry:
                link.symlink_to(SKILLS / name)
            fixable += 1

    return fixable, blocked


# ---------------------------------------------------------------- add

def cmd_add(args, manifest):
    repo, ref = args.repo, args.ref
    tree = fetch_tree(repo, ref)

    # 全仓库扫一遍：任何含 SKILL.md 的目录都是候选，不预设它藏在哪。
    blobs = {t["path"] for t in tree["tree"] if t["type"] == "blob"}
    found = {}
    for p in blobs:
        if not p.endswith("/SKILL.md"):
            continue
        base = p[: -len("/SKILL.md")]
        found[base.split("/")[-1]] = base
    if not found:
        die(f"{repo} 里没找到任何 SKILL.md")

    if args.skills:
        unknown = [s for s in args.skills if s not in found]
        if unknown:
            die(f"{repo} 里没有这些 skill：{', '.join(unknown)}\n"
                f"它有的是：{', '.join(sorted(found))}")
        chosen = list(args.skills)
    elif args.all:
        chosen = sorted(found)
    else:
        print(f"\n{BOLD}{repo}{RESET} 里发现 {len(found)} 个 skill：")
        for name in sorted(found):
            print(f"  {name}  {DIM}{found[name]}{RESET}")
        die("挑几个装：写在命令后面（sync-skills.py add %s <skill>...），要全装就加 --all" % repo)

    local = {p.name for p in SKILLS.iterdir() if p.is_dir()}
    clash = [s for s in chosen if s in local]
    if clash:
        die(f"这些名字本地已经有了：{', '.join(clash)}\n"
            f"重名会让同步分不清该跟谁，先改名或删掉旧的。")

    roots = sorted({found[s].rsplit("/", 1)[0] if "/" in found[s] else "" for s in chosen})
    source = {"repo": repo, "ref": ref, "roots": roots}
    if not args.all:
        source["only"] = sorted(chosen)

    print(f"\n{BOLD}要装{RESET}")
    for s in sorted(chosen):
        print(f"  {s}  {DIM}{repo}/{found[s]}{RESET}")
    print(f"  {DIM}roots: {roots or ['(仓库根)']}{RESET}")

    files = discover(source)
    for name in sorted(chosen):
        for rel, (sha, mode) in sorted(files[name].items()):
            write_blob(SKILLS / name / rel, fetch_blob(repo, sha, rel), mode)
        print(f"  {GREEN}新建{RESET} {name}/  （{len(files[name])} 个文件）")

    manifest["sources"].append(source)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"  {GREEN}登记{RESET} upstream.json —— 从此每次同步都会检查它")

    print(f"\n{BOLD}软链{RESET}")
    sync_links(manifest)
    print(f"\n{DIM}装完了。检查一下 git diff，然后提交。{RESET}")


# ---------------------------------------------------------------- list

def cmd_list(manifest):
    # 谁归谁：向每个上游要 tree（只拿目录结构，不下载 blob，便宜），得到 skill→repo。
    origin = {}
    for source in manifest["sources"]:
        for name in discover(source):
            origin.setdefault(name, source["repo"])

    untracked = manifest["untracked"]
    local = sorted(p.name for p in SKILLS.iterdir() if p.is_dir())

    # 每个 agent 目录里，这个 skill 有没有正确软链回来。
    agents = {}
    for agent, cfg in manifest["links"].items():
        d = Path(os.path.expanduser(cfg["dir"]))
        linked = set()
        if d.is_dir():
            for name in local:
                link = d / name
                if link.is_symlink() and Path(os.path.realpath(link)) == SKILLS / name:
                    linked.add(name)
        agents[agent] = (cfg, linked, d.is_dir())

    def link_marks(name):
        marks = []
        for agent, (cfg, linked, exists) in agents.items():
            if name in cfg["exclude"]:
                marks.append(f"{DIM}{agent}−{RESET}")     # 有意排除
            elif not exists:
                marks.append(f"{DIM}{agent}?{RESET}")      # agent 目录不在，没法判断
            elif name in linked:
                marks.append(f"{GREEN}{agent}✓{RESET}")
            else:
                marks.append(f"{RED}{agent}✗{RESET}")      # 该软链却没有
        return "  ".join(marks)

    def source_of(name):
        if name in origin:
            return f"{DIM}{origin[name]}{RESET}"
        if name in untracked:
            return f"{YELLOW}不跟上游{RESET}  {DIM}{untracked[name]}{RESET}"
        return f"{RED}上游已无{RESET}  {DIM}本地有，上游找不到{RESET}"

    width = max((len(n) for n in local), default=0)
    print(f"\n{BOLD}共 {len(local)} 个 skill{RESET}  {DIM}（软链：✓ 已连  ✗ 缺  − 排除  ? agent 不在）{RESET}\n")
    for name in local:
        print(f"  {BOLD}{name.ljust(width)}{RESET}  {link_marks(name)}  {source_of(name)}")

    # 上游有、本地还没装的，也顺带提一句 —— 和同步报告里的「上游新增」对得上。
    ahead = [n for n in sorted(origin) if n not in local]
    if ahead:
        print(f"\n{CYAN}上游还有 {len(ahead)} 个本地没装{RESET}  {DIM}（sync-skills.py --apply 会装）{RESET}")
        for name in ahead:
            print(f"  {name}  {DIM}{origin[name]}{RESET}")


# ---------------------------------------------------------------- 报告

def show(r):
    if r["collisions"]:
        print(f"\n{RED}{BOLD}名字撞车{RESET}  同一个 skill 名出现在多个上游：")
        for name, a, b in r["collisions"]:
            print(f"  {name}: {a} 和 {b}")
        print(f"  {DIM}没法判断该跟谁，所以 --apply 会拒绝执行。在 upstream.json 里用 only 划清。{RESET}")

    if r["missing_keep"]:
        print(f"\n{RED}{BOLD}keep 文件不见了{RESET}  上游没有这些文件，脚本也造不出来：")
        for name, rel in r["missing_keep"]:
            print(f"  {name}/{rel}  {DIM}→ git restore skills/{name}/{rel}{RESET}")

    if r["gone"]:
        print(f"\n{YELLOW}{BOLD}上游已无{RESET}  本地有，上游找不到 —— 多半是上游删了或改了名：")
        for name in r["gone"]:
            print(f"  {name}")
        print(f"  {DIM}确认过就用 --prune 删掉。改名的话，新名字会出现在下面「上游新增」里。{RESET}")

    if r["added"]:
        print(f"\n{CYAN}{BOLD}上游新增{RESET}  上游有，本地没有：")
        for name in r["added"]:
            print(f"  {name}")

    if r["drift"]:
        print(f"\n{BOLD}内容漂移{RESET}  {len(r['drift'])} 个文件：")
        by_skill = {}
        for name, _, rel, kind, _ in r["drift"]:
            by_skill.setdefault(name, []).append((kind, rel))
        for name, items in sorted(by_skill.items()):
            print(f"  {BOLD}{name}{RESET}")
            for kind, rel in sorted(items):
                colour = {CHANGED: YELLOW, ADDED: GREEN, EXTRA: RED}[kind]
                print(f"    {colour}{LABEL[kind]}{RESET} {rel}")

    if r["untracked"]:
        print(f"\n{DIM}不跟上游（声明在 upstream.json 里）：{RESET}")
        for name, why in r["untracked"].items():
            print(f"  {DIM}{name} —— {why}{RESET}")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="装新 skill、跟上游对齐、维护软链")
    ap.add_argument("--apply", action="store_true", help="把上游改动写进 skills/（并顺带修软链）")
    ap.add_argument("--link", action="store_true", help="只修软链")
    ap.add_argument("--prune", action="store_true", help="连上游已删的 skill 一起删（配合 --apply）")

    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list", help="列出所有 skill：来源和软链现状")
    a = sub.add_parser("add", help="装一个新来源的 skill")
    a.add_argument("repo", help="owner/repo")
    a.add_argument("skills", nargs="*", help="要装哪几个；不写就列出来给你看")
    a.add_argument("--all", action="store_true", help="整个仓库都跟（以后它新增的 skill 也会自动发现）")
    a.add_argument("--ref", default="HEAD")

    args = ap.parse_args()

    if not shutil.which("gh"):
        die("需要 gh CLI（brew install gh && gh auth login）")

    manifest = json.loads(MANIFEST.read_text())

    if args.cmd == "list":
        cmd_list(manifest)
        return

    if args.cmd == "add":
        cmd_add(args, manifest)
        return

    if args.prune and not args.apply:
        print(f"{YELLOW}--prune 要配合 --apply 才有效{RESET}")

    print(f"{BOLD}比对上游{RESET}  {DIM}{len(manifest['sources'])} 个仓库{RESET}")
    index, report = plan(manifest)
    show(report)

    blocking = bool(report["collisions"] or report["missing_keep"])
    dirty = bool(report["drift"] or report["added"] or report["gone"]) or blocking

    if args.apply and blocking:
        die("\n先把上面的问题解决掉 —— 撞车和 keep 文件缺失都会让同步做出错误的删除，所以拒绝执行。")

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

    # --apply 一定顺带维护软链：skill 被删掉、软链还指着它，那是坏状态，不是可以
    # 留给下一条命令的选项。
    write_links = args.link or args.apply

    print(f"\n{BOLD}软链{RESET}")
    fixable, blocked = sync_links(manifest, dry=not write_links)
    if not fixable and not blocked:
        print(f"  {GREEN}都对{RESET}")
    elif fixable and not write_links:
        print(f"  {DIM}以上只是报告。加 --link（或 --apply）才会动软链。{RESET}")

    if blocked or (dirty and not args.apply) or (fixable and not write_links):
        sys.exit(1)


if __name__ == "__main__":
    main()
