import base64
import importlib.util
import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync-skills.py"
SPEC = importlib.util.spec_from_file_location("sync_skills", SCRIPT)
sync_skills = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_skills)


class SyncSkillsTests(unittest.TestCase):
    @staticmethod
    def source(*managed, only=None):
        source = {
            "repo": "example/repo",
            "ref": "HEAD",
            "roots": ["skills"],
            "managed": list(managed),
        }
        if only is not None:
            source["only"] = list(only)
        return source

    @staticmethod
    def manifest(source, links=None):
        return {
            "sources": [source],
            "untracked": {},
            "links": links or {},
        }

    @staticmethod
    def init_git(root, *paths):
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "add", *paths], cwd=root, check=True)
        subprocess.run(
            [
                "git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                "commit", "-qm", "fixture",
            ],
            cwd=root,
            check=True,
        )

    def test_fetch_blob_rejects_content_that_does_not_match_tree_sha(self):
        encoded = base64.b64encode(b"wrong bytes").decode()
        with mock.patch.object(sync_skills, "gh", return_value={"content": encoded}):
            with self.assertRaises(SystemExit):
                sync_skills.fetch_blob(
                    "example/repo", sync_skills.blob_sha(b"expected bytes"), "SKILL.md"
                )

    def test_discover_rejects_remote_git_metadata_path(self):
        tree = {
            "tree": [
                {
                    "type": "blob", "mode": "100644", "sha": "a" * 40,
                    "path": "skills/probe/SKILL.md",
                },
                {
                    "type": "blob", "mode": "100644", "sha": "b" * 40,
                    "path": "skills/probe/.GiT/config",
                },
            ]
        }
        source = self.source()
        with mock.patch.object(sync_skills, "fetch_tree", return_value=tree):
            with self.assertRaises(SystemExit):
                sync_skills.discover(source)

    def test_new_install_rejects_remote_git_metadata_without_partial_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / "skills"
            skills.mkdir()
            files = {
                "SKILL.md": ("a" * 40, "100644"),
                ".git/config": ("b" * 40, "100644"),
            }

            def content_for_path(_repo, _sha, path):
                return path.encode()

            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "fetch_blob", side_effect=content_for_path),
            ):
                with self.assertRaises(SystemExit):
                    sync_skills.install_skill_atomic("probe", "example/repo", files)

            self.assertFalse((skills / "probe").exists())
            self.assertEqual(list(skills.iterdir()), [])

    def test_existing_update_rejects_remote_git_metadata_and_preserves_old_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skill = skills / "probe"
            skill.mkdir(parents=True)
            old = skill / "SKILL.md"
            old.write_text("old\n")
            self.init_git(root, "skills/probe/SKILL.md")
            source = self.source("probe")
            remote = {
                "probe": {
                    "SKILL.md": (sync_skills.blob_sha(b"remote\n"), "100644"),
                    ".git/config": (sync_skills.blob_sha(b"hidden\n"), "100644"),
                }
            }

            def content_for_path(_repo, _sha, path):
                return b"remote\n" if path == "SKILL.md" else b"hidden\n"

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
                mock.patch.object(sync_skills, "fetch_blob", side_effect=content_for_path),
                redirect_stdout(io.StringIO()),
            ):
                index, report = sync_skills.plan(self.manifest(source))
                with self.assertRaises(SystemExit):
                    sync_skills.apply_changes(index, report, prune=False)

            self.assertEqual(old.read_text(), "old\n")
            self.assertFalse((skill / ".git").exists())

    def test_prune_preserves_unregistered_local_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / "skills"
            (skills / "tracked").mkdir(parents=True)
            (skills / "tracked" / "SKILL.md").write_text("tracked\n")
            (skills / "manual").mkdir()
            (skills / "manual" / "SKILL.md").write_text("keep me\n")
            (skills / "manual" / "empty-assets").mkdir()

            tracked = {
                "SKILL.md": (sync_skills.blob_sha(b"tracked\n"), "100644")
            }
            manifest = self.manifest(self.source("tracked"))

            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(
                    sync_skills, "discover", return_value={"tracked": tracked}
                ),
            ):
                index, report = sync_skills.plan(manifest)
                self.assertEqual(report["unregistered"], ["manual"])
                self.assertEqual(report["gone"], [])
                sync_skills.apply_changes(index, report, prune=True)

            self.assertTrue((skills / "manual" / "SKILL.md").is_file())
            self.assertTrue((skills / "manual" / "empty-assets").is_dir())

    def test_prune_removes_only_managed_remote_deletion_and_its_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            retired = skills / "retired"
            retired.mkdir(parents=True)
            (retired / "SKILL.md").write_text("retired\n")
            claude = root / "claude"
            codex = root / "codex"
            claude.mkdir()
            codex.mkdir()
            (claude / "retired").symlink_to(retired)
            (codex / "retired").symlink_to(retired)

            source = self.source("retired")
            manifest = self.manifest(
                source,
                {
                    "claude": {"dir": str(claude), "exclude": []},
                    "codex": {"dir": str(codex), "exclude": []},
                },
            )

            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value={}),
                mock.patch.object(sync_skills, "prune_blocker", return_value=None),
                redirect_stdout(io.StringIO()),
            ):
                index, report = sync_skills.plan(manifest)
                self.assertEqual([name for name, _ in report["gone"]], ["retired"])
                self.assertEqual(report["unregistered"], [])
                sync_skills.apply_changes(index, report, prune=True)
                sync_skills.sync_links(manifest)

            self.assertFalse(retired.exists())
            self.assertFalse((claude / "retired").is_symlink())
            self.assertFalse((codex / "retired").is_symlink())
            self.assertEqual(source["managed"], [])

    def test_apply_installs_and_registers_new_remote_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / "skills"
            skills.mkdir()
            source = self.source()
            manifest = self.manifest(source)
            remote = {
                "new-skill": {
                    "SKILL.md": (sync_skills.blob_sha(b"new\n"), "100755")
                }
            }

            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
                mock.patch.object(sync_skills, "fetch_blob", return_value=b"new\n"),
                redirect_stdout(io.StringIO()),
            ):
                index, report = sync_skills.plan(manifest)
                self.assertEqual(report["added"], ["new-skill"])
                sync_skills.apply_changes(index, report, prune=False)

            installed = skills / "new-skill" / "SKILL.md"
            self.assertEqual(installed.read_bytes(), b"new\n")
            self.assertTrue(os.access(installed, os.X_OK))
            self.assertEqual(source["managed"], ["new-skill"])

    def test_new_install_publish_never_replaces_late_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / "skills"
            skills.mkdir()
            source = self.source()
            remote = {
                "new-skill": {
                    "SKILL.md": (sync_skills.blob_sha(b"new\n"), "100644")
                }
            }

            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
            ):
                index, report = sync_skills.plan(self.manifest(source))

            real_rename_noreplace = sync_skills.rename_noreplace

            def create_target_at_publish(source_path, target_path):
                target_path = Path(target_path)
                if target_path == skills / "new-skill":
                    target_path.mkdir(mode=0o711)
                return real_rename_noreplace(source_path, target_path)

            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "fetch_blob", return_value=b"new\n"),
                mock.patch.object(
                    sync_skills,
                    "rename_noreplace",
                    side_effect=create_target_at_publish,
                ),
                redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(SystemExit):
                    sync_skills.apply_changes(index, report, prune=False)

            target = skills / "new-skill"
            self.assertTrue(target.is_dir())
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o711)
            self.assertEqual(list(target.iterdir()), [])
            self.assertEqual(source["managed"], [])

    def test_existing_update_publish_never_replaces_late_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skill = skills / "x"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("old\n")
            self.init_git(root, "skills/x/SKILL.md")
            source = self.source("x")
            remote = {
                "x": {"SKILL.md": (sync_skills.blob_sha(b"new\n"), "100644")}
            }

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
            ):
                index, report = sync_skills.plan(self.manifest(source))

            real_rename_noreplace = sync_skills.rename_noreplace

            def create_target_at_publish(source_path, target_path):
                target_path = Path(target_path)
                if target_path == skill:
                    target_path.mkdir(mode=0o711)
                return real_rename_noreplace(source_path, target_path)

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "fetch_blob", return_value=b"new\n"),
                mock.patch.object(
                    sync_skills,
                    "rename_noreplace",
                    side_effect=create_target_at_publish,
                ),
                redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(SystemExit):
                    sync_skills.apply_changes(index, report, prune=False)

            self.assertTrue(skill.is_dir())
            self.assertEqual(stat.S_IMODE(skill.stat().st_mode), 0o711)
            self.assertEqual(list(skill.iterdir()), [])
            backups = list((root / ".sync-skills-recovery").glob("x.update.*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "SKILL.md").read_text(), "old\n")
            self.assertEqual(source["managed"], ["x"])

    def test_remote_new_skill_cannot_overwrite_unregistered_same_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / "skills"
            candidate = skills / "candidate"
            candidate.mkdir(parents=True)
            local = candidate / "SKILL.md"
            local.write_text("local fork\n")
            source = self.source()
            remote = {
                "candidate": {
                    "SKILL.md": (sync_skills.blob_sha(b"upstream\n"), "100644")
                }
            }

            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
            ):
                _, report = sync_skills.plan(self.manifest(source))

            self.assertEqual(report["adoption_conflicts"], [("candidate", "example/repo")])
            self.assertEqual(report["drift"], [])
            self.assertEqual(report["added"], [])
            self.assertEqual(local.read_text(), "local fork\n")

    def test_only_filter_does_not_turn_existing_remote_skill_into_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / "skills"
            (skills / "b").mkdir(parents=True)
            (skills / "b" / "SKILL.md").write_text("b\n")
            source = self.source("b", only=["a"])
            remote = {
                "a": {"SKILL.md": (sync_skills.blob_sha(b"a\n"), "100644")},
                "b": {"SKILL.md": (sync_skills.blob_sha(b"b\n"), "100644")},
            }

            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
            ):
                _, report = sync_skills.plan(self.manifest(source))

            self.assertEqual(report["gone"], [])
            self.assertEqual(report["filtered"], [("b", "example/repo")])
            self.assertEqual(report["optional"], [])
            self.assertEqual(report["unregistered"], [])

    def test_only_reports_unselected_remote_addition_without_installing_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / "skills"
            (skills / "a").mkdir(parents=True)
            (skills / "a" / "SKILL.md").write_text("a\n")
            source = self.source("a", only=["a"])
            remote = {
                "a": {"SKILL.md": (sync_skills.blob_sha(b"a\n"), "100644")},
                "optional-b": {
                    "SKILL.md": (sync_skills.blob_sha(b"b\n"), "100644")
                },
            }

            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
            ):
                _, report = sync_skills.plan(self.manifest(source))

            self.assertEqual(report["optional"], [("optional-b", "example/repo")])
            self.assertEqual(report["added"], [])

    def test_prune_guard_requires_tracked_clean_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            retired = skills / "retired"
            retired.mkdir(parents=True)
            skill_file = retired / "SKILL.md"
            skill_file.write_text("clean\n")
            (root / ".gitignore").write_text("*.log\n")
            self.init_git(root, ".gitignore", "skills/retired/SKILL.md")

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
            ):
                self.assertIsNone(sync_skills.prune_blocker("retired"))
                skill_file.write_text("modified\n")
                self.assertIn("本地改动", sync_skills.prune_blocker("retired"))
                skill_file.write_text("clean\n")
                (retired / "notes.txt").write_text("untracked\n")
                self.assertIn("未跟踪", sync_skills.prune_blocker("retired"))
                (retired / "notes.txt").unlink()
                (retired / "cache.log").write_text("ignored\n")
                self.assertIn("!!", sync_skills.prune_blocker("retired"))

    def test_prune_guard_rejects_nested_git_directory_or_gitfile(self):
        for git_kind in ("directory", "file"):
            with self.subTest(git_kind=git_kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                skills = root / "skills"
                retired = skills / "retired"
                retired.mkdir(parents=True)
                (retired / "SKILL.md").write_text("clean\n")
                self.init_git(root, "skills/retired/SKILL.md")
                if git_kind == "directory":
                    subprocess.run(["git", "init", "-q"], cwd=retired, check=True)
                else:
                    (retired / ".git").write_text("gitdir: /some/worktree/metadata\n")

                with (
                    mock.patch.object(sync_skills, "ROOT", root),
                    mock.patch.object(sync_skills, "SKILLS", skills),
                ):
                    reason = sync_skills.prune_blocker("retired")

                self.assertIn("嵌套 Git", reason)
                self.assertTrue((retired / ".git").exists())

    def test_prune_guard_rejects_hidden_index_flags(self):
        for flag, undo in (
            ("--assume-unchanged", "--no-assume-unchanged"),
            ("--skip-worktree", "--no-skip-worktree"),
        ):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                skills = root / "skills"
                retired = skills / "retired"
                retired.mkdir(parents=True)
                skill_file = retired / "SKILL.md"
                skill_file.write_text("clean\n")
                self.init_git(root, "skills/retired/SKILL.md")
                subprocess.run(
                    ["git", "update-index", flag, "skills/retired/SKILL.md"],
                    cwd=root,
                    check=True,
                )
                skill_file.write_text("hidden local change\n")

                with (
                    mock.patch.object(sync_skills, "ROOT", root),
                    mock.patch.object(sync_skills, "SKILLS", skills),
                ):
                    reason = sync_skills.prune_blocker("retired")

                self.assertIn("skip-worktree", reason)
                subprocess.run(
                    ["git", "update-index", undo, "skills/retired/SKILL.md"],
                    cwd=root,
                    check=True,
                )

    def test_prune_guard_rejects_combined_hidden_index_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            retired = skills / "retired"
            retired.mkdir(parents=True)
            skill_file = retired / "SKILL.md"
            skill_file.write_text("clean\n")
            self.init_git(root, "skills/retired/SKILL.md")
            subprocess.run(
                ["git", "update-index", "--assume-unchanged", "skills/retired/SKILL.md"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "update-index", "--skip-worktree", "skills/retired/SKILL.md"],
                cwd=root,
                check=True,
            )
            skill_file.write_text("hidden local change\n")
            tag = subprocess.run(
                ["git", "ls-files", "-v", "--", "skills/retired/SKILL.md"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout[:1]
            self.assertEqual(tag, "s")  # 组合标志不是单独的 h 或 S。

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
            ):
                self.assertIn("skip-worktree", sync_skills.prune_blocker("retired"))
                self.assertIn("skip-worktree", sync_skills.git_worktree_issue("retired"))

    def test_symlinked_skills_root_is_rejected_before_remote_or_local_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"
            outside.mkdir()
            (outside / "tracked").mkdir()
            payload = outside / "tracked" / "SKILL.md"
            payload.write_text("outside\n")
            skills = root / "skills"
            skills.symlink_to(outside, target_is_directory=True)

            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover") as discover,
            ):
                with self.assertRaises(SystemExit):
                    sync_skills.plan(self.manifest(self.source("tracked")))

            discover.assert_not_called()
            self.assertEqual(payload.read_text(), "outside\n")

    def test_regular_apply_refuses_dirty_or_untracked_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skill = skills / "tracked"
            skill.mkdir(parents=True)
            local = skill / "SKILL.md"
            local.write_text("base\n")
            self.init_git(root, "skills/tracked/SKILL.md")
            local.write_text("local edit\n")
            private = skill / "notes.private"
            private.write_text("do not delete\n")

            remote = {
                "tracked": {
                    "SKILL.md": (sync_skills.blob_sha(b"remote\n"), "100644")
                }
            }
            source = self.source("tracked")
            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
                redirect_stdout(io.StringIO()),
            ):
                index, report = sync_skills.plan(self.manifest(source))
                with self.assertRaises(SystemExit):
                    sync_skills.apply_changes(index, report, prune=False)

            self.assertEqual(local.read_text(), "local edit\n")
            self.assertEqual(private.read_text(), "do not delete\n")

    def test_symlinked_payload_cannot_escape_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skill = skills / "tracked"
            skill.mkdir(parents=True)
            outside = root / "outside.txt"
            outside.write_text("outside\n")
            (skill / "SKILL.md").symlink_to(outside)
            remote = {
                "tracked": {
                    "SKILL.md": (sync_skills.blob_sha(b"remote\n"), "100644")
                }
            }

            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
            ):
                _, report = sync_skills.plan(self.manifest(self.source("tracked")))

            self.assertEqual(report["unsafe"], [("tracked", "SKILL.md 是软链")])
            self.assertEqual(report["drift"], [])
            self.assertEqual(outside.read_text(), "outside\n")

            # 即使调用者绕过 plan，叶子软链也只会被原子替换，不会跟出去。
            sync_skills.write_blob(skill / "SKILL.md", b"safe\n", "100644", skill)
            self.assertEqual((skill / "SKILL.md").read_text(), "safe\n")
            self.assertFalse((skill / "SKILL.md").is_symlink())
            self.assertEqual(outside.read_text(), "outside\n")

    def test_missing_skill_with_keep_is_a_hard_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skills.mkdir()
            source = self.source("licensed")
            source["keep"] = {"licensed": ["LICENSE.txt"]}
            manifest = self.manifest(source)
            manifest_path = root / "upstream.json"
            manifest_path.write_text(json.dumps(manifest))
            remote = {
                "licensed": {
                    "SKILL.md": (sync_skills.blob_sha(b"remote\n"), "100644")
                }
            }

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "MANIFEST", manifest_path),
                mock.patch.object(sync_skills, "discover", return_value=remote),
                mock.patch.object(sync_skills.shutil, "which", return_value="/usr/bin/gh"),
                mock.patch.object(sync_skills.sys, "argv", ["sync-skills.py", "--apply"]),
                redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(SystemExit):
                    sync_skills.main()

            self.assertFalse((skills / "licensed").exists())

    def test_new_install_is_atomic_and_complete_retry_is_adoptable(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / "skills"
            skills.mkdir()
            source = self.source()
            manifest = self.manifest(source)
            remote = {
                "new-skill": {
                    "SKILL.md": (sync_skills.blob_sha(b"skill\n"), "100644"),
                    "notes.md": (sync_skills.blob_sha(b"notes\n"), "100644"),
                }
            }

            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
                mock.patch.object(
                    sync_skills,
                    "fetch_blob",
                    side_effect=[b"skill\n", RuntimeError("network failed")],
                ),
                redirect_stdout(io.StringIO()),
            ):
                index, report = sync_skills.plan(manifest)
                with self.assertRaises(RuntimeError):
                    sync_skills.apply_changes(index, report, prune=False)

            self.assertFalse((skills / "new-skill").exists())
            self.assertEqual(list(skills.iterdir()), [])
            self.assertEqual(source["managed"], [])

            # 完整目录若只是没来得及保存 managed，下次会补登记而非自锁。
            installed = skills / "new-skill"
            installed.mkdir()
            (installed / "SKILL.md").write_text("skill\n")
            (installed / "notes.md").write_text("notes\n")
            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
                redirect_stdout(io.StringIO()),
            ):
                index, retry = sync_skills.plan(manifest)
                self.assertEqual([name for name, _ in retry["adoptable"]], ["new-skill"])
                self.assertEqual(retry["adoption_conflicts"], [])
                sync_skills.apply_changes(index, retry, prune=False)

            self.assertEqual(source["managed"], ["new-skill"])

    def test_existing_multifile_update_is_atomic_and_retryable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skill = skills / "x"
            skill.mkdir(parents=True)
            a = skill / "a.txt"
            b = skill / "b.txt"
            a.write_text("old-a\n")
            b.write_text("old-b\n")
            self.init_git(root, "skills/x/a.txt", "skills/x/b.txt")
            source = self.source("x")
            remote = {
                "x": {
                    "a.txt": (sync_skills.blob_sha(b"new-a\n"), "100644"),
                    "b.txt": (sync_skills.blob_sha(b"new-b\n"), "100644"),
                }
            }

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
                mock.patch.object(
                    sync_skills,
                    "fetch_blob",
                    side_effect=[b"new-a\n", RuntimeError("network failed")],
                ),
                redirect_stdout(io.StringIO()),
            ):
                index, report = sync_skills.plan(self.manifest(source))
                with self.assertRaises(RuntimeError):
                    sync_skills.apply_changes(index, report, prune=False)

            self.assertEqual(a.read_text(), "old-a\n")
            self.assertEqual(b.read_text(), "old-b\n")
            self.assertEqual(
                subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=root,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout,
                "",
            )

    def test_existing_update_preserves_keep_files_and_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skill = skills / "licensed"
            skill.mkdir(parents=True)
            payload = skill / "SKILL.md"
            license_file = skill / "LICENSE.txt"
            payload.write_text("old\n")
            license_file.write_text("local license\n")
            license_file.chmod(0o755)
            self.init_git(root, "skills/licensed/SKILL.md", "skills/licensed/LICENSE.txt")
            source = self.source("licensed")
            source["keep"] = {"licensed": ["LICENSE.txt"]}
            remote = {
                "licensed": {
                    "SKILL.md": (sync_skills.blob_sha(b"remote\n"), "100644")
                }
            }

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
                mock.patch.object(sync_skills, "fetch_blob", return_value=b"remote\n"),
                redirect_stdout(io.StringIO()),
            ):
                index, report = sync_skills.plan(self.manifest(source))
                self.assertEqual(report["missing_keep"], [])
                sync_skills.apply_changes(index, report, prune=False)

            self.assertEqual(payload.read_text(), "remote\n")
            self.assertEqual(license_file.read_text(), "local license\n")
            self.assertTrue(os.access(license_file, os.X_OK))

    def test_existing_update_rechecks_baseline_after_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skill = skills / "x"
            skill.mkdir(parents=True)
            payload = skill / "SKILL.md"
            payload.write_text("old\n")
            self.init_git(root, "skills/x/SKILL.md")
            source = self.source("x")
            remote = {
                "x": {"SKILL.md": (sync_skills.blob_sha(b"remote\n"), "100644")}
            }

            def late_local_edit(*_):
                payload.write_text("late local edit\n")
                return b"remote\n"

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
                mock.patch.object(sync_skills, "fetch_blob", side_effect=late_local_edit),
                redirect_stdout(io.StringIO()),
            ):
                index, report = sync_skills.plan(self.manifest(source))
                with self.assertRaises(SystemExit):
                    sync_skills.apply_changes(index, report, prune=False)

            self.assertEqual(payload.read_text(), "late local edit\n")

    def test_existing_update_rechecks_after_final_git_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skill = skills / "x"
            skill.mkdir(parents=True)
            payload = skill / "SKILL.md"
            payload.write_text("old\n")
            self.init_git(root, "skills/x/SKILL.md")
            source = self.source("x")
            remote = {
                "x": {"SKILL.md": (sync_skills.blob_sha(b"remote\n"), "100644")}
            }

            real_guard = sync_skills.git_worktree_issue
            calls = 0

            def edit_after_final_guard(name):
                nonlocal calls
                reason = real_guard(name)
                calls += 1
                if calls == 2 and reason is None:
                    payload.write_text("late local edit\n")
                return reason

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
                mock.patch.object(sync_skills, "fetch_blob", return_value=b"remote\n"),
                mock.patch.object(
                    sync_skills, "git_worktree_issue", side_effect=edit_after_final_guard
                ),
                redirect_stdout(io.StringIO()),
            ):
                index, report = sync_skills.plan(self.manifest(source))
                with self.assertRaises(SystemExit):
                    sync_skills.apply_changes(index, report, prune=False)

            self.assertEqual(calls, 2)
            self.assertEqual(payload.read_text(), "late local edit\n")
            self.assertFalse(any(p.name.startswith(".x.") for p in skills.iterdir()))

    def test_existing_update_keeps_recovery_copy_for_write_after_final_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skill = skills / "x"
            skill.mkdir(parents=True)
            payload = skill / "SKILL.md"
            payload.write_text("old\n")
            self.init_git(root, "skills/x/SKILL.md")
            source = self.source("x")
            remote = {
                "x": {"SKILL.md": (sync_skills.blob_sha(b"remote\n"), "100644")}
            }

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
            ):
                index, report = sync_skills.plan(self.manifest(source))

            real_local_state = sync_skills.local_state
            recovery_reads = 0
            open_old = payload.open("r+")

            def write_after_final_checksum(path):
                nonlocal recovery_reads
                state = real_local_state(path)
                if path.parent.name == ".sync-skills-recovery":
                    recovery_reads += 1
                    if recovery_reads == 2:
                        open_old.seek(0)
                        open_old.write("late unique edit\n")
                        open_old.truncate()
                        open_old.flush()
                return state

            try:
                with (
                    mock.patch.object(sync_skills, "ROOT", root),
                    mock.patch.object(sync_skills, "SKILLS", skills),
                    mock.patch.object(sync_skills, "fetch_blob", return_value=b"remote\n"),
                    mock.patch.object(sync_skills, "local_state", side_effect=write_after_final_checksum),
                    redirect_stdout(io.StringIO()),
                ):
                    sync_skills.apply_changes(index, report, prune=False)
            finally:
                open_old.close()

            backups = list((root / ".sync-skills-recovery").glob("x.update.*"))
            self.assertEqual(recovery_reads, 2)
            self.assertEqual(payload.read_text(), "remote\n")
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "SKILL.md").read_text(), "late unique edit\n")

    def test_update_rollback_preserves_writes_to_old_and_new_trees(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skill = skills / "x"
            skill.mkdir(parents=True)
            payload = skill / "SKILL.md"
            payload.write_text("old\n")
            self.init_git(root, "skills/x/SKILL.md")
            source = self.source("x")
            remote = {
                "x": {"SKILL.md": (sync_skills.blob_sha(b"remote\n"), "100644")}
            }

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
            ):
                index, report = sync_skills.plan(self.manifest(source))

            real_local_state = sync_skills.local_state
            recovery_reads = 0
            open_old = payload.open("r+")

            def write_both_before_final_checksum(path):
                nonlocal recovery_reads
                if path.parent.name == ".sync-skills-recovery":
                    recovery_reads += 1
                    if recovery_reads == 2:
                        open_old.seek(0)
                        open_old.write("late old-tree edit\n")
                        open_old.truncate()
                        open_old.flush()
                        (skills / "x" / "user-note.txt").write_text("late new-tree edit\n")
                return real_local_state(path)

            try:
                with (
                    mock.patch.object(sync_skills, "ROOT", root),
                    mock.patch.object(sync_skills, "SKILLS", skills),
                    mock.patch.object(sync_skills, "fetch_blob", return_value=b"remote\n"),
                    mock.patch.object(
                        sync_skills, "local_state", side_effect=write_both_before_final_checksum
                    ),
                    redirect_stdout(io.StringIO()),
                ):
                    with self.assertRaises(SystemExit):
                        sync_skills.apply_changes(index, report, prune=False)
            finally:
                open_old.close()

            recovery = root / ".sync-skills-recovery"
            rolled_back = list(recovery.glob("x.rollback-new.*"))
            self.assertEqual(recovery_reads, 2)
            self.assertEqual((skills / "x" / "SKILL.md").read_text(), "late old-tree edit\n")
            self.assertEqual(len(rolled_back), 1)
            self.assertEqual((rolled_back[0] / "SKILL.md").read_text(), "remote\n")
            self.assertEqual(
                (rolled_back[0] / "user-note.txt").read_text(), "late new-tree edit\n"
            )

    def test_adoption_rechecks_content_before_recording_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / "skills"
            skill = skills / "candidate"
            skill.mkdir(parents=True)
            payload = skill / "SKILL.md"
            payload.write_text("same\n")
            source = self.source()
            remote = {
                "candidate": {
                    "SKILL.md": (sync_skills.blob_sha(b"same\n"), "100644")
                }
            }

            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
                redirect_stdout(io.StringIO()),
            ):
                index, report = sync_skills.plan(self.manifest(source))
                payload.write_text("late local edit\n")
                with self.assertRaises(SystemExit):
                    sync_skills.apply_changes(index, report, prune=False)

            self.assertEqual(source["managed"], [])
            self.assertEqual(payload.read_text(), "late local edit\n")

    def test_nested_git_repository_blocks_managed_skill_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skill = skills / "x"
            skill.mkdir(parents=True)
            payload = skill / "SKILL.md"
            payload.write_text("old\n")
            self.init_git(root, "skills/x/SKILL.md")
            subprocess.run(["git", "init", "-q"], cwd=skill, check=True)
            remote = {
                "x": {"SKILL.md": (sync_skills.blob_sha(b"remote\n"), "100644")}
            }

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
            ):
                _, report = sync_skills.plan(self.manifest(self.source("x")))

            self.assertEqual(report["unsafe"], [("x", ".git 是嵌套 Git 元数据")])
            self.assertEqual(payload.read_text(), "old\n")

    def test_gitfile_worktree_metadata_blocks_managed_skill_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skill = skills / "x"
            skill.mkdir(parents=True)
            payload = skill / "SKILL.md"
            payload.write_text("old\n")
            self.init_git(root, "skills/x/SKILL.md")
            (skill / ".git").write_text("gitdir: /some/worktree/metadata\n")
            remote = {
                "x": {"SKILL.md": (sync_skills.blob_sha(b"remote\n"), "100644")}
            }

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
            ):
                _, report = sync_skills.plan(self.manifest(self.source("x")))

            self.assertEqual(report["unsafe"], [("x", ".git 是嵌套 Git 元数据")])
            self.assertTrue((skill / ".git").is_file())
            self.assertEqual(payload.read_text(), "old\n")

    def test_duplicate_skill_name_within_source_is_rejected(self):
        tree = {
            "tree": [
                {"type": "blob", "path": "a/x/SKILL.md"},
                {"type": "blob", "path": "b/x/SKILL.md"},
            ]
        }
        with self.assertRaises(SystemExit):
            sync_skills.skill_paths(tree, ["a", "b"])

    def test_add_rejects_duplicate_names_and_all_with_names_before_network(self):
        manifest = {"sources": [], "untracked": {}, "links": {}}
        cases = [
            mock.Mock(repo="example/repo", ref="HEAD", skills=["x", "x"], all=False),
            mock.Mock(repo="example/repo", ref="HEAD", skills=["x"], all=True),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / "skills"
            skills.mkdir()
            for args in cases:
                with (
                    self.subTest(args=args),
                    mock.patch.object(sync_skills, "SKILLS", skills),
                    mock.patch.object(sync_skills, "fetch_tree") as fetch_tree,
                ):
                    with self.assertRaises(SystemExit):
                        sync_skills.cmd_add(args, manifest, b"{}\n")
                    fetch_tree.assert_not_called()
        self.assertEqual(manifest["sources"], [])

    def test_prune_rechecks_immediately_before_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / "skills"
            retired = skills / "retired"
            retired.mkdir(parents=True)
            note = retired / "late-note.txt"
            source = self.source("retired")
            report = {
                "drift": [], "missing": [], "added": [], "gone": [("retired", source)],
                "adoptable": [],
            }

            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(
                    sync_skills,
                    "prune_blocker",
                    side_effect=[None, "刚出现本地文件"],
                ),
                redirect_stdout(io.StringIO()),
            ):
                note.write_text("preserve\n")
                with self.assertRaises(SystemExit):
                    sync_skills.apply_changes({}, report, prune=True)

            self.assertEqual(note.read_text(), "preserve\n")
            self.assertEqual(source["managed"], ["retired"])

    def test_prune_quarantines_and_restores_change_after_final_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            retired = skills / "retired"
            retired.mkdir(parents=True)
            (retired / "SKILL.md").write_text("clean\n")
            self.init_git(root, "skills/retired/SKILL.md")
            source = self.source("retired")
            manifest = self.manifest(source)

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value={}),
            ):
                index, report = sync_skills.plan(manifest)

            real_guard = sync_skills.prune_blocker
            calls = 0
            note = retired / "late-secret.txt"

            def write_after_final_guard(name):
                nonlocal calls
                reason = real_guard(name)
                calls += 1
                if calls == 2 and reason is None:
                    note.write_text("preserve\n")
                return reason

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "prune_blocker", side_effect=write_after_final_guard),
                redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(SystemExit):
                    sync_skills.apply_changes(index, report, prune=True)

            self.assertEqual(calls, 2)
            self.assertEqual(note.read_text(), "preserve\n")
            self.assertEqual(source["managed"], ["retired"])
            self.assertFalse(any(p.name.startswith(".retired.") for p in skills.iterdir()))

    def test_prune_keeps_recovery_copy_for_write_after_final_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            retired = skills / "retired"
            retired.mkdir(parents=True)
            payload = retired / "SKILL.md"
            payload.write_text("old\n")
            self.init_git(root, "skills/retired/SKILL.md")
            source = self.source("retired")

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value={}),
            ):
                index, report = sync_skills.plan(self.manifest(source))

            real_local_state = sync_skills.local_state
            recovery_reads = 0
            open_old = payload.open("r+")

            def write_after_final_checksum(path):
                nonlocal recovery_reads
                state = real_local_state(path)
                if path.parent.name == ".sync-skills-recovery":
                    recovery_reads += 1
                    if recovery_reads == 2:
                        open_old.seek(0)
                        open_old.write("late unique edit\n")
                        open_old.truncate()
                        open_old.flush()
                return state

            try:
                with (
                    mock.patch.object(sync_skills, "ROOT", root),
                    mock.patch.object(sync_skills, "SKILLS", skills),
                    mock.patch.object(sync_skills, "local_state", side_effect=write_after_final_checksum),
                    redirect_stdout(io.StringIO()),
                ):
                    sync_skills.apply_changes(index, report, prune=True)
            finally:
                open_old.close()

            backups = list((root / ".sync-skills-recovery").glob("retired.prune.*"))
            self.assertEqual(recovery_reads, 2)
            self.assertFalse(retired.exists())
            self.assertEqual(source["managed"], [])
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "SKILL.md").read_text(), "late unique edit\n")

    def test_sync_links_preserves_aliases_and_wrong_target_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            check = skills / "check"
            ui = skills / "ui"
            check.mkdir(parents=True)
            ui.mkdir()
            (check / "SKILL.md").write_text("check\n")
            (ui / "SKILL.md").write_text("ui\n")
            agent = root / "agent"
            agent.mkdir()
            alias = agent / "my-alias"
            wrong = agent / "check"
            alias.symlink_to(check)
            wrong.symlink_to(ui)
            manifest = self.manifest(
                self.source(), {"codex": {"dir": str(agent), "exclude": []}}
            )

            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                redirect_stdout(io.StringIO()),
            ):
                _, blocked = sync_skills.sync_links(manifest)

            self.assertEqual(blocked, 1)
            self.assertTrue(alias.is_symlink())
            self.assertEqual(alias.resolve(), check.resolve())
            self.assertTrue(wrong.is_symlink())
            self.assertEqual(wrong.resolve(), ui.resolve())

    def test_link_main_is_offline_creates_directories_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skill = skills / "check"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("local version\n")
            agent = root / "new-home" / "agent" / "skills"
            manifest = self.manifest(
                self.source("check"), {"codex": {"dir": str(agent), "exclude": []}}
            )
            manifest_path = root / "upstream.json"
            manifest_path.write_text(json.dumps(manifest))
            original = manifest_path.read_bytes()
            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "MANIFEST", manifest_path),
                mock.patch.object(sync_skills.shutil, "which", side_effect=AssertionError("gh dependency")),
                mock.patch.object(sync_skills, "gh", side_effect=AssertionError("network access")),
                mock.patch.object(sync_skills.sys, "argv", ["sync-skills.py", "--link"]),
                redirect_stdout(io.StringIO()),
            ):
                sync_skills.main()
                link_stat = (agent / "check").lstat()
                sync_skills.main()
            self.assertTrue((agent / "check").is_symlink())
            self.assertEqual((agent / "check").resolve(), skill.resolve())
            self.assertEqual((agent / "check").lstat().st_ino, link_stat.st_ino)
            self.assertEqual((skill / "SKILL.md").read_text(), "local version\n")
            self.assertEqual(manifest_path.read_bytes(), original)

    def test_link_dry_run_reports_missing_directory_without_creating_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skills.mkdir()
            agent = root / "missing" / "skills"
            manifest = self.manifest(
                self.source(), {"codex": {"dir": str(agent), "exclude": []}}
            )
            with mock.patch.object(sync_skills, "SKILLS", skills), redirect_stdout(io.StringIO()):
                self.assertEqual(sync_skills.sync_links(manifest, dry=True), (1, 0))
            self.assertFalse(agent.parent.exists())

    def test_link_main_quarantines_relative_owned_links_and_is_idempotent(self):
        for agent_path in [".claude/skills", ".codex/skills", ".pi/agent/skills"]:
            for target_exists in [False, True]:
                with self.subTest(agent=agent_path, target_exists=target_exists), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    skills = root / ".agents" / "skills"
                    skills.mkdir(parents=True)
                    target = skills / "retired"
                    if target_exists:
                        target.mkdir()
                        (target / "SKILL.md").write_text("keep excluded skill\n")
                    agent = root / agent_path
                    agent.mkdir(parents=True)
                    link = agent / "retired"
                    original_target = os.path.relpath(target, agent)
                    link.symlink_to(original_target)
                    original_inode = link.lstat().st_ino
                    manifest = self.manifest(
                        self.source(), {"agent": {"dir": str(agent), "exclude": ["retired"]}}
                    )
                    manifest_path = root / "upstream.json"
                    manifest_path.write_text(json.dumps(manifest))
                    with (
                        mock.patch.object(sync_skills, "SKILLS", skills),
                        mock.patch.object(sync_skills, "MANIFEST", manifest_path),
                        mock.patch.object(sync_skills, "gh", side_effect=AssertionError("network access")),
                        mock.patch.object(sync_skills.sys, "argv", ["sync-skills.py", "--link"]),
                        redirect_stdout(io.StringIO()),
                    ):
                        sync_skills.main()
                        sync_skills.main()
                    self.assertFalse(link.is_symlink())
                    recovered = [slot / "entry" for slot in (agent / ".sync-skills-recovery").glob("retired.*")]
                    self.assertEqual(len(recovered), 1)
                    held = recovered[0]
                    self.assertEqual(os.readlink(held), original_target)
                    self.assertEqual(held.lstat().st_ino, original_inode)
                    if target_exists:
                        self.assertEqual((target / "SKILL.md").read_text(), "keep excluded skill\n")
                    else:
                        self.assertFalse(target.exists())
                    held.rename(link)
                    self.assertEqual(link.resolve(), target.resolve())

    def test_link_quarantine_checks_replaced_relative_target_at_original_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "home" / "workspace"
            skills = root / "skills"
            skills.mkdir(parents=True)
            target = skills / "retired"
            agent = root / "agent"
            agent.mkdir()
            link = agent / "retired"
            link.symlink_to(os.path.relpath(target, agent))
            manifest = self.manifest(
                self.source(), {"codex": {"dir": str(agent), "exclude": []}}
            )
            real_rename = sync_skills.rename_noreplace
            replaced_target = None

            def replace_before_quarantine(src, dst):
                nonlocal replaced_target
                # This replacement looks owned only if resolved at the recovery path.
                replaced_target = os.path.relpath(target, dst.parent)
                self.assertNotEqual((agent / replaced_target).resolve(), target.resolve())
                link.unlink()
                link.symlink_to(replaced_target)
                return real_rename(src, dst)

            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "rename_noreplace", side_effect=replace_before_quarantine),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(sync_skills.sync_links(manifest), (0, 1))
            recovered = [slot / "entry" for slot in (agent / ".sync-skills-recovery").glob("retired.*")]
            self.assertEqual(len(recovered), 1)
            self.assertEqual(os.readlink(recovered[0]), replaced_target)
            self.assertFalse(link.is_symlink())

    def test_link_preserves_external_directories_but_blocks_name_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skill = skills / "check"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("upstream\n")
            agent = root / "agent"
            synced = agent / "synced"
            synced.mkdir(parents=True)
            (synced / "local.txt").write_text("keep\n")
            manifest = self.manifest(
                self.source("check"), {"codex": {"dir": str(agent), "exclude": []}}
            )
            with mock.patch.object(sync_skills, "SKILLS", skills), redirect_stdout(io.StringIO()):
                self.assertEqual(sync_skills.sync_links(manifest), (1, 0))
                (agent / "check").unlink()
                (agent / "check").mkdir()
                (agent / "check" / "SKILL.md").write_text("unique\n")
                self.assertEqual(sync_skills.sync_links(manifest), (0, 1))
            self.assertEqual((synced / "local.txt").read_text(), "keep\n")
            self.assertEqual((agent / "check" / "SKILL.md").read_text(), "unique\n")

    def test_link_blocks_unusable_root_and_external_broken_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skills.mkdir()
            agent = root / "agent"
            manifest = self.manifest(
                self.source(), {"codex": {"dir": str(agent), "exclude": []}}
            )
            agent.write_text("keep\n")
            with mock.patch.object(sync_skills, "SKILLS", skills), redirect_stdout(io.StringIO()):
                self.assertEqual(sync_skills.sync_links(manifest), (0, 1))
                self.assertEqual(agent.read_text(), "keep\n")
                agent.unlink()
                agent.symlink_to(root / "missing")
                self.assertEqual(sync_skills.sync_links(manifest), (0, 1))
                self.assertTrue(agent.is_symlink())
                agent.unlink()
                agent.mkdir()
                broken = agent / "external"
                broken.symlink_to(root / "missing")
                self.assertEqual(sync_skills.sync_links(manifest), (0, 1))
                self.assertTrue(broken.is_symlink())

    def test_cache_noise_is_ignored_only_in_report_not_write_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skill = skills / "check"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_bytes(b"same\n")
            self.init_git(root, "skills")
            cache = skill / "__pycache__" / "module.pyc"
            cache.parent.mkdir()
            cache.write_bytes(b"cache")
            manifest = self.manifest(self.source("check"))
            remote = {"check": {"SKILL.md": (sync_skills.blob_sha(b"same\n"), "100644")}}
            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value=remote),
            ):
                _, report = sync_skills.plan(manifest)
                self.assertEqual(report["drift"], [])
                self.assertIn("__pycache__/module.pyc", sync_skills.local_state(skill))
                self.assertIsNotNone(sync_skills.git_worktree_issue("check"))
                (skill / "notes.txt").write_text("unique\n")
                _, report = sync_skills.plan(manifest)
                self.assertEqual([d[2] for d in report["drift"]], ["notes.txt"])
                remote["check"]["__pycache__/module.pyc"] = (sync_skills.blob_sha(b"upstream"), "100644")
                _, report = sync_skills.plan(manifest)
                self.assertEqual({d[2] for d in report["drift"]}, {"notes.txt", "__pycache__/module.pyc"})
                cache.unlink()
                cache.symlink_to(root / "outside")
                _, report = sync_skills.plan(manifest)
                self.assertTrue(report["unsafe"])

    def test_sync_links_restores_concurrent_file_replacing_owned_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            check = skills / "check"
            check.mkdir(parents=True)
            (check / "SKILL.md").write_text("check\n")
            agent = root / "agent"
            agent.mkdir()
            link = agent / "check"
            link.symlink_to(check)
            manifest = self.manifest(
                self.source(), {"codex": {"dir": str(agent), "exclude": ["check"]}}
            )

            realpath = os.path.realpath
            replaced = False

            def replace_after_ownership_check(path):
                nonlocal replaced
                result = realpath(path)
                if Path(path) == link and not replaced:
                    replaced = True
                    link.unlink()
                    link.write_text("unique concurrent file\n")
                return result

            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills.os.path, "realpath", side_effect=replace_after_ownership_check),
                redirect_stdout(io.StringIO()),
            ):
                _, blocked = sync_skills.sync_links(manifest)

            self.assertTrue(replaced)
            self.assertEqual(blocked, 1)
            recovered = list((agent / ".sync-skills-recovery").glob("check.*/entry"))
            self.assertEqual(len(recovered), 1)
            self.assertEqual(recovered[0].read_text(), "unique concurrent file\n")

    def test_source_without_managed_inventory_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            skills = Path(tmp) / "skills"
            skills.mkdir()
            source = {"repo": "example/repo", "ref": "HEAD", "roots": ["skills"]}
            with (
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "discover", return_value={}),
            ):
                _, report = sync_skills.plan(self.manifest(source))

            self.assertEqual(
                report["manifest_errors"],
                ["example/repo 缺少合法的 managed 列表"],
            )

    def test_main_persists_new_registration_and_builds_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skills.mkdir()
            claude = root / "claude"
            codex = root / "codex"
            claude.mkdir()
            codex.mkdir()
            source = self.source()
            manifest = self.manifest(
                source,
                {
                    "claude": {"dir": str(claude), "exclude": []},
                    "codex": {"dir": str(codex), "exclude": []},
                },
            )
            manifest_path = root / "upstream.json"
            manifest_path.write_text(json.dumps(manifest))
            remote = {
                "new-skill": {
                    "SKILL.md": (sync_skills.blob_sha(b"new\n"), "100644")
                }
            }

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "MANIFEST", manifest_path),
                mock.patch.object(sync_skills, "discover", return_value=remote),
                mock.patch.object(sync_skills, "fetch_blob", return_value=b"new\n"),
                mock.patch.object(sync_skills.shutil, "which", return_value="/usr/bin/gh"),
                mock.patch.object(sync_skills.sys, "argv", ["sync-skills.py", "--apply"]),
                redirect_stdout(io.StringIO()),
            ):
                sync_skills.main()

            saved = json.loads(manifest_path.read_text())
            self.assertEqual(saved["sources"][0]["managed"], ["new-skill"])
            self.assertEqual((skills / "new-skill" / "SKILL.md").read_bytes(), b"new\n")
            self.assertEqual((claude / "new-skill").resolve(), (skills / "new-skill").resolve())
            self.assertEqual((codex / "new-skill").resolve(), (skills / "new-skill").resolve())

    def test_main_does_not_overwrite_concurrent_manifest_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skills.mkdir()
            source = self.source()
            manifest = self.manifest(source)
            manifest_path = root / "upstream.json"
            manifest_path.write_text(json.dumps(manifest))
            remote = {
                "new-skill": {
                    "SKILL.md": (sync_skills.blob_sha(b"new\n"), "100644")
                }
            }

            def concurrent_manifest_edit(*_):
                concurrent = json.loads(manifest_path.read_text())
                concurrent["untracked"]["concurrent-user-entry"] = "preserve me"
                manifest_path.write_text(json.dumps(concurrent))
                return b"new\n"

            with (
                mock.patch.object(sync_skills, "ROOT", root),
                mock.patch.object(sync_skills, "SKILLS", skills),
                mock.patch.object(sync_skills, "MANIFEST", manifest_path),
                mock.patch.object(sync_skills, "discover", return_value=remote),
                mock.patch.object(sync_skills, "fetch_blob", side_effect=concurrent_manifest_edit),
                mock.patch.object(sync_skills.shutil, "which", return_value="/usr/bin/gh"),
                mock.patch.object(sync_skills.sys, "argv", ["sync-skills.py", "--apply"]),
                redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(SystemExit):
                    sync_skills.main()

            saved = json.loads(manifest_path.read_text())
            self.assertEqual(saved["untracked"]["concurrent-user-entry"], "preserve me")
            self.assertEqual(saved["sources"][0]["managed"], [])
            self.assertEqual((skills / "new-skill" / "SKILL.md").read_text(), "new\n")

    def test_manifest_cas_preserves_late_write_to_open_old_inode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skills.mkdir()
            manifest_path = root / "upstream.json"
            original = b'{"value": "old"}\n'
            manifest_path.write_bytes(original)
            open_old = manifest_path.open("r+")

            real_link = os.link

            def late_write_then_publish(src, dst):
                open_old.seek(0)
                open_old.write('{"value": "late unique edit"}\n')
                open_old.truncate()
                open_old.flush()
                return real_link(src, dst)

            try:
                with (
                    mock.patch.object(sync_skills, "SKILLS", skills),
                    mock.patch.object(sync_skills, "MANIFEST", manifest_path),
                    mock.patch.object(sync_skills.os, "link", side_effect=late_write_then_publish),
                    redirect_stdout(io.StringIO()),
                ):
                    sync_skills.save_manifest({"value": "new"}, original)
            finally:
                open_old.close()

            backups = list((root / ".sync-skills-recovery").glob("upstream.json.manifest.*"))
            self.assertEqual(json.loads(manifest_path.read_text()), {"value": "new"})
            self.assertEqual(len(backups), 1)
            self.assertEqual(
                json.loads(backups[0].read_text()), {"value": "late unique edit"}
            )

    def test_manifest_cas_never_restores_over_second_concurrent_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            skills.mkdir()
            manifest_path = root / "upstream.json"
            original = b'{"value": "old"}\n'
            manifest_path.write_bytes(original)
            open_old = manifest_path.open("r+")
            real_read_bytes = Path.read_bytes
            injected = False

            def inject_two_writers(path):
                nonlocal injected
                if path.parent.name == ".sync-skills-recovery" and not injected:
                    injected = True
                    open_old.seek(0)
                    open_old.write('{"value": "late old fd"}\n')
                    open_old.truncate()
                    open_old.flush()
                    manifest_path.write_text('{"value": "second writer unique"}\n')
                return real_read_bytes(path)

            try:
                with (
                    mock.patch.object(sync_skills, "SKILLS", skills),
                    mock.patch.object(sync_skills, "MANIFEST", manifest_path),
                    mock.patch.object(Path, "read_bytes", new=inject_two_writers),
                    redirect_stdout(io.StringIO()),
                ):
                    with self.assertRaises(SystemExit):
                        sync_skills.save_manifest({"value": "new"}, original)
            finally:
                open_old.close()

            backups = list((root / ".sync-skills-recovery").glob("upstream.json.manifest.*"))
            self.assertTrue(injected)
            self.assertEqual(
                json.loads(manifest_path.read_text()), {"value": "second writer unique"}
            )
            self.assertEqual(len(backups), 1)
            self.assertEqual(json.loads(backups[0].read_text()), {"value": "late old fd"})


if __name__ == "__main__":
    unittest.main()
