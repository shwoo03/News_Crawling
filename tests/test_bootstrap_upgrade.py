from tests.test_support import *


class BootstrapIntegrationTests(unittest.TestCase):
    """End-to-end: bootstrap a new project into a tmpdir and verify it.

    This is the single most valuable test in the file: it exercises copy
    semantics, profile seeding, knowledge seeding, and then runs the full
    verifier against the produced tree. A regression in any of those steps
    fails this one test.
    """

    def test_new_project_then_verify(self) -> None:
        tmp = _make_external_tmpdir_or_skip(self, "skeleton-smoke")
        fake_clone = (
            REPO_ROOT
            / "runtime"
            / "external-repos"
            / "test.invalid"
            / "example__service"
        )
        try:
            fake_clone.mkdir(parents=True, exist_ok=True)
            (fake_clone / "README.md").write_text(
                "# fake external repo\n", encoding="utf-8"
            )
            target = tmp / "proj"
            # bootstrap
            result = _run(
                [
                    str(SCRIPTS / "bootstrap" / "new-project.py"),
                    "--name",
                    "smoke",
                    "--target",
                    str(target),
                    "--domain",
                    "test",
                    "--stack",
                    "python",
                    "--owner",
                    "tester",
                    "--profile",
                    "cli",
                ]
            )
            self.assertEqual(
                result.returncode,
                0,
                f"new-project failed:\nstdout={result.stdout}\nstderr={result.stderr}",
            )
            self.assertTrue((target / "CLAUDE.md").exists())
            self.assertTrue((target / "docs" / "PROJECT_PROFILE.md").exists())
            self.assertTrue((target / "docs" / "REFERENCE_REVIEW.template.md").exists())
            self.assertTrue((target / "docs" / "RUNTIME_STARTUP.template.md").exists())
            self.assertTrue((target / ".codex" / "skills").is_dir())
            self.assertTrue((target / ".claude" / "skills").is_dir())
            self.assertTrue((target / "runtime" / "install-state.jsonl").exists())
            self.assertTrue((target / "runtime" / "skill-usage.jsonl").exists())
            self.assertTrue((target / "runtime" / "skill-lifecycle.jsonl").exists())
            self.assertTrue((target / "runtime" / "session-snapshot.json").exists())
            self.assertTrue((target / "runtime" / "external-repos" / "README.md").exists())
            self.assertFalse(
                (target / "runtime" / "external-repos" / "test.invalid").exists(),
                "bootstrap must not copy external repo clones into new projects",
            )

            # verify the produced project
            verify = _run(
                [
                    str(SCRIPTS / "verify-skeleton.py"),
                    "--root",
                    str(target),
                    "--skip-wiki-lint",
                ]
            )
            self.assertEqual(
                verify.returncode,
                0,
                f"verify-skeleton on bootstrapped project failed:\n"
                f"stdout={verify.stdout}\nstderr={verify.stderr}",
            )
            parity = _run([str(SCRIPTS / "verify-parity.py"), "--root", str(target)])
            self.assertEqual(parity.returncode, 0, parity.stdout + parity.stderr)
            install_state = (target / "runtime" / "install-state.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertGreaterEqual(len(install_state), 2)
            bootstrap_record = json.loads(install_state[0])
            self.assertEqual(bootstrap_record["requested_profile"], "cli")
            self.assertIn("cli", bootstrap_record["selected_components"])
        finally:
            shutil.rmtree(fake_clone.parent, ignore_errors=True)
            shutil.rmtree(tmp, ignore_errors=True)

class UpgradeFromSkeletonTests(unittest.TestCase):
    """Existing projects must receive safe missing skeleton files without
    clobbering project-owned or locally edited files."""

    SCRIPT = SCRIPTS / "upgrade-from-skeleton.py"

    def test_dry_run_reports_missing_safe_files_and_risky_updates(self) -> None:
        tmp = _make_external_tmpdir_or_skip(self, "skeleton-upgrade-dry-run")
        try:
            target = tmp / "proj"
            (target / "docs").mkdir(parents=True)
            (target / "AGENTS.md").write_text("# project custom agent rules\n", encoding="utf-8")

            result = _run(
                [str(self.SCRIPT), "--target", str(target), "--json"],
                cwd=REPO_ROOT,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"upgrade dry-run failed:\nstdout={result.stdout}\nstderr={result.stderr}",
            )
            payload = json.loads(result.stdout)
            by_path = {item["path"]: item for item in payload["actions"]}
            self.assertEqual(by_path["docs/REFERENCE_REVIEW.template.md"]["action"], "add")
            self.assertEqual(by_path["docs/REFERENCE_REVIEW.template.md"]["safety"], "safe")
            self.assertEqual(by_path["AGENTS.md"]["action"], "update_available")
            self.assertEqual(by_path["AGENTS.md"]["safety"], "risky")
            self.assertFalse(
                (target / "docs" / "REFERENCE_REVIEW.template.md").exists(),
                "dry-run must not copy files",
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_safe_only_apply_copies_missing_templates_without_overwrite(self) -> None:
        tmp = _make_external_tmpdir_or_skip(self, "skeleton-upgrade-safe-apply")
        try:
            target = tmp / "proj"
            target.mkdir(parents=True)
            custom_agents = "# project custom agent rules\n"
            (target / "AGENTS.md").write_text(custom_agents, encoding="utf-8")

            result = _run(
                [
                    str(self.SCRIPT),
                    "--target",
                    str(target),
                    "--apply",
                    "--safe-only",
                    "--json",
                ],
                cwd=REPO_ROOT,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"upgrade safe apply failed:\nstdout={result.stdout}\nstderr={result.stderr}",
            )
            self.assertEqual((target / "AGENTS.md").read_text(encoding="utf-8"), custom_agents)
            self.assertTrue((target / "docs" / "REFERENCE_REVIEW.template.md").exists())
            self.assertTrue((target / "docs" / "RUNTIME_STARTUP.template.md").exists())
            self.assertTrue((target / "runtime" / "activity-log.jsonl").exists())
            payload = json.loads(result.stdout)
            applied = {
                item["path"]
                for item in payload["actions"]
                if item["applied"]
            }
            self.assertIn("docs/REFERENCE_REVIEW.template.md", applied)
            self.assertNotIn("AGENTS.md", applied)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

class SkeletonDoctorTests(unittest.TestCase):
    """`skeleton-doctor.py` is the operator-facing readiness diagnostic.

    It must stay read-only, emit parseable JSON for automation, and fail fast
    on invalid roots.
    """

    SCRIPT = SCRIPTS / "skeleton-doctor.py"

    def test_current_skeleton_doctor_passes(self) -> None:
        result = _run([str(self.SCRIPT), "--root", str(REPO_ROOT)], cwd=REPO_ROOT)
        self.assertEqual(
            result.returncode,
            0,
            f"doctor failed:\nstdout={result.stdout}\nstderr={result.stderr}",
        )
        self.assertIn("Skeleton Doctor", result.stdout)
        self.assertIn("verify-skeleton", result.stdout)

    def test_json_output_is_parseable(self) -> None:
        result = _run(
            [str(self.SCRIPT), "--root", str(REPO_ROOT), "--format", "json"],
            cwd=REPO_ROOT,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"doctor json failed:\nstdout={result.stdout}\nstderr={result.stderr}",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["root"], str(REPO_ROOT.resolve()))
        self.assertTrue(payload["checks"])

    def test_bad_root_exits_two(self) -> None:
        result = _run(
            [str(self.SCRIPT), "--root", str(REPO_ROOT / "does-not-exist")],
            cwd=REPO_ROOT,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("root not a directory", result.stderr)
