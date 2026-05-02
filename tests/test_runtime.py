from tests.test_support import *


class RotateActivityLogDryRunTests(unittest.TestCase):
    """`rotate-activity-log.py` without --apply must be a safe no-op that
    prints a plan and exits 0. This is our guard against the planner
    crashing on a real project's logs."""

    def test_dry_run_exits_zero(self) -> None:
        result = _run(
            [str(SCRIPTS / "rotate-activity-log.py")],
            cwd=REPO_ROOT,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"rotate dry-run failed:\nstdout={result.stdout}\nstderr={result.stderr}",
        )
        self.assertIn("dry-run", result.stdout)

class PostToolUseLogTests(unittest.TestCase):
    """`scripts/hooks/post-tool-use-log.py` is invoked by the Claude Code harness
    with JSON on stdin. Two failure modes have burned us before and are cheap to
    pin down here:

    1. A UTF-8 BOM leading the stdin payload used to make json.loads raise.
    2. A `--log` path outside the project root would silently write to an
       attacker-controlled location. Must be refused with a non-zero exit.
    """

    HOOK = SCRIPTS / "hooks" / "post-tool-use-log.py"

    def test_bom_prefixed_stdin_is_accepted(self) -> None:
        # The --log containment check rejects paths outside the repo root
        # (see test_log_outside_root_is_refused), so the scratch dir for this
        # test must live inside REPO_ROOT. Use runtime/ (the skeleton's own
        # throwaway area) and clean up the file in a try/finally so a failure
        # mid-test does not leave junk behind.
        scratch_dir = REPO_ROOT / "runtime"
        scratch_dir.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix="skeleton-bom-", suffix=".jsonl", dir=str(scratch_dir), delete=False
        ) as tmpfile:
            log_path = Path(tmpfile.name)
        try:
            # Start from an empty file so we assert exactly 1 appended line.
            log_path.write_bytes(b"")
            # BOM + minimal well-formed event payload.
            payload = b"\xef\xbb\xbf" + b'{"tool":"Bash","status":"completed"}'
            result = _run_bytes(
                [str(self.HOOK), "--log", str(log_path), "--project", "bom-smoke"],
                stdin_bytes=payload,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"BOM-prefixed stdin rejected:\n"
                f"stdout={result.stdout!r}\nstderr={result.stderr!r}",
            )
            self.assertTrue(log_path.exists(), "log file was not written")
            written = log_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(written), 1, f"expected 1 line, got {written!r}")
        finally:
            lock_path = log_path.parent / f".{log_path.stem}.rotation.lock"
            try:
                log_path.unlink()
            except FileNotFoundError:
                pass
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

    def test_log_outside_root_is_refused(self) -> None:
        # Absolute path outside the repo root must be rejected; the script
        # should never open a write handle to an arbitrary filesystem location.
        outside = Path.home() / f".skeleton-escape-{uuid.uuid4().hex}" / "escape.jsonl"
        result = _run_bytes(
            [str(self.HOOK), "--log", str(outside), "--project", "escape-smoke"],
            stdin_bytes=b'{"tool":"Bash"}',
        )
        self.assertNotEqual(
            result.returncode,
            0,
            f"--log outside root was accepted (should have been refused):\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}",
        )
        self.assertFalse(
            outside.exists(),
            f"script wrote to forbidden path {outside}",
        )

    def test_long_summary_is_written_to_sidecar_and_searchable(self) -> None:
        scratch_dir = REPO_ROOT / "runtime"
        scratch_dir.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix="skeleton-sidecar-", suffix=".jsonl", dir=str(scratch_dir), delete=False
        ) as tmpfile:
            log_path = Path(tmpfile.name)
        created_sidecar: Path | None = None
        try:
            log_path.write_bytes(b"")
            payload = {"tool": "Bash", "status": "completed", "summary": "alpha " + ("needle " * 200)}
            result = _run_bytes(
                [str(self.HOOK), "--log", str(log_path), "--project", "sidecar-smoke", "--max-summary-chars", "40"],
                stdin_bytes=json.dumps(payload).encode("utf-8"),
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            entry = json.loads(log_path.read_text(encoding="utf-8").strip())
            sidecar = entry["tool_call"]["sidecar_path"]
            created_sidecar = REPO_ROOT / sidecar
            self.assertTrue(created_sidecar.is_file())
            self.assertTrue(entry["tool_call"]["truncated"])

            found = _run(
                [
                    str(SCRIPTS / "search-activity-log.py"),
                    "--log",
                    str(log_path),
                    "--sidecar-contains",
                    "needle",
                ]
            )
            self.assertEqual(found.returncode, 0, found.stdout + found.stderr)
            self.assertIn(sidecar, found.stdout)
        finally:
            lock_path = log_path.parent / f".{log_path.stem}.rotation.lock"
            try:
                log_path.unlink()
            except FileNotFoundError:
                pass
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
            if created_sidecar is not None:
                try:
                    created_sidecar.unlink()
                except FileNotFoundError:
                    pass

class ResumeReadinessTests(unittest.TestCase):
    """`resume-readiness.py` verifies handoff and ledgers line up for the next agent."""

    SCRIPT = SCRIPTS / "resume-readiness.py"

    def _make_root(
        self,
        *,
        handoff_ts: str = "2026-04-30T09:00:00Z",
        activity_ts: str = "2026-04-30T08:59:00Z",
        handoff_event_ts: str = "2026-04-30T09:00:00Z",
        evidence_ts: str = "2026-04-30T08:58:00Z",
        evidence_outcome: str = "genuine_success",
        include_resume_prompt: bool = True,
    ) -> Path:
        tmp = REPO_ROOT / "runtime" / f"resume-readiness-{uuid.uuid4().hex}"
        (tmp / "runtime" / "state").mkdir(parents=True)
        sections = [
            "# Session Handoff",
            "",
            "## Last Updated",
            "",
            handoff_ts,
            "",
            "## Current Task",
            "",
            "Resume smoke.",
            "",
            "## Last Completed",
            "",
            "- Prior task.",
            "",
            "## Validation",
            "",
            "- Checked.",
            "",
            "## Recommended Next Step",
            "",
            "Run the next agent step.",
            "",
            "## Open Questions / Blockers",
            "",
            "- None.",
            "",
        ]
        if include_resume_prompt:
            sections.extend(["## Resume Prompt", "", "Continue from this smoke state.", ""])
        (tmp / "runtime" / "state" / "session-handoff.md").write_text("\n".join(sections), encoding="utf-8")
        activity = [
            {"ts": handoff_event_ts, "phase": "session", "action": "handoff_saved", "project": "smoke", "data": {}},
            {"ts": activity_ts, "phase": "implementation", "action": "some_work", "project": "smoke", "data": {}},
        ]
        (tmp / "runtime" / "activity-log.jsonl").write_text(
            "".join(json.dumps(item, separators=(",", ":")) + "\n" for item in activity),
            encoding="utf-8",
        )
        evidence = {
            "ts": evidence_ts,
            "goal": "smoke",
            "changed_paths": ["docs/example.md"],
            "validations": [{"name": "verify", "status": "OK"}],
            "outcome": evidence_outcome,
        }
        (tmp / "runtime" / "completion-evidence.jsonl").write_text(
            json.dumps(evidence, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        return tmp

    def test_ready_root_passes_strict_json(self) -> None:
        tmp = self._make_root()
        try:
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--strict", "--format", "json"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["summary"]["ERROR"], 0)
            self.assertEqual(payload["summary"]["WARN"], 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_activity_newer_than_handoff_fails_strict(self) -> None:
        tmp = self._make_root(activity_ts="2026-04-30T09:01:00Z")
        try:
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--strict", "--format", "json"])
            self.assertEqual(result.returncode, 1)
            rules = {finding["check"] for finding in json.loads(result.stdout)["findings"]}
            self.assertIn("activity_log_newer_than_handoff", rules)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_completion_evidence_newer_than_handoff_fails_strict(self) -> None:
        tmp = self._make_root(evidence_ts="2026-04-30T09:01:00Z")
        try:
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--strict", "--format", "json"])
            self.assertEqual(result.returncode, 1)
            rules = {finding["check"] for finding in json.loads(result.stdout)["findings"]}
            self.assertIn("completion_evidence_newer_than_handoff", rules)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_partial_completion_evidence_warns_and_fails_strict(self) -> None:
        tmp = self._make_root(evidence_outcome="partial_progress")
        try:
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--strict", "--format", "json"])
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            rules = {finding["check"] for finding in payload["findings"]}
            self.assertIn("completion_evidence_not_genuine_success", rules)
            self.assertEqual(payload["latest"]["completion_evidence"]["latest_outcome"], "partial_progress")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_missing_handoff_section_fails(self) -> None:
        tmp = self._make_root(include_resume_prompt=False)
        try:
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--strict", "--format", "json"])
            self.assertEqual(result.returncode, 1)
            rules = {finding["check"] for finding in json.loads(result.stdout)["findings"]}
            self.assertIn("handoff_section_missing", rules)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

class AgentAutonomyTests(unittest.TestCase):
    """`agent-autonomy-check.py` keeps routine execution assigned to agents."""

    SCRIPT = SCRIPTS / "agent-autonomy-check.py"

    def test_current_docs_pass_strict(self) -> None:
        result = _run([str(self.SCRIPT), "--root", str(REPO_ROOT), "--strict", "--format", "json"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["findings"], [])

    def test_user_run_instruction_is_flagged(self) -> None:
        scratch = REPO_ROOT / "docs" / "_tmp_agent_autonomy_smoke.md"
        scratch.write_text(
            "# bad\n\n사용자가 직접 python scripts/example.py 명령을 실행합니다.\n",
            encoding="utf-8",
        )
        try:
            result = _run([str(self.SCRIPT), "--root", str(REPO_ROOT), "--strict"])
            self.assertEqual(result.returncode, 1)
            self.assertIn("user_runs_command", result.stdout)
        finally:
            scratch.unlink(missing_ok=True)

class CompletionEvidenceTests(unittest.TestCase):
    """Completion evidence is append-only and agent-owned."""

    SCRIPT = SCRIPTS / "completion-evidence.py"

    def test_add_list_check_round_trip(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"completion-evidence-{uuid.uuid4().hex}"
        try:
            tmp.mkdir(parents=True)
            add = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "add",
                    "--goal",
                    "smoke closeout",
                    "--changed-path",
                    "docs/example.md",
                    "--validation",
                    '{"name":"verify","status":"OK"}',
                    "--json",
                ]
            )
            self.assertEqual(add.returncode, 0, add.stderr)
            record = json.loads(add.stdout)
            self.assertEqual(record["goal"], "smoke closeout")

            listing = _run([str(self.SCRIPT), "--root", str(tmp), "list", "--json"])
            self.assertEqual(listing.returncode, 0, listing.stderr)
            self.assertEqual(len(json.loads(listing.stdout)), 1)

            check = _run([str(self.SCRIPT), "--root", str(tmp), "check"])
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_genuine_success_rejects_failed_validation(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"completion-evidence-fail-{uuid.uuid4().hex}"
        try:
            tmp.mkdir(parents=True)
            add = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "add",
                    "--goal",
                    "bad closeout",
                    "--changed-path",
                    ".",
                    "--validation",
                    '{"name":"unit","status":"FAIL"}',
                    "--outcome",
                    "genuine_success",
                ]
            )
            self.assertEqual(add.returncode, 1)
            self.assertIn("requires all validations passing", add.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_genuine_success_rejects_warn_validation(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"completion-evidence-warn-{uuid.uuid4().hex}"
        try:
            tmp.mkdir(parents=True)
            add = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "add",
                    "--goal",
                    "warn closeout",
                    "--changed-path",
                    ".",
                    "--validation",
                    '{"name":"quality-gate","status":"WARN"}',
                    "--outcome",
                    "genuine_success",
                ]
            )
            self.assertEqual(add.returncode, 1)
            self.assertIn("OK/PASS", add.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_partial_progress_warn_requires_risk_or_next_action(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"completion-evidence-partial-{uuid.uuid4().hex}"
        try:
            tmp.mkdir(parents=True)
            bad = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "add",
                    "--goal",
                    "partial closeout",
                    "--changed-path",
                    ".",
                    "--validation",
                    '{"name":"quality-gate","status":"SKIP"}',
                    "--outcome",
                    "partial_progress",
                ]
            )
            self.assertEqual(bad.returncode, 1)
            good = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "add",
                    "--goal",
                    "partial closeout",
                    "--changed-path",
                    ".",
                    "--validation",
                    '{"name":"quality-gate","status":"SKIP"}',
                    "--outcome",
                    "partial_progress",
                    "--next-action",
                    "add golden coverage",
                ]
            )
            self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_legacy_blocked_failed_outcomes_are_rejected(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"completion-evidence-legacy-{uuid.uuid4().hex}"
        try:
            tmp.mkdir(parents=True)
            for outcome in ("blocked", "failed"):
                result = _run([
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "add",
                    "--goal",
                    "legacy outcome",
                    "--changed-path",
                    ".",
                    "--validation",
                    '{"name":"verify","status":"OK"}',
                    "--outcome",
                    outcome,
                ])
                self.assertNotEqual(result.returncode, 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

class TaskCloseoutTests(unittest.TestCase):
    """`task-closeout.py` selects checks and can record completion evidence."""

    SCRIPT = SCRIPTS / "task-closeout.py"

    def test_docs_profile_runs_read_only_checks(self) -> None:
        result = _run(
            [
                str(self.SCRIPT),
                "--root",
                str(REPO_ROOT),
                "--profile",
                "docs",
                "--goal",
                "docs smoke",
                "--changed-path",
                "docs/OPERATING_LOOP.md",
                "--no-record",
                "--format",
                "json",
            ]
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        names = {check["name"] for check in payload["checks"]}
        self.assertIn("verify-skeleton", names)
        self.assertIn("agent-autonomy-check", names)
        self.assertFalse(payload["recorded"])

    def test_record_writes_completion_evidence_in_target_root(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"task-closeout-{uuid.uuid4().hex}"
        try:
            (tmp / "scripts").mkdir(parents=True)
            (tmp / "docs").mkdir()
            (tmp / "scripts" / "verify-skeleton.py").write_text(
                "import sys\nprint('ok')\nraise SystemExit(0)\n",
                encoding="utf-8",
            )
            (tmp / "scripts" / "agent-autonomy-check.py").write_text(
                "import sys\nprint('ok')\nraise SystemExit(0)\n",
                encoding="utf-8",
            )
            shutil.copyfile(SCRIPTS / "completion-evidence.py", tmp / "scripts" / "completion-evidence.py")

            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "--profile",
                    "docs",
                    "--goal",
                    "record smoke",
                    "--changed-path",
                    "docs/example.md",
                    "--record",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["recorded"])
            self.assertTrue((tmp / "runtime" / "completion-evidence.jsonl").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_record_with_skill_writes_skill_usage(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"task-closeout-skill-{uuid.uuid4().hex}"
        try:
            (tmp / "scripts").mkdir(parents=True)
            (tmp / "docs").mkdir()
            (tmp / "scripts" / "verify-skeleton.py").write_text(
                "import sys\nprint('ok')\nraise SystemExit(0)\n",
                encoding="utf-8",
            )
            (tmp / "scripts" / "agent-autonomy-check.py").write_text(
                "import sys\nprint('ok')\nraise SystemExit(0)\n",
                encoding="utf-8",
            )
            shutil.copyfile(SCRIPTS / "completion-evidence.py", tmp / "scripts" / "completion-evidence.py")
            shutil.copyfile(SCRIPTS / "skill-lifecycle.py", tmp / "scripts" / "skill-lifecycle.py")

            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "--profile",
                    "docs",
                    "--goal",
                    "skill record smoke",
                    "--changed-path",
                    "docs/example.md",
                    "--record",
                    "--skill",
                    "verification-loop",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["skills"], ["verification-loop"])
            records = (tmp / "runtime" / "skill-usage.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(records), 1)
            record = json.loads(records[0])
            self.assertEqual(record["skill"], "verification-loop")
            self.assertEqual(record["outcome"], "success")
            self.assertTrue(record["run_id"].startswith("closeout-"))
            self.assertEqual(record["evidence_ref"], "runtime/completion-evidence.jsonl")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

class ReviewQueueTests(unittest.TestCase):
    """Human review queue stores unresolved decisions as JSONL events."""

    SCRIPT = SCRIPTS / "review-queue.py"

    def test_add_list_resolve_flow(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"review-queue-smoke-{uuid.uuid4().hex}"
        try:
            (tmp / "runtime").mkdir(parents=True)
            add = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "add",
                    "--type",
                    "duplicate",
                    "--title",
                    "Notion page duplicate",
                    "--description",
                    "Choose update or supersede.",
                    "--affected-path",
                    "docs/NOTION.md",
                    "--option",
                    "update_existing",
                    "--json",
                ],
                cwd=REPO_ROOT,
            )
            self.assertEqual(add.returncode, 0, add.stderr)
            item_id = json.loads(add.stdout)["id"]

            listing = _run([str(self.SCRIPT), "--root", str(tmp), "list", "--json"])
            self.assertEqual(listing.returncode, 0, listing.stderr)
            items = json.loads(listing.stdout)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["id"], item_id)

            resolved = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "resolve",
                    item_id,
                    "--decision",
                    "update_existing",
                ]
            )
            self.assertEqual(resolved.returncode, 0, resolved.stderr)

            count = _run([str(self.SCRIPT), "--root", str(tmp), "count"])
            self.assertEqual(count.stdout.strip(), "0")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_duplicate_open_items_are_merged(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"review-queue-dedupe-{uuid.uuid4().hex}"
        try:
            (tmp / "runtime").mkdir(parents=True)
            base = [
                str(self.SCRIPT),
                "--root",
                str(tmp),
                "add",
                "--type",
                "risky-update",
                "--title",
                "AGENTS.md risky update",
                "--description",
                "Review before applying.",
                "--affected-path",
                "AGENTS.md",
                "--json",
            ]
            first = _run(base)
            second = _run(base)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(json.loads(second.stdout)["status"], "merged")

            listing = _run([str(self.SCRIPT), "--root", str(tmp), "list", "--json"])
            self.assertEqual(len(json.loads(listing.stdout)), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_sweep_dry_run_does_not_mutate_and_apply_dismisses_missing_source(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"review-queue-sweep-{uuid.uuid4().hex}"
        try:
            (tmp / "runtime").mkdir(parents=True)
            add = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "add",
                    "--type",
                    "reference-adoption",
                    "--title",
                    "Missing proposal",
                    "--description",
                    "Proposal disappeared.",
                    "--source-path",
                    "runtime/proposals/reference-adoption/missing.md",
                    "--json",
                ]
            )
            self.assertEqual(add.returncode, 0, add.stdout + add.stderr)
            before = (tmp / "runtime" / "review-queue.jsonl").read_text(encoding="utf-8")
            dry = _run([str(self.SCRIPT), "--root", str(tmp), "sweep", "--dry-run", "--json"])
            self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
            self.assertEqual(before, (tmp / "runtime" / "review-queue.jsonl").read_text(encoding="utf-8"))
            payload = json.loads(dry.stdout)
            self.assertEqual(payload["status"], "dry_run")
            self.assertEqual(payload["actions"][0]["action"], "dismiss")

            apply = _run([str(self.SCRIPT), "--root", str(tmp), "sweep", "--apply", "--json"])
            self.assertEqual(apply.returncode, 0, apply.stdout + apply.stderr)
            listing = _run([str(self.SCRIPT), "--root", str(tmp), "list", "--all", "--json"])
            items = json.loads(listing.stdout)
            self.assertEqual(items[0]["status"], "dismissed")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_deferred_decision_stays_deferred_not_dismissed(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"review-queue-defer-{uuid.uuid4().hex}"
        try:
            proposal = tmp / "runtime" / "proposals" / "reference-adoption" / "proposal.md"
            proposal.parent.mkdir(parents=True)
            proposal.write_text("- `decision`: deferred\n", encoding="utf-8")
            add = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "add",
                    "--type",
                    "reference-adoption",
                    "--title",
                    "Deferred proposal",
                    "--description",
                    "Proposal is deferred.",
                    "--source-path",
                    "runtime/proposals/reference-adoption/proposal.md",
                    "--json",
                ]
            )
            self.assertEqual(add.returncode, 0, add.stdout + add.stderr)
            apply = _run([str(self.SCRIPT), "--root", str(tmp), "sweep", "--apply", "--json"])
            self.assertEqual(apply.returncode, 0, apply.stdout + apply.stderr)
            listing = _run([str(self.SCRIPT), "--root", str(tmp), "list", "--all", "--json"])
            item = json.loads(listing.stdout)[0]
            self.assertEqual(item["status"], "deferred")
            count = _run([str(self.SCRIPT), "--root", str(tmp), "count", "--json"])
            self.assertEqual(json.loads(count.stdout)["open"], 0)
            self.assertEqual(json.loads(count.stdout)["deferred"], 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class ReferenceTaskQueueTests(unittest.TestCase):
    SCRIPT = SCRIPTS / "reference-task-queue.py"

    def test_add_claim_complete_check_round_trip(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"reference-task-{uuid.uuid4().hex}"
        try:
            tmp.mkdir(parents=True)
            add = _run([str(self.SCRIPT), "--root", str(tmp), "add", "--target", "runtime/external-repos/local/fake", "--goal", "inspect", "--format", "json"])
            self.assertEqual(add.returncode, 0, add.stdout + add.stderr)
            task_id = json.loads(add.stdout)["id"]
            claim = _run([str(self.SCRIPT), "--root", str(tmp), "claim", task_id, "--by", "test", "--format", "json"])
            self.assertEqual(claim.returncode, 0, claim.stdout + claim.stderr)
            candidate = tmp / "research" / "reference-candidates" / "fake.md"
            proposal = tmp / "runtime" / "proposals" / "reference-adoption" / "fake.md"
            candidate.parent.mkdir(parents=True)
            proposal.parent.mkdir(parents=True)
            candidate.write_text("# candidate\n", encoding="utf-8")
            proposal.write_text("# proposal\n", encoding="utf-8")
            complete = _run([
                str(self.SCRIPT),
                "--root",
                str(tmp),
                "complete",
                task_id,
                "--candidate-card",
                "research/reference-candidates/fake.md",
                "--proposal",
                "runtime/proposals/reference-adoption/fake.md",
                "--format",
                "json",
            ])
            self.assertEqual(complete.returncode, 0, complete.stdout + complete.stderr)
            check = _run([str(self.SCRIPT), "--root", str(tmp), "check"])
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            listing = _run([str(self.SCRIPT), "--root", str(tmp), "list", "--format", "json"])
            self.assertEqual(json.loads(listing.stdout)[0]["status"], "done")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_corrupted_ledger_blocks_mutation(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"reference-task-corrupt-{uuid.uuid4().hex}"
        try:
            (tmp / "runtime").mkdir(parents=True)
            (tmp / "runtime" / "reference-tasks.jsonl").write_text(
                json.dumps({"ts": "2026-05-02T00:00:00Z", "action": "add", "id": "r1", "target": "repo", "goal": "inspect"}) + "\n{bad\n",
                encoding="utf-8",
            )
            before = (tmp / "runtime" / "reference-tasks.jsonl").read_text(encoding="utf-8")
            for command in (
                ["claim", "r1"],
                ["complete", "r1"],
                ["fail", "r1", "--error", "x"],
                ["cancel", "r1"],
            ):
                result = _run([str(self.SCRIPT), "--root", str(tmp), *command])
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("invalid JSON", result.stderr)
                self.assertEqual(before, (tmp / "runtime" / "reference-tasks.jsonl").read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_duplicate_add_id_is_rejected_and_detected(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"reference-task-dupe-{uuid.uuid4().hex}"
        try:
            (tmp / "runtime").mkdir(parents=True)
            first = _run([str(self.SCRIPT), "--root", str(tmp), "add", "--id", "r1", "--target", "repo"])
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            second = _run([str(self.SCRIPT), "--root", str(tmp), "add", "--id", "r1", "--target", "repo2"])
            self.assertEqual(second.returncode, 1)
            self.assertIn("already exists", second.stderr)
            with (tmp / "runtime" / "reference-tasks.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"ts": "2026-05-02T00:00:00Z", "action": "add", "id": "r1", "target": "repo2", "goal": "x"}) + "\n")
            check = _run([str(self.SCRIPT), "--root", str(tmp), "check"])
            self.assertEqual(check.returncode, 1)
            self.assertIn("duplicate add event", check.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_hash_skip_and_retry_flow(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"reference-task-hash-{uuid.uuid4().hex}"
        try:
            repo = tmp / "runtime" / "external-repos" / "local" / "fake"
            repo.mkdir(parents=True)
            (repo / "README.md").write_text("same content\n", encoding="utf-8")
            add = _run([str(self.SCRIPT), "--root", str(tmp), "add", "--target", "runtime/external-repos/local/fake", "--format", "json"])
            self.assertEqual(add.returncode, 0, add.stdout + add.stderr)
            first = json.loads(add.stdout)
            self.assertEqual(first["hash_algorithm"], "sha256")
            second = _run([str(self.SCRIPT), "--root", str(tmp), "add", "--target", "runtime/external-repos/local/fake", "--format", "json"])
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            skipped = json.loads(second.stdout)
            self.assertTrue(skipped["skipped"])
            self.assertEqual(skipped["skip_reason"], "unchanged")
            task_id = first["id"]
            claim = _run([str(self.SCRIPT), "--root", str(tmp), "claim", task_id])
            self.assertEqual(claim.returncode, 0, claim.stdout + claim.stderr)
            fail = _run([str(self.SCRIPT), "--root", str(tmp), "fail", task_id, "--error", "temporary"])
            self.assertEqual(fail.returncode, 0, fail.stdout + fail.stderr)
            retry = _run([str(self.SCRIPT), "--root", str(tmp), "retry", task_id, "--format", "json"])
            self.assertEqual(retry.returncode, 0, retry.stdout + retry.stderr)
            payload = json.loads(retry.stdout)
            self.assertEqual(payload["status"], "queued")
            self.assertEqual(payload["retry_count"], 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class SessionRecallTests(unittest.TestCase):
    SCRIPT = SCRIPTS / "session-recall.py"

    def test_index_search_check_round_trip(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"session-recall-{uuid.uuid4().hex}"
        try:
            (tmp / "runtime").mkdir(parents=True)
            (tmp / "state").mkdir()
            (tmp / "runtime" / "activity-log.jsonl").write_text('{"action":"reference_decision","data":{"topic":"checkout"}}\n', encoding="utf-8")
            (tmp / "runtime" / "completion-evidence.jsonl").write_text("", encoding="utf-8")
            (tmp / "runtime" / "skill-usage.jsonl").write_text("", encoding="utf-8")
            (tmp / "state" / "decisions.md").write_text("## 2026-05-02 - checkout\n- keep recall index\n", encoding="utf-8")
            index = _run([str(self.SCRIPT), "--root", str(tmp), "index", "--format", "json"])
            self.assertEqual(index.returncode, 0, index.stdout + index.stderr)
            search = _run([str(self.SCRIPT), "--root", str(tmp), "search", "checkout", "--format", "json"])
            self.assertEqual(search.returncode, 0, search.stdout + search.stderr)
            self.assertGreaterEqual(len(json.loads(search.stdout)), 1)
            check = _run([str(self.SCRIPT), "--root", str(tmp), "check"])
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            (tmp / "runtime" / "session-recall.sqlite").unlink()
            reindex = _run([str(self.SCRIPT), "--root", str(tmp), "index"])
            self.assertEqual(reindex.returncode, 0, reindex.stdout + reindex.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_check_reports_stale_index_when_source_changes(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"session-recall-stale-{uuid.uuid4().hex}"
        try:
            (tmp / "runtime").mkdir(parents=True)
            (tmp / "state").mkdir()
            activity = tmp / "runtime" / "activity-log.jsonl"
            activity.write_text('{"action":"first"}\n', encoding="utf-8")
            (tmp / "runtime" / "completion-evidence.jsonl").write_text("", encoding="utf-8")
            (tmp / "runtime" / "skill-usage.jsonl").write_text("", encoding="utf-8")
            (tmp / "state" / "decisions.md").write_text("## first\n", encoding="utf-8")
            index = _run([str(self.SCRIPT), "--root", str(tmp), "index"])
            self.assertEqual(index.returncode, 0, index.stdout + index.stderr)
            activity.write_text('{"action":"first"}\n{"action":"second"}\n', encoding="utf-8")
            stale = _run([str(self.SCRIPT), "--root", str(tmp), "check", "--format", "json"])
            self.assertEqual(stale.returncode, 1)
            payload = json.loads(stale.stdout)
            self.assertEqual(payload["status"], "stale")
            self.assertIn("runtime/activity-log.jsonl", payload["stale_sources"])
            refreshed = _run([str(self.SCRIPT), "--root", str(tmp), "index"])
            self.assertEqual(refreshed.returncode, 0, refreshed.stdout + refreshed.stderr)
            current = _run([str(self.SCRIPT), "--root", str(tmp), "check", "--format", "json"])
            self.assertEqual(current.returncode, 0, current.stdout + current.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class CheckpointTests(unittest.TestCase):
    SCRIPT = SCRIPTS / "checkpoint.py"

    def test_create_list_check_round_trip(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"checkpoint-{uuid.uuid4().hex}"
        try:
            tmp.mkdir(parents=True)
            create = _run([
                str(self.SCRIPT),
                "--root",
                str(tmp),
                "create",
                "--name",
                "midpoint",
                "--goal",
                "smoke",
                "--changed-path",
                ".",
                "--verify-status",
                "passed",
                "--format",
                "json",
            ])
            self.assertEqual(create.returncode, 0, create.stdout + create.stderr)
            record = json.loads(create.stdout)
            self.assertEqual(record["verify_status"], "passed")
            listing = _run([str(self.SCRIPT), "--root", str(tmp), "list", "--format", "json"])
            self.assertEqual(len(json.loads(listing.stdout)), 1)
            check = _run([str(self.SCRIPT), "--root", str(tmp), "check"])
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
