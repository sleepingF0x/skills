#!/usr/bin/env python3
"""管理 vendored 的 skill：装新的、跟上游对齐、维护 Claude / Codex 的软链。

    scripts/sync-skills.py                    体检：内容漂移 + 软链问题，什么都不动（有问题 exit 1）
    scripts/sync-skills.py --apply            拉上游改动，并把软链修到位
    scripts/sync-skills.py --link             离线建链/修链，创建缺失的 agent 目录
    scripts/sync-skills.py --apply --prune    移出有归属记录、且上游已删的干净 skill
    scripts/sync-skills.py list               列出所有 skill：各自的来源，和软链现状
    scripts/sync-skills.py add <owner/repo> [skill...]   装一个新来源的 skill

不走 `npx skills`。直接向 GitHub 要 git tree，拿每个文件的 blob SHA 和 mode，跟
**本地磁盘上的文件**逐一比对。关键在"跟谁比"：`npx skills update` 比的是上游
folder hash 和 lock 里当初装的时候记下的 hash，不看磁盘 —— 所以本地私改或 fork
过的 skill 它报"已是最新"，上游新增的 skill 它也遍历不到（只走 lock 里已有的
条目）。这里的 managed 只记归属，不缓存内容；内容每次都拿磁盘上的真实字节碰上游。

`add` 把新来源写进 upstream.json 并装进 skills/，所以它从此归版本控制管，也从此
每次同步都会被检查 —— 而不是像安装器那样把文件拷进 agent 目录、漂在版本控制外面。

每个 source 的 managed 是本脚本自己的历史归属记录。当前上游 tree 只能说明
"现在有什么"；只有 managed 里曾经有、当前 tree 已没有的 skill，才算上游删除。
未登记的本地目录只报告，永远不会被 --prune 删除。

--prune 是单独的开关：上游删掉一个 skill，往往是改了名（Waza 把 design 改成了
ui），这时该做的是同时删旧的、加新的。自动删除的判断留给人；目录有本地改动、
未跟踪文件或忽略文件时也会拒绝。旧树会移到可恢复目录，本次运行不永久删除。
"""

import argparse
import base64
import ctypes
import errno
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

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


def require_skills_root():
    """skills/ 本身必须是实体目录，否则所有子路径检查都没有边界。"""
    if SKILLS.is_symlink():
        die(f"拒绝使用软链 skills 根目录：{SKILLS}")
    try:
        mode = SKILLS.lstat().st_mode
    except FileNotFoundError:
        die(f"skills 根目录不存在：{SKILLS}")
    if not stat.S_ISDIR(mode):
        die(f"skills 根路径不是实体目录：{SKILLS}")


def rename_noreplace(source: Path, target: Path):
    """原子 rename，但目标已存在时绝不覆盖。

    Python/POSIX 的 os.rename 会覆盖刚在检查后出现的同名空目录，标准库又
    没有暴露 no-replace flag。macOS 和 Linux 都有对应内核原语；不支持的
    平台宁可拒绝写入，也不退回有竞态的 exists()+rename。
    """
    libc = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    target_bytes = os.fsencode(target)

    if sys.platform == "darwin":
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        args = (source_bytes, target_bytes, 0x00000004)  # RENAME_EXCL
    elif sys.platform.startswith("linux"):
        try:
            rename = libc.renameat2
        except AttributeError:
            die("当前 Linux libc 没有 renameat2，无法安全执行原子发布")
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        args = (-100, source_bytes, -100, target_bytes, 1)  # AT_FDCWD, RENAME_NOREPLACE
    else:
        die(f"{sys.platform} 没有已实现的原子 no-replace rename，拒绝写入")

    ctypes.set_errno(0)
    if rename(*args) == 0:
        return
    error = ctypes.get_errno()
    if error == errno.EEXIST:
        raise FileExistsError(error, os.strerror(error), str(target))
    die(f"无法把 {source} 安全移到 {target}：{os.strerror(error)}")


def gh(path):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if r.returncode != 0:
        die(f"gh api {path} 失败\n{r.stderr.strip()}")
    return json.loads(r.stdout)


def blob_sha(data: bytes) -> str:
    """git 给 blob 算的那个 SHA-1，所以能直接和 tree 里的条目比。"""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def valid_skill_name(name: str) -> bool:
    return bool(name) and name not in {".", ".."} and "/" not in name and not name.startswith(".")


def safe_relpath(rel: str) -> PurePosixPath:
    """把上游 tree 的路径限定在一个 skill 内。

    GitHub 正常不会给出 ..，但“远端数据永远不能选中仓库外路径”是写入端
    必须自己守住的不变量，不应依赖上游恰好正常。
    """
    path = PurePosixPath(rel)
    if (path.is_absolute() or not path.parts
            or any(part in {"", ".", ".."} or part.casefold() == ".git" for part in path.parts)):
        die(f"上游含不安全的 skill 路径：{rel!r}")
    return path


def local_tree_issue(skill_dir: Path):
    """返回不安全的本地树原因；实体目录+普通文件才能受管。"""
    if skill_dir.is_symlink():
        return "skill 根目录是软链"
    if not skill_dir.is_dir():
        return "skill 根路径不是实体目录"

    for dirpath, dirnames, filenames in os.walk(skill_dir, followlinks=False):
        base = Path(dirpath)
        git_names = [name for name in dirnames + filenames if name.casefold() == ".git"]
        if git_names:
            return f"{(base / git_names[0]).relative_to(skill_dir)} 是嵌套 Git 元数据"
        for name in dirnames + filenames:
            path = base / name
            rel = path.relative_to(skill_dir)
            try:
                mode = path.lstat().st_mode
            except FileNotFoundError:
                return f"{rel} 在检查期间发生变化"
            if stat.S_ISLNK(mode):
                return f"{rel} 是软链"
            if name in dirnames and not stat.S_ISDIR(mode):
                return f"{rel} 不是普通目录"
            if name in filenames and not stat.S_ISREG(mode):
                return f"{rel} 不是普通文件"
    return None


def local_state(skill_dir: Path) -> dict:
    """{relpath: (sha, mode)}。拒绝软链；mode 只区分可执行与否。"""
    issue = local_tree_issue(skill_dir)
    if issue:
        raise ValueError(issue)
    out = {}
    for dirpath, _, filenames in os.walk(skill_dir):
        for fn in filenames:
            fp = Path(dirpath) / fn
            mode = "100755" if fp.lstat().st_mode & 0o111 else "100644"
            out[str(fp.relative_to(skill_dir))] = (blob_sha(fp.read_bytes()), mode)
    return out


def is_runtime_cache(rel: str) -> bool:
    """仅用于上游差异报告；完整基线与写入保护仍包含这些文件。"""
    path = PurePosixPath(rel)
    return "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}


def fetch_blob(repo: str, sha: str, path: str) -> bytes:
    data = base64.b64decode(gh(f"repos/{repo}/git/blobs/{sha}")["content"])
    if blob_sha(data) != sha:
        die(f"{repo} 的 {path} 内容与 tree blob {sha} 不匹配，拒绝写入")
    if data.startswith(LFS_MAGIC):
        die(f"{repo} 的 {path} 是 Git LFS 指针，不是真内容。\n"
            f"tree API 拿不到 LFS 的实体，写下去只会得到一个假文件。这个上游得改用 clone 来跟。")
    return data


def write_blob(target: Path, data: bytes, mode: str, root: Path):
    """在已知根目录内写普通文件；不跟随中间软链，叶子用原子替换。"""
    if mode not in {"100644", "100755"}:
        die(f"不支持的 Git 文件模式：{mode}")
    try:
        parts = target.relative_to(root).parts
    except ValueError:
        die(f"拒绝写入根目录外：{target}")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        die(f"拒绝写入不安全路径：{target}")
    if root.is_symlink() or not root.is_dir():
        die(f"拒绝写入非实体根目录：{root}")

    current = root
    for part in parts[:-1]:
        current = current / part
        if current.is_symlink():
            die(f"拒绝跟随软链目录：{current}")
        if current.exists():
            if not current.is_dir():
                die(f"拒绝穿过非目录路径：{current}")
        else:
            current.mkdir()

    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        tmp.chmod(0o755 if mode == "100755" else 0o644)
        # os.replace 替换软链本身，不会沿叶子软链写到外面。
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def manifest_bytes(manifest) -> bytes:
    return (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode()


def save_manifest(manifest, expected: bytes):
    """用 compare-and-swap 发布 manifest；并发编辑永远不被 stale 内存覆盖。"""
    try:
        current = MANIFEST.read_bytes()
        mode = MANIFEST.lstat().st_mode & 0o777
    except FileNotFoundError:
        die(f"{MANIFEST} 在同步期间不见了，拒绝覆盖")
    if current != expected:
        die(f"{MANIFEST.name} 在同步期间被另一个进程修改，拒绝覆盖")

    fd, tmp_name = tempfile.mkstemp(prefix=f".{MANIFEST.name}.", dir=MANIFEST.parent)
    tmp = Path(tmp_name)
    recovery = new_recovery_path(MANIFEST.name, "manifest")
    published = False
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(manifest_bytes(manifest))
        tmp.chmod(mode)

        rename_noreplace(MANIFEST, recovery)
        if recovery.read_bytes() != expected:
            # 恢复也必须 no-clobber；否则另一个保存恰好重建 canonical
            # 名称时，覆盖式 rename 反而会把新版本抹掉。
            try:
                os.link(recovery, MANIFEST)
            except FileExistsError:
                pass
            die(f"{MANIFEST.name} 在同步期间被修改，拒绝覆盖；"
                f"旧 inode 版本保留在 {recovery}")
        try:
            os.link(tmp, MANIFEST)  # 目标已存在就失败，绝不覆盖并发保存。
            published = True
            print(f"  {DIM}恢复副本{RESET} {recovery}")
        except FileExistsError:
            die(f"{MANIFEST.name} 在同步期间被重新创建，拒绝覆盖；"
                "本次登记可在下次 --apply 重建")
    except BaseException:
        if recovery.exists():
            try:
                os.link(recovery, MANIFEST)
            except FileExistsError:
                pass
        raise
    finally:
        if published or MANIFEST.exists():
            tmp.unlink(missing_ok=True)


def fetch_tree(repo: str, ref: str) -> dict:
    tree = gh(f"repos/{repo}/git/trees/{ref}?recursive=1")
    if tree.get("truncated"):
        die(f"{repo} 的 tree 被截断了，没法保证完整比对")
    return tree


def skill_paths(tree: dict, roots) -> dict:
    """{skill 名: 它在上游的目录路径}。含 SKILL.md 的目录就是一个 skill。"""
    paths = {t["path"] for t in tree["tree"] if t["type"] == "blob"}
    candidates = {}
    for root in roots:
        prefix = f"{root}/" if root else ""
        for p in paths:
            if not p.startswith(prefix):
                continue
            parts = p[len(prefix):].split("/")
            if len(parts) >= 2 and f"{prefix}{parts[0]}/SKILL.md" in paths:
                if not valid_skill_name(parts[0]):
                    die(f"上游含不安全的 skill 名称：{parts[0]!r}")
                candidates.setdefault(parts[0], set()).add(f"{prefix}{parts[0]}")
    duplicates = {name: bases for name, bases in candidates.items() if len(bases) > 1}
    if duplicates:
        details = "；".join(
            f"{name}: {', '.join(sorted(bases))}" for name, bases in sorted(duplicates.items())
        )
        die(f"同一 source 内出现同名 skill，无法判定跟哪个：{details}")
    return {name: next(iter(bases)) for name, bases in candidates.items()}


def discover(source: dict, include_filtered=False) -> dict:
    """{skill 名: {relpath: (sha, mode)}}"""
    repo, ref = source["repo"], source.get("ref", "HEAD")
    tree = fetch_tree(repo, ref)
    only = None if include_filtered else source.get("only")

    for t in tree["tree"]:
        if t["type"] == "commit":
            print(f"  {YELLOW}注意{RESET} {repo} 有子模块 {t['path']}，脚本不跟子模块内容")

    out = {}
    for name, base in skill_paths(tree, source["roots"]).items():
        if only is not None and name not in only:
            continue
        for t in tree["tree"]:
            if t["type"] == "blob" and t["path"].startswith(f"{base}/"):
                rel = t["path"][len(base) + 1:]
                safe_relpath(rel)
                if t["mode"] not in {"100644", "100755"}:
                    die(f"{repo} 的 {t['path']} 模式是 {t['mode']}，"
                        "脚本不会把软链或特殊文件写进 skill")
                out.setdefault(name, {})[rel] = (t["sha"], t["mode"])
    return out


# ---------------------------------------------------------------- 比对

def plan(manifest):
    require_skills_root()
    index, collisions, manifest_errors = {}, [], []
    remote_owner, managed_owner, source_states = {}, {}, []
    collision_keys = set()

    def add_collision(name, a, b):
        key = (name, a["repo"], b["repo"])
        reverse = (name, b["repo"], a["repo"])
        if key not in collision_keys and reverse not in collision_keys:
            collisions.append(key)
            collision_keys.add(key)

    for source in manifest["sources"]:
        all_remote = discover(source, include_filtered=True)
        if "only" in source:
            selected = {name: all_remote[name] for name in source["only"] if name in all_remote}
        else:
            selected = all_remote

        raw_managed = source.get("managed")
        if not isinstance(raw_managed, list) or any(not isinstance(n, str) for n in raw_managed):
            manifest_errors.append(f"{source['repo']} 缺少合法的 managed 列表")
            managed = set()
        else:
            managed = set(raw_managed)
            if len(managed) != len(raw_managed):
                manifest_errors.append(f"{source['repo']} 的 managed 有重复名称")
            for name in managed:
                if not valid_skill_name(name):
                    manifest_errors.append(f"{source['repo']} 的 managed 含非法名称：{name!r}")

        source_states.append((source, all_remote, selected, managed))

        for name, files in selected.items():
            if name in remote_owner and remote_owner[name] is not source:
                add_collision(name, remote_owner[name], source)
            else:
                remote_owner[name] = source
            index[name] = (source, files)

        for name in managed:
            if name in managed_owner and managed_owner[name] is not source:
                add_collision(name, managed_owner[name], source)
            else:
                managed_owner[name] = source

    for name in sorted(set(remote_owner) & set(managed_owner)):
        if remote_owner[name] is not managed_owner[name]:
            add_collision(name, managed_owner[name], remote_owner[name])

    untracked = manifest["untracked"]
    entries = {p.name: p for p in SKILLS.iterdir() if not p.name.startswith(".")}
    local, unsafe, unsafe_names = set(), [], set()

    def add_unsafe(name, reason):
        if name not in unsafe_names:
            unsafe.append((name, reason))
            unsafe_names.add(name)

    for name, path in sorted(entries.items()):
        if path.is_symlink():
            add_unsafe(name, "skills/ 下的 skill 根路径是软链")
        elif path.is_dir():
            local.add(name)
        else:
            add_unsafe(name, "skills/ 下的顶层项不是目录")

    drift, added, missing, gone, missing_keep = [], [], [], [], []
    gone_baseline = {}
    unregistered, adoption_conflicts, adoptable = [], [], []
    filtered, optional = [], []

    for name in sorted(set(untracked) & set(managed_owner)):
        manifest_errors.append(f"{name} 同时声明为 managed 和 untracked")

    for source, all_remote, selected, managed in source_states:
        repo = source["repo"]

        # only 是“不自动安装”，不是“让用户永远看不见”。
        for name in sorted(set(all_remote) - set(selected) - managed):
            optional.append((name, repo))

        for name in sorted(managed):
            if name not in all_remote:
                if name in local:
                    issue = local_tree_issue(SKILLS / name)
                    if issue:
                        add_unsafe(name, issue)
                    else:
                        gone_baseline[name] = local_state(SKILLS / name)
                gone.append((name, source))
                continue
            if name not in selected:
                filtered.append((name, repo))
                continue
            if remote_owner.get(name) is not source or managed_owner.get(name) is not source:
                continue  # 名字撞车会在 apply 前整体阻断。
            keep = source.get("keep", {}).get(name, [])
            if name not in local:
                for rel in keep:
                    missing_keep.append((name, rel))
                missing.append(name)
                continue

            up = selected[name]
            issue = local_tree_issue(SKILLS / name)
            if issue:
                add_unsafe(name, issue)
                continue
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
                if u is None and is_runtime_cache(rel):
                    continue  # 上游自带的同名文件仍需比较，缓存也不从基线删除。
                if u == l:
                    continue
                kind = ADDED if l is None else (EXTRA if u is None else CHANGED)
                drift.append((name, repo, rel, kind, u))

        for name in sorted(set(selected) - managed):
            if remote_owner.get(name) is not source:
                continue
            keep = source.get("keep", {}).get(name, [])
            if name in untracked:
                adoption_conflicts.append((name, repo))
                continue
            if name in entries:
                if name not in local:
                    adoption_conflicts.append((name, repo))
                    continue
                issue = local_tree_issue(SKILLS / name)
                if issue:
                    add_unsafe(name, issue)
                    continue
                loc = local_state(SKILLS / name)
                for rel in keep:
                    if rel not in loc:
                        missing_keep.append((name, rel))
                comparable = {rel: state for rel, state in loc.items() if rel not in keep}
                if comparable == selected[name] and all(rel in loc for rel in keep):
                    # 字节完全相同说明可能只在上次保存 manifest 前中断，
                    # 可安全补登记；任何不一致仍然视为用户目录撞车。
                    adoptable.append((name, source))
                else:
                    adoption_conflicts.append((name, repo))
                continue
            for rel in keep:
                missing_keep.append((name, rel))
            added.append(name)

    reserved = set(managed_owner) | set(remote_owner)
    for name in sorted(local):
        if name not in untracked and name not in reserved:
            unregistered.append(name)

    return index, {
        "collisions": collisions,
        "manifest_errors": manifest_errors,
        "drift": drift,
        "added": added,
        "missing": missing,
        "gone": gone,
        "missing_keep": missing_keep,
        "unsafe": unsafe,
        "unregistered": unregistered,
        "adoption_conflicts": adoption_conflicts,
        "adoptable": adoptable,
        "filtered": filtered,
        "optional": optional,
        "gone_baseline": gone_baseline,
        "baseline": {
            name: local_state(SKILLS / name)
            for name in sorted({item[0] for item in drift})
        },
        "untracked": untracked,
    }


def prune_blocker(name: str):
    """返回拒绝删除的原因；None 表示目标缺失或可由 Git 完整恢复。"""
    target = SKILLS / name
    if not target.exists() and not target.is_symlink():
        return None
    if target.is_symlink():
        return "目标是软链，不是受管实体目录"
    if not target.is_dir():
        return "目标不是目录"
    issue = local_tree_issue(target)
    if issue:
        return f"目录树不安全：{issue}"

    try:
        rel = target.relative_to(ROOT)
    except ValueError:
        return "目标不在仓库根目录内"

    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", str(rel)],
        cwd=ROOT,
        capture_output=True,
    )
    if tracked.returncode != 0:
        return f"无法确认 Git 跟踪状态：{tracked.stderr.decode(errors='replace').strip()}"
    if not tracked.stdout:
        return "目录没有 Git 跟踪文件，无法保证可恢复"

    flags = subprocess.run(
        ["git", "ls-files", "-v", "--", str(rel)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if flags.returncode != 0:
        return f"无法确认 Git index 标志：{flags.stderr.strip()}"
    hidden = [line for line in flags.stdout.splitlines() if line[:1] != "H"]
    if hidden:
        return "目录含 assume-unchanged 或 skip-worktree 文件，无法证明本地内容可恢复"

    status = subprocess.run(
        [
            "git", "status", "--porcelain=v1", "--untracked-files=all",
            "--ignored=matching", "--", str(rel),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if status.returncode != 0:
        return f"无法确认工作树状态：{status.stderr.strip()}"
    if status.stdout.strip():
        preview = "；".join(status.stdout.strip().splitlines()[:3])
        return f"目录含本地改动、未跟踪或忽略文件：{preview}"
    return None


def git_worktree_issue(name: str):
    """普通 --apply 的保护：受管目录内有任何本地状态就不自动覆盖/删除。"""
    target = SKILLS / name
    try:
        rel = target.relative_to(ROOT)
    except ValueError:
        return "目标不在仓库根目录内"

    flags = subprocess.run(
        ["git", "ls-files", "-v", "--", str(rel)], cwd=ROOT, capture_output=True, text=True
    )
    if flags.returncode != 0:
        return f"无法确认 Git index 标志：{flags.stderr.strip()}"
    if any(line[:1] != "H" for line in flags.stdout.splitlines()):
        return "含 assume-unchanged 或 skip-worktree 文件"

    status = subprocess.run(
        [
            "git", "status", "--porcelain=v1", "--untracked-files=all",
            "--ignored=matching", "--", str(rel),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if status.returncode != 0:
        return f"无法确认工作树状态：{status.stderr.strip()}"
    if status.stdout.strip():
        preview = "；".join(status.stdout.strip().splitlines()[:3])
        return f"含本地改动、未跟踪或忽略文件：{preview}"
    return None


def fetch_skill_payload(repo: str, files: dict) -> dict:
    """先把一个 skill 全部取回内存；网络失败时最终目录一个字节都不动。"""
    return {
        rel: (fetch_blob(repo, sha, rel), mode)
        for rel, (sha, mode) in sorted(files.items())
    }


def build_skill_tree(staging: Path, payload: dict):
    """把已全部下载的载荷写成一棵新目录。"""
    for rel, (data, mode) in payload.items():
        safe_relpath(rel)
        write_blob(staging.joinpath(*PurePosixPath(rel).parts), data, mode, staging)


def new_recovery_path(name: str, operation: str) -> Path:
    """在 skills/ 同文件系统内分配可恢复隔离路径；本次运行不会永久删除它。"""
    recovery = SKILLS.parent / ".sync-skills-recovery"
    if recovery.is_symlink():
        die(f"拒绝使用软链恢复目录：{recovery}")
    if recovery.exists():
        if not stat.S_ISDIR(recovery.lstat().st_mode):
            die(f"恢复路径不是实体目录：{recovery}")
    else:
        recovery.mkdir(mode=0o700)
    reserved = Path(tempfile.mkdtemp(prefix=f"{name}.{operation}.", dir=recovery))
    reserved.rmdir()
    return reserved


def swap_skill_tree(name: str, staging: Path, expected_state):
    """
    在一次原子 rename 前复核本地基线，然后把旧目录移到备份位置。

    若第二次 rename 失败，立即把备份恢复；所以既不会留下多文件半更新，
    也不会覆盖预检后才出现的用户修改。
    """
    target = SKILLS / name
    if expected_state is None:
        if target.exists() or target.is_symlink():
            die(f"安装期间目标路径已被创建，拒绝覆盖：{target}")
        try:
            rename_noreplace(staging, target)
        except FileExistsError:
            die(f"安装期间目标路径已被创建，拒绝覆盖：{target}")
        return

    issue = local_tree_issue(target)
    if issue:
        die(f"拒绝更新 {name}：{issue}")
    if local_state(target) != expected_state:
        die(f"拒绝更新 {name}：本地内容在比对后发生了变化")
    reason = git_worktree_issue(name)
    if reason:
        die(f"拒绝更新 {name}：{reason}")

    backup = new_recovery_path(name, "update")
    rename_noreplace(target, backup)
    rollback_new = new_recovery_path(name, "rollback-new")
    published = False
    try:
        issue = local_tree_issue(backup)
        if issue or local_state(backup) != expected_state:
            die(f"拒绝更新 {name}：安全检查后又出现了本地变化")
        try:
            rename_noreplace(staging, target)
        except FileExistsError:
            die(f"拒绝更新 {name}：隔离后原路径又被创建；"
                f"旧目录保留在 {backup}")
        published = True
        # 可能有进程在 rename 前已打开旧文件，它的晚到写入会落在
        # backup inode 上。删除备份前再对完整树做一次基线核验。
        issue = local_tree_issue(backup)
        if issue or local_state(backup) != expected_state:
            die(f"拒绝更新 {name}：隔离后收到了晚到的本地写入")
        # 不删 backup。已打开旧 inode 的进程仍可能在任何“最后检查”后
        # 写入；保留恢复副本才能从根本上避免不可恢复的丢数据窗口。
        print(f"  {DIM}恢复副本{RESET} {backup}")
    except BaseException:
        if backup.exists():
            if published and (target.exists() or target.is_symlink()):
                rename_noreplace(target, rollback_new)
                print(f"  {DIM}回滚新树副本{RESET} {rollback_new}")
            if not target.exists():
                try:
                    rename_noreplace(backup, target)
                except FileExistsError:
                    print(f"  {RED}旧树无法恢复到原名，仍保留在{RESET} {backup}")
        raise


def replace_skill_atomic(
    name: str,
    repo: str,
    files: dict,
    expected_state,
    keep=(),
):
    """全量取回一个 skill，组装新树，然后整棵替换。"""
    require_skills_root()
    payload = fetch_skill_payload(repo, files)
    if keep:
        if expected_state is None:
            die(f"无法为新建的 {name} 造出本地 keep 文件")
        target = SKILLS / name
        issue = local_tree_issue(target)
        if issue:
            die(f"拒绝更新 {name}：{issue}")
        for rel in keep:
            safe_relpath(rel)
            if rel in files:
                die(f"{name}/{rel} 同时是上游文件和 keep，归属不明")
            path = target.joinpath(*PurePosixPath(rel).parts)
            try:
                data = path.read_bytes()
                mode = "100755" if path.lstat().st_mode & 0o111 else "100644"
            except FileNotFoundError:
                die(f"拒绝更新 {name}：keep 文件 {rel} 在比对后不见了")
            state = (blob_sha(data), mode)
            if expected_state.get(rel) != state:
                die(f"拒绝更新 {name}：keep 文件 {rel} 在比对后发生了变化")
            payload[rel] = (data, mode)
    staging = Path(tempfile.mkdtemp(prefix=f".{name}.install.", dir=SKILLS))
    try:
        build_skill_tree(staging, payload)
        issue = local_tree_issue(staging)
        if issue:
            die(f"拒绝安装 {name}：远端载荷不安全：{issue}")
        swap_skill_tree(name, staging, expected_state)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def install_skill_atomic(name: str, repo: str, files: dict):
    """在同一文件系统的隐藏目录组装完成后，再一次性放到 skills/<name>。"""
    require_skills_root()
    if not valid_skill_name(name):
        die(f"拒绝安装非法 skill 名称：{name!r}")
    target = SKILLS / name
    if target.exists() or target.is_symlink():
        die(f"拒绝覆盖已存在的路径：{target}")

    replace_skill_atomic(name, repo, files, expected_state=None)


def prune_skill_atomic(name: str, expected_state):
    """先把待删目录原子移到隔离路径，再证明它仍等于 plan 时的完整基线。"""
    target = SKILLS / name
    if not target.exists() and not target.is_symlink():
        return False
    if expected_state is None:
        die(f"拒绝裁剪 {name}：比对时没有这个目录，之后才出现")
    if target.is_symlink() or not target.is_dir():
        die(f"拒绝裁剪 {name}：目标不是实体目录")

    quarantine = new_recovery_path(name, "prune")
    rename_noreplace(target, quarantine)
    try:
        issue = local_tree_issue(quarantine)
        if issue or local_state(quarantine) != expected_state:
            die(f"拒绝裁剪 {name}：安全检查后又出现了本地变化")
        if target.exists() or target.is_symlink():
            die(f"拒绝裁剪 {name}：隔离后原路径又被创建；"
                f"旧目录保留在 {quarantine}")
        # 同更新路径一样，捕获 rename 前已打开文件的晚到写入。
        issue = local_tree_issue(quarantine)
        if issue or local_state(quarantine) != expected_state:
            die(f"拒绝裁剪 {name}：隔离后收到了晚到的本地写入")
        print(f"  {DIM}恢复副本{RESET} {quarantine}")
    except BaseException:
        if quarantine.exists() and not target.exists() and not target.is_symlink():
            try:
                rename_noreplace(quarantine, target)
            except FileExistsError:
                print(f"  {RED}旧树无法恢复到原名，仍保留在{RESET} {quarantine}")
        raise
    return True


def apply_changes(index, report, prune):
    require_skills_root()
    # 在取任何远程 blob 前先检查全部本地写目标，避免应用一半才发现
    # 另一个 skill 有未跟踪文件。这也让“日常 --apply”可以安全默认使用。
    touched = sorted({name for name, *_ in report["drift"]})
    blockers = []
    for name in touched:
        reason = git_worktree_issue(name)
        if reason:
            blockers.append((name, reason))
    if prune:
        for name, _ in report["gone"]:
            reason = prune_blocker(name)
            if reason:
                blockers.append((name, reason))
    if blockers:
        details = "\n".join(f"  {name}: {reason}" for name, reason in blockers)
        die(f"拒绝写入：这些目录含不可恢复或无法验证的本地状态\n{details}")

    changed = 0
    drift_by_skill = {}
    for item in report["drift"]:
        drift_by_skill.setdefault(item[0], []).append(item)
    for name, items in sorted(drift_by_skill.items()):
        source, files = index[name]
        replace_skill_atomic(
            name,
            source["repo"],
            files,
            report["baseline"][name],
            source.get("keep", {}).get(name, []),
        )
        for _, _, rel, kind, _ in items:
            verb = "删除" if kind == EXTRA else "写入"
            colour = RED if kind == EXTRA else GREEN
            print(f"  {colour}{verb}{RESET} {name}/{rel}")
        changed += len(items)

    installed_new = []
    for name in report["missing"] + report["added"]:
        source, files = index[name]
        repo = source["repo"]
        install_skill_atomic(name, repo, files)
        print(f"  {GREEN}新建{RESET} {name}/  （{len(files)} 个文件，来自 {repo}）")
        if name in report["added"]:
            installed_new.append((name, source))
        changed += 1

    if prune:
        for name, source in report["gone"]:
            target = SKILLS / name
            # 删除紧前复检：上面的网络/文件操作期间可能又出现新本地内容。
            reason = prune_blocker(name)
            if reason:
                die(f"拒绝裁剪 {name}：{reason}")
            if prune_skill_atomic(name, report.get("gone_baseline", {}).get(name)):
                print(f"  {RED}删除{RESET} {name}/  （已登记来源的上游已删除）")
            else:
                print(f"  {RED}移除登记{RESET} {name}  （本地已不存在，上游也已删除）")
            source["managed"] = sorted(set(source["managed"]) - {name})
            changed += 1
    elif report["gone"]:
        print(f"  {YELLOW}跳过{RESET} {len(report['gone'])} 个上游已删除的 skill —— 要删加 --prune")

    for name, source in installed_new:
        source["managed"] = sorted(set(source["managed"]) | {name})
    for name, source in report["adoptable"]:
        _, expected_files = index[name]
        issue = local_tree_issue(SKILLS / name)
        if issue:
            die(f"拒绝补登记 {name}：{issue}")
        loc = local_state(SKILLS / name)
        keep = source.get("keep", {}).get(name, [])
        comparable = {rel: state for rel, state in loc.items() if rel not in keep}
        if comparable != expected_files or any(rel not in loc for rel in keep):
            die(f"拒绝补登记 {name}：本地内容在比对后发生了变化")
        source["managed"] = sorted(set(source["managed"]) | {name})
        print(f"  {GREEN}补登记{RESET} {name}  （本地字节与上游完全一致）")
        changed += 1
    return changed


# ---------------------------------------------------------------- 软链

def quarantine_link(entry: Path, expected: Path):
    """
    原子移走 agent 目录里的当前项，再验证它仍是脚本创建的精确软链。

    隔离项不永久删除：这同时关闭“检查后被并发替换为实体文件”的丢数据窗口。
    """
    recovery = entry.parent / ".sync-skills-recovery"
    if recovery.is_symlink():
        return False, f"恢复目录是软链：{recovery}"
    if recovery.exists():
        if not stat.S_ISDIR(recovery.lstat().st_mode):
            return False, f"恢复路径不是目录：{recovery}"
    else:
        recovery.mkdir(mode=0o700)
    slot = Path(tempfile.mkdtemp(prefix=f"{entry.name}.", dir=recovery))
    held = slot / "entry"
    try:
        rename_noreplace(entry, held)
    except FileNotFoundError:
        slot.rmdir()
        return True, None  # 另一个进程已移走，无内容可删。

    # 相对链接仍以原父目录为基准；移入恢复目录不能改变归属判断。
    owned = held.is_symlink() and Path(
        os.path.realpath(entry.parent / os.readlink(held))
    ) == expected
    if owned:
        return True, str(held)

    # 不自动放回 canonical 名称。“检查为空→rename 放回”仍可能覆盖
    # 检查后才出现的第二个并发文件；留在恢复区才不会丢任何一份。
    return False, f"目录项在检查后被替换，已保留在 {held}"

def sync_links(manifest, dry=False):
    """返回 (可修的问题数, 不敢碰的问题数)。"""
    require_skills_root()
    wanted_all, unsafe_skills = [], set()
    blocked = 0
    for path in sorted(SKILLS.iterdir()):
        if path.name.startswith("."):
            continue
        issue = local_tree_issue(path)
        if issue:
            unsafe_skills.add(path.name)
            print(f"  {RED}警告{RESET} skills/{path.name} 不安全：{issue} —— 不会建链或删链")
            blocked += 1
        else:
            wanted_all.append(path.name)
    skills_real = Path(os.path.realpath(SKILLS))
    fixable = 0

    for agent, cfg in manifest["links"].items():
        d = Path(os.path.expanduser(cfg["dir"]))
        if not d.is_dir():
            if d.exists() or d.is_symlink():
                print(f"  {RED}警告{RESET} {agent}：{d} 不是可用目录 —— 不会覆盖")
                blocked += 1
                continue
            print(f"  {GREEN}{'待创建目录' if dry else '创建目录'}{RESET} {d}")
            fixable += 1
            if dry:
                continue
            d.mkdir(parents=True, exist_ok=True)
        wanted = {n for n in wanted_all if n not in cfg["exclude"]}

        for entry in sorted(d.iterdir()):
            if entry.name.startswith("."):
                continue

            if not entry.is_symlink():
                # 实体目录或文件。可能装着别处没有的内容，绝不替用户删。
                what = "实体目录" if entry.is_dir() else "普通文件"
                conflict = entry.name in wanted or entry.name in unsafe_skills
                print(f"  {YELLOW}{'警告' if conflict else '提示'}{RESET} {agent}/{entry.name} "
                      f"是{what}，{'占用所需链接位置' if conflict else '与所需链接无冲突'} —— 保留")
                blocked += int(conflict)
                continue

            dest = Path(os.path.realpath(entry))
            expected = skills_real / entry.name
            if dest != expected:
                # 本脚本只会创建 name -> skills/name。别名、交叉链和仓库外
                # 的链都没有所有权证据，绝不替用户删。
                conflict = entry.name in wanted or entry.name in unsafe_skills
                broken = not entry.exists()
                print(f"  {YELLOW}{'警告' if conflict or broken else '提示'}{RESET} "
                      f"{agent}/{entry.name} 指向 {dest}"
                      f"（{'断链' if broken else '外部链接或别名'}） —— 保留")
                blocked += int(conflict or broken)
                continue

            if entry.name in unsafe_skills:
                print(f"  {YELLOW}警告{RESET} {agent}/{entry.name} 指向不安全的 skill —— 我不会动它")
                blocked += 1
                continue

            if entry.name not in wanted or not dest.exists():
                why = "断链" if not dest.exists() else "不该在这"
                print(f"  {RED}{'待移除' if dry else '移除'}{RESET} {agent}/{entry.name}  （{why}）")
                if not dry:
                    removed, detail = quarantine_link(entry, expected)
                    if not removed:
                        print(f"  {RED}警告{RESET} {agent}/{entry.name} 未移除：{detail}")
                        blocked += 1
                        continue
                    if detail:
                        print(f"  {DIM}恢复副本{RESET} {detail}")
                fixable += 1

        for name in sorted(wanted):
            link = d / name
            if link.is_symlink() and Path(os.path.realpath(link)) == skills_real / name:
                continue
            if link.exists() or link.is_symlink():
                continue  # 上面已经警告过了
            print(f"  {GREEN}{'待软链' if dry else '软链'}{RESET} {agent}/{name}")
            if not dry:
                link.symlink_to(SKILLS / name)
            fixable += 1

    return fixable, blocked


# ---------------------------------------------------------------- add

def cmd_add(args, manifest, expected_manifest):
    require_skills_root()
    repo, ref = args.repo, args.ref
    if args.all and args.skills:
        die("--all 和具体 skill 名不能同时使用")
    if len(args.skills) != len(set(args.skills)):
        die("同一个 skill 名不能重复指定")
    if any(s["repo"] == repo and s.get("ref", "HEAD") == ref for s in manifest["sources"]):
        die(f"{repo}@{ref} 已在 upstream.json 登记；请编辑它的 only，"
            "或直接跑 sync-skills.py --apply")
    tree = fetch_tree(repo, ref)

    # 全仓库扫一遍：任何含 SKILL.md 的目录都是候选，不预设它藏在哪。
    blobs = {t["path"] for t in tree["tree"] if t["type"] == "blob"}
    candidates = {}
    for p in blobs:
        if not p.endswith("/SKILL.md"):
            continue
        base = p[: -len("/SKILL.md")]
        name = base.split("/")[-1]
        if not valid_skill_name(name):
            die(f"{repo} 含不安全的 skill 名称：{name!r}")
        candidates.setdefault(name, set()).add(base)
    duplicates = {name: bases for name, bases in candidates.items() if len(bases) > 1}
    if duplicates:
        details = "；".join(
            f"{name}: {', '.join(sorted(bases))}" for name, bases in sorted(duplicates.items())
        )
        die(f"{repo} 里有同名 skill，请先用不同名称消除歧义：{details}")
    found = {name: next(iter(bases)) for name, bases in candidates.items()}
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

    local = {p.name for p in SKILLS.iterdir()}
    clash = [s for s in chosen if s in local]
    if clash:
        die(f"这些名字本地已经有了：{', '.join(clash)}\n"
            f"重名会让同步分不清该跟谁，先改名或删掉旧的。")

    roots = sorted({found[s].rsplit("/", 1)[0] if "/" in found[s] else "" for s in chosen})
    source = {"repo": repo, "ref": ref, "roots": roots, "managed": sorted(chosen)}
    if not args.all:
        source["only"] = sorted(chosen)

    print(f"\n{BOLD}要装{RESET}")
    for s in sorted(chosen):
        print(f"  {s}  {DIM}{repo}/{found[s]}{RESET}")
    print(f"  {DIM}roots: {roots or ['(仓库根)']}{RESET}")

    files = discover(source)
    missing = [name for name in chosen if name not in files]
    if missing:
        die(f"上游在安装前发生变化，已找不到：{', '.join(missing)}")

    # 先登记归属，再逐个原子放入目录。之后若断网/磁盘失败，状态是
    # “已登记但本地缺失”，下次 --apply 能自动续上，不会卡成来源冲突。
    manifest["sources"].append(source)
    save_manifest(manifest, expected_manifest)
    print(f"  {GREEN}登记{RESET} upstream.json —— 从此每次同步都会检查它")

    for name in sorted(chosen):
        install_skill_atomic(name, repo, files[name])
        print(f"  {GREEN}新建{RESET} {name}/  （{len(files[name])} 个文件）")

    print(f"\n{BOLD}软链{RESET}")
    sync_links(manifest)
    print(f"\n{DIM}装完了。检查一下 git diff，然后提交。{RESET}")


# ---------------------------------------------------------------- list

def cmd_list(manifest):
    require_skills_root()
    # 当前上游回答“现在有谁”，managed 回答“过去接纳过谁”；两者不能混为一谈。
    origin, all_origin, managed_origin, optional = {}, {}, {}, []
    for source in manifest["sources"]:
        all_remote = discover(source, include_filtered=True)
        selected = (
            {name: all_remote[name] for name in source["only"] if name in all_remote}
            if "only" in source else all_remote
        )
        for name in all_remote:
            all_origin.setdefault(name, source["repo"])
        for name in selected:
            origin.setdefault(name, source["repo"])
        for name in source.get("managed", []):
            managed_origin.setdefault(name, source["repo"])
        for name in sorted(set(all_remote) - set(selected) - set(source.get("managed", []))):
            optional.append((name, source["repo"]))

    untracked = manifest["untracked"]
    local_paths = {p.name: p for p in SKILLS.iterdir() if not p.name.startswith(".")}
    local = sorted(local_paths)
    unsafe_local = {
        name: issue for name, path in local_paths.items()
        if (issue := local_tree_issue(path))
    }

    # 每个 agent 目录里，这个 skill 有没有正确软链回来。
    agents = {}
    skills_real = Path(os.path.realpath(SKILLS))
    for agent, cfg in manifest["links"].items():
        d = Path(os.path.expanduser(cfg["dir"]))
        linked = set()
        if d.is_dir():
            for name in local:
                link = d / name
                if link.is_symlink() and Path(os.path.realpath(link)) == skills_real / name:
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
        if name in unsafe_local:
            return f"{RED}不安全{RESET}  {DIM}{unsafe_local[name]}{RESET}"
        if name in managed_origin:
            repo = managed_origin[name]
            if name in origin:
                return f"{DIM}{repo}{RESET}"
            if name in all_origin:
                return f"{YELLOW}已登记但被 only 排除{RESET}  {DIM}{repo}{RESET}"
            return f"{YELLOW}上游已删除{RESET}  {DIM}{repo}（有 managed 记录）{RESET}"
        if name in untracked:
            return f"{YELLOW}不跟上游{RESET}  {DIM}{untracked[name]}{RESET}"
        if name in origin:
            return f"{RED}登记冲突{RESET}  {DIM}与 {origin[name]} 的新增 skill 同名{RESET}"
        return f"{RED}未登记{RESET}  {DIM}不会更新，也不会被 --prune 删除{RESET}"

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

    if optional:
        print(f"\n{CYAN}only 外还发现 {len(optional)} 个可选 skill{RESET}  "
              f"{DIM}（不会自动安装）{RESET}")
        for name, repo in optional:
            print(f"  {name}  {DIM}{repo}{RESET}")


# ---------------------------------------------------------------- 报告

def show(r):
    if r["manifest_errors"]:
        print(f"\n{RED}{BOLD}来源登记错误{RESET}  upstream.json 不能证明这些 skill 的归属：")
        for error in r["manifest_errors"]:
            print(f"  {error}")

    if r["collisions"]:
        print(f"\n{RED}{BOLD}名字撞车{RESET}  同一个 skill 名出现在多个上游：")
        for name, a, b in r["collisions"]:
            print(f"  {name}: {a} 和 {b}")
        print(f"  {DIM}没法判断该跟谁，所以 --apply 会拒绝执行。在 upstream.json 里用 only 划清。{RESET}")

    if r["missing_keep"]:
        print(f"\n{RED}{BOLD}keep 文件不见了{RESET}  上游没有这些文件，脚本也造不出来：")
        for name, rel in r["missing_keep"]:
            print(f"  {name}/{rel}  {DIM}→ git restore skills/{name}/{rel}{RESET}")

    if r["unsafe"]:
        print(f"\n{RED}{BOLD}不安全的本地路径{RESET}  可能让同步跟随软链写出 skills/：")
        for name, reason in r["unsafe"]:
            print(f"  {name}  {DIM}{reason}{RESET}")
        print(f"  {DIM}修复前 --apply 会拒绝写入。{RESET}")

    if r["adoption_conflicts"]:
        print(f"\n{RED}{BOLD}登记冲突{RESET}  上游新增与未登记的本地目录同名，不会覆盖：")
        for name, repo in r["adoption_conflicts"]:
            print(f"  {name}  {DIM}{repo}{RESET}")
        print(f"  {DIM}确认归属后，显式登记或给其中一边改名。{RESET}")

    if r["gone"]:
        print(f"\n{YELLOW}{BOLD}上游已删除{RESET}  managed 有历史归属、当前上游已找不到：")
        for name, source in r["gone"]:
            print(f"  {name}  {DIM}{source['repo']}{RESET}")
        print(f"  {DIM}确认过就用 --prune 删掉。改名的话，新名字会出现在下面「上游新增」里。{RESET}")

    if r["added"]:
        print(f"\n{CYAN}{BOLD}上游新增{RESET}  上游有，本地没有：")
        for name in r["added"]:
            print(f"  {name}")

    if r["adoptable"]:
        print(f"\n{CYAN}{BOLD}待补登记{RESET}  本地与上游字节完全一致：")
        for name, source in r["adoptable"]:
            print(f"  {name}  {DIM}{source['repo']}{RESET}")
        print(f"  {DIM}--apply 只补 managed 归属，不改内容。{RESET}")

    if r["missing"]:
        print(f"\n{CYAN}{BOLD}受管 skill 本地缺失{RESET}  上游仍有，--apply 会恢复：")
        for name in r["missing"]:
            print(f"  {name}")

    if r["unregistered"]:
        print(f"\n{RED}{BOLD}未登记{RESET}  来源未知；只报告，--apply 和 --prune 都不会碰：")
        for name in r["unregistered"]:
            print(f"  {name}")
        print(f"  {DIM}要纳管请先确认来源，再用 sync-skills.py add 安装；本地独有请写进 untracked。{RESET}")

    if r["filtered"]:
        print(f"\n{YELLOW}{BOLD}已登记但被 only 排除{RESET}  不更新，也不删除：")
        for name, repo in r["filtered"]:
            print(f"  {name}  {DIM}{repo}{RESET}")

    if r["optional"]:
        print(f"\n{CYAN}{BOLD}only 外的远端 skill{RESET}  已发现，但不会自动安装：")
        for name, repo in r["optional"]:
            print(f"  {name}  {DIM}{repo}{RESET}")
        print(f"  {DIM}想纳管就把名称加到该 source 的 only；--all 来源则会自动安装新增。{RESET}")

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
    ap.add_argument("--link", action="store_true", help="离线建链/修链，创建缺失目录；与 --apply 合用时仍查询上游")
    ap.add_argument(
        "--prune", action="store_true",
        help="移出有 managed 归属、上游已删且工作树干净的 skill（保留恢复副本）",
    )

    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list", help="列出所有 skill：来源和软链现状")
    a = sub.add_parser("add", help="装一个新来源的 skill")
    a.add_argument("repo", help="owner/repo")
    a.add_argument("skills", nargs="*", help="要装哪几个；不写就列出来给你看")
    a.add_argument("--all", action="store_true", help="整个仓库都跟（以后它新增的 skill 也会自动发现）")
    a.add_argument("--ref", default="HEAD")

    args = ap.parse_args()

    if args.link and args.cmd:
        ap.error("--link 不能与 list/add 子命令合用")
    if args.link and args.prune and not args.apply:
        ap.error("--link --prune 需要 --apply；离线建链不会裁剪 skill")

    manifest_original = MANIFEST.read_bytes()
    manifest = json.loads(manifest_original)

    if args.link and not args.apply:
        print(f"{BOLD}本地软链{RESET}  不查询上游、不修改 skill 内容")
        fixable, blocked = sync_links(manifest)
        if blocked:
            sys.exit(1)
        print(f"  {GREEN}{'软链已更新' if fixable else '软链无需更新'}{RESET}")
        return

    if not shutil.which("gh"):
        die("需要 gh CLI（brew install gh && gh auth login）")

    if args.cmd == "list":
        cmd_list(manifest)
        return

    if args.cmd == "add":
        cmd_add(args, manifest, manifest_original)
        return

    if args.prune and not args.apply:
        print(f"{YELLOW}--prune 要配合 --apply 才有效{RESET}")

    print(f"{BOLD}比对上游{RESET}  {DIM}{len(manifest['sources'])} 个仓库{RESET}")
    manifest_before = json.dumps(manifest, sort_keys=True, ensure_ascii=False)
    index, report = plan(manifest)
    show(report)

    blocking = bool(
        report["collisions"]
        or report["manifest_errors"]
        or report["missing_keep"]
        or report["unsafe"]
        or report["adoption_conflicts"]
    )
    actionable = bool(
        report["drift"] or report["added"] or report["missing"]
        or report["gone"] or report["adoptable"]
    )
    unresolved = bool(report["unregistered"] or report["filtered"])
    dirty = actionable or unresolved or blocking

    if args.apply and blocking:
        die("\n先解决上面的归属、路径安全、撞车或 keep 问题；在此之前拒绝写入。")

    if args.apply:
        if actionable:
            print(f"\n{BOLD}应用{RESET}")
            apply_changes(index, report, args.prune)
            if json.dumps(manifest, sort_keys=True, ensure_ascii=False) != manifest_before:
                save_manifest(manifest, manifest_original)
                print(f"  {GREEN}更新登记{RESET} upstream.json")
        else:
            print(f"\n{GREEN}受管 skill 没有变化{RESET}")
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

    still_unresolved = unresolved or (bool(report["gone"]) and not (args.apply and args.prune))
    if blocked or still_unresolved or (dirty and not args.apply) or (fixable and not write_links):
        sys.exit(1)


if __name__ == "__main__":
    main()
