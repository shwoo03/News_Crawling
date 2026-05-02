from tests.test_support import *
import re


class AgentFlowTests(unittest.TestCase):
    SCRIPT = SCRIPTS / "agent-flow.py"

    def _tmp_root(self, name: str) -> Path:
        tmp = REPO_ROOT / "runtime" / f"agent-flow-{name}-{uuid.uuid4().hex}"
        tmp.mkdir(parents=True)
        return tmp

    def _copy_scripts(self, root: Path, names: list[str]) -> None:
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        for name in names:
            shutil.copyfile(SCRIPTS / name, root / "scripts" / name)

    def _fake_reference_root(self, root: Path) -> Path:
        repo = root / "runtime" / "external-repos" / "local" / "fake"
        (repo / "scripts").mkdir(parents=True)
        (repo / "tests").mkdir()
        (repo / "README.md").write_text("# Fake\n\nReusable helper patterns.\n", encoding="utf-8")
        (repo / "LICENSE").write_text("MIT License\n", encoding="utf-8")
        (repo / "pyproject.toml").write_text("[project]\nname='fake'\n", encoding="utf-8")
        (repo / "scripts" / "helper.py").write_text("print('ok')\n", encoding="utf-8")
        (repo / "tests" / "test_helper.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        return repo

    def _fake_reference_named(self, root: Path, name: str, markers: tuple[str, ...]) -> Path:
        repo = root / "runtime" / "external-repos" / "local" / name
        repo.mkdir(parents=True)
        if "README.md" in markers:
            (repo / "README.md").write_text(f"# {name}\n", encoding="utf-8")
        if "LICENSE" in markers:
            (repo / "LICENSE").write_text("MIT License\n", encoding="utf-8")
        if "pyproject.toml" in markers:
            (repo / "pyproject.toml").write_text(f"[project]\nname='{name}'\n", encoding="utf-8")
        if "scripts" in markers:
            (repo / "scripts").mkdir()
            (repo / "scripts" / "helper.py").write_text("print('ok')\n", encoding="utf-8")
        if "tests" in markers:
            (repo / "tests").mkdir()
            (repo / "tests" / "test_helper.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        return repo

    def _prepare_research_root(self) -> Path:
        tmp = self._tmp_root("research")
        self._copy_scripts(
            tmp,
            [
                "reference-intake.py",
                "validate-reference-candidates.py",
                "create-reference-proposal.py",
                "validate-reference-proposals.py",
                "review-queue.py",
                "reference-task-queue.py",
            ],
        )
        self._fake_reference_root(tmp)
        return tmp

    def test_help_exits_zero(self) -> None:
        result = _run([str(self.SCRIPT), "--help"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("usage:", result.stdout.lower())

    def test_start_json_reports_project_status(self) -> None:
        tmp = self._tmp_root("start")
        try:
            self._copy_scripts(tmp, ["review-queue.py"])
            (tmp / "runtime" / "state").mkdir(parents=True)
            (tmp / "runtime" / "state" / "session-handoff.md").write_text("# Handoff\n\nReady.\n", encoding="utf-8")
            result = _run([str(self.SCRIPT), "--root", str(tmp), "start", "--format", "json"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["root"], str(tmp.resolve()))
            self.assertEqual(payload["review_queue_count"], 0)
            self.assertIn(payload["recommended_next_action"], {"research", "decide", "closeout"})
            self.assertIn(payload["mode"], {"research", "decide", "build", "maintain", "closeout"})
            self.assertEqual(payload["recommended_next_action"], payload["mode"])
            self.assertIn("next_command", payload)
            self.assertIn("signals", payload)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_start_build_goal_keeps_recommended_action_aligned(self) -> None:
        tmp = self._tmp_root("start-build-aligned")
        try:
            self._copy_scripts(tmp, ["review-queue.py"])
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "start",
                    "--goal",
                    "이 기능 구현해줘",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["mode"], "build")
            self.assertEqual(payload["recommended_next_action"], "build")
            self.assertEqual(payload["next_action_type"], "manual_work_required")
            self.assertIn("manual:", payload["next_command"])
            self.assertTrue(payload["build_intake"]["plan_required"])
            self.assertIn("plans/active", payload["build_intake"]["plan_location"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_start_goal_routes_research_request(self) -> None:
        tmp = self._tmp_root("start-goal")
        try:
            self._copy_scripts(tmp, ["review-queue.py"])
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "start",
                    "--goal",
                    "쇼핑몰 웹앱 만들고 있어. 오픈소스 먼저 보고 해줘",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["mode"], "research")
            self.assertIn("research --auto", payload["next_command"])
            self.assertIn("--goal", payload["next_command"])
            self.assertNotIn("--write-card", payload["next_command"])
            self.assertFalse(payload["requires_confirmation"])
            self.assertEqual(payload["next_action_type"], "agent_flow_command")
            self.assertIn(payload["catalog_status"]["source"], {"scripts/catalog.yaml", "defaults"})
            self.assertIn(payload["confidence"], {"high", "medium"})
            self.assertEqual(payload["write_policy"], "read_only")
            self.assertIn("reference_tasks", payload)
            self.assertIn("goal_mentions_reference", payload["signals"])
            questions = "\n".join(payload["suggested_questions"])
            self.assertIn("프로젝트 타입", questions)
            self.assertIn("레퍼런스", questions)
            self.assertIn("MVP", questions)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_start_goal_routes_closeout_request(self) -> None:
        tmp = self._tmp_root("start-closeout")
        try:
            self._copy_scripts(tmp, ["review-queue.py"])
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "start",
                    "--goal",
                    "검증하고 마무리해줘",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["mode"], "closeout")
            self.assertIn("goal_mentions_closeout", payload["signals"])
            self.assertTrue(payload["requires_confirmation"])
            self.assertEqual(payload["next_action_type"], "confirmation_required")
            self.assertEqual(payload["write_policy"], "write_with_confirmation")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_start_goal_routes_maintain_request(self) -> None:
        tmp = self._tmp_root("start-maintain")
        try:
            self._copy_scripts(tmp, ["review-queue.py"])
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "start",
                    "--goal",
                    "우리 시스템 구조 개선해줘",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["mode"], "maintain")
            self.assertEqual(payload["next_action_type"], "manual_work_required")
            self.assertEqual(payload["write_policy"], "manual_work_required")
            self.assertTrue(payload["next_command"].startswith("manual:"))
            self.assertIn("goal_mentions_maintain", payload["signals"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_start_reference_maintain_request_prefers_reference_review(self) -> None:
        tmp = self._tmp_root("start-maintain-reference")
        try:
            self._copy_scripts(tmp, ["review-queue.py"])
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "start",
                    "--goal",
                    "ECC opencode 같은 성숙한 레퍼런스 참고해서 우리 뼈대 개선해줘",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["mode"], "maintain")
            self.assertEqual(payload["next_action_type"], "reference_review_required")
            self.assertIn("research --auto", payload["next_command"])
            self.assertIn("--goal", payload["next_command"])
            self.assertIn("goal_mentions_reference", payload["signals"])
            self.assertIn("reference_review_required", payload["signals"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_start_without_goal_does_not_closeout_from_old_reference_files(self) -> None:
        tmp = self._tmp_root("start-no-goal-old-reference")
        try:
            self._copy_scripts(tmp, ["review-queue.py"])
            (tmp / "research" / "reference-candidates").mkdir(parents=True)
            (tmp / "runtime" / "proposals" / "reference-adoption").mkdir(parents=True)
            (tmp / "research" / "reference-candidates" / "old.md").write_text("# Old\n", encoding="utf-8")
            (tmp / "runtime" / "proposals" / "reference-adoption" / "old.md").write_text("# Old\n", encoding="utf-8")
            result = _run([str(self.SCRIPT), "--root", str(tmp), "start", "--format", "json"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["mode"], "build")
            self.assertEqual(payload["next_action_type"], "manual_work_required")
            self.assertIn("no_goal_provided", payload["signals"])
            self.assertNotEqual(payload["recommended_next_action"], "closeout")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_start_goal_routes_plain_build_request_to_build(self) -> None:
        tmp = self._tmp_root("start-build")
        try:
            self._copy_scripts(tmp, ["review-queue.py"])
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "start",
                    "--goal",
                    "이 기능 구현해줘",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["mode"], "build")
            self.assertEqual(payload["next_action_type"], "manual_work_required")
            self.assertTrue(payload["next_command"].startswith("manual:"))
            self.assertIn("goal_mentions_build", payload["signals"])
            self.assertTrue(payload["build_intake"]["plan_required"])
            self.assertEqual(payload["build_intake"]["goal"], "이 기능 구현해줘")
            questions = "\n".join(payload["suggested_questions"])
            self.assertIn("구현할 정확한 범위", questions)
            self.assertIn("수용 기준", questions)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_start_open_review_queue_overrides_goal(self) -> None:
        tmp = self._tmp_root("start-decision")
        try:
            self._copy_scripts(tmp, ["review-queue.py"])
            add = _run(
                [
                    str(tmp / "scripts" / "review-queue.py"),
                    "--root",
                    str(tmp),
                    "add",
                    "--type",
                    "reference-adoption",
                    "--title",
                    "Approve proposal",
                    "--description",
                    "Needs user decision.",
                    "--source-path",
                    "runtime/proposals/reference-adoption/example.md",
                    "--option",
                    "accept",
                ]
            )
            self.assertEqual(add.returncode, 0, add.stdout + add.stderr)
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "start",
                    "--goal",
                    "새 프로젝트라 오픈소스 먼저 보고 해줘",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["mode"], "decide")
            self.assertTrue(payload["requires_confirmation"])
            self.assertEqual(payload["next_action_type"], "user_decision_required")
            self.assertEqual(payload["write_policy"], "read_only")
            self.assertIn("runtime/proposals/reference-adoption/example.md", payload["next_command"])
            self.assertIn("open_review_queue", payload["signals"])
            self.assertIn("accepted, rejected, deferred", "\n".join(payload["suggested_questions"]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_research_preview_does_not_write_candidate_card(self) -> None:
        tmp = self._prepare_research_root()
        try:
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "research",
                    "--local-path",
                    "runtime/external-repos/local/fake",
                    "--url",
                    "https://example.com/fake.git",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("# suggested_output:", result.stdout)
            self.assertFalse((tmp / "research" / "reference-candidates").exists())
            self.assertTrue((tmp / "runtime" / "external-repos" / "local" / "fake" / "README.md").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_research_auto_preview_selects_fake_reference_without_writes(self) -> None:
        tmp = self._prepare_research_root()
        try:
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "research",
                    "--auto",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["auto"])
            self.assertEqual(payload["selected_reference"], "runtime/external-repos/local/fake")
            self.assertEqual(len(payload["reference_candidates"]), 1)
            self.assertEqual(payload["reference_candidates"][0]["path"], payload["selected_reference"])
            self.assertIn("not_yet_candidate_carded", payload["selection_signals"])
            self.assertIn("matched_goal_terms", payload)
            self.assertIn("excluded_references", payload)
            self.assertIn("reference_memory", payload)
            self.assertFalse(payload["reuse_existing_card_suggested"])
            self.assertTrue(any(item.startswith("repo_markers:") for item in payload["selection_signals"]))
            self.assertFalse((tmp / "research" / "reference-candidates").exists())
            self.assertTrue((tmp / "runtime" / "external-repos" / "local" / "fake" / "README.md").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_research_auto_write_card_and_proposal(self) -> None:
        tmp = self._prepare_research_root()
        try:
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "research",
                    "--auto",
                    "--write-card",
                    "--proposal",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["selected_reference"], "runtime/external-repos/local/fake")
            self.assertEqual(payload["reference_candidates"][0]["path"], payload["selected_reference"])
            self.assertIn("not_yet_candidate_carded", payload["selection_signals"])
            self.assertTrue((tmp / payload["candidate_path"]).is_file())
            self.assertTrue((tmp / payload["proposal_path"]).is_file())
            self.assertTrue(payload["reference_task_id"].startswith("ref-task-"))
            self.assertIn("reference-adoption", (tmp / "runtime" / "review-queue.jsonl").read_text(encoding="utf-8"))
            tasks = (tmp / "runtime" / "reference-tasks.jsonl").read_text(encoding="utf-8")
            self.assertIn(payload["reference_task_id"], tasks)
            self.assertIn('"action":"complete"', tasks)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_research_write_card_and_proposal_creates_review_item(self) -> None:
        tmp = self._prepare_research_root()
        try:
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "research",
                    "--local-path",
                    "runtime/external-repos/local/fake",
                    "--url",
                    "https://example.com/fake.git",
                    "--write-card",
                    "--proposal",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["selection_reason"], "explicit local path")
            self.assertIn("explicit_local_path", payload["selection_signals"])
            self.assertEqual(len(payload["reference_candidates"]), 1)
            self.assertEqual(payload["reference_candidates"][0]["path"], "runtime/external-repos/local/fake")
            candidate = tmp / payload["candidate_path"]
            proposal = tmp / payload["proposal_path"]
            self.assertTrue(candidate.is_file())
            self.assertTrue(proposal.is_file())
            self.assertIn("- `sources`:", candidate.read_text(encoding="utf-8"))
            self.assertIn("Source-backed evidence:", proposal.read_text(encoding="utf-8"))
            queue_text = (tmp / "runtime" / "review-queue.jsonl").read_text(encoding="utf-8")
            self.assertIn("reference-adoption", queue_text)
            self.assertTrue(all(item["ok"] for item in payload["commands"]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_research_auto_reports_top_three_candidates_sorted_by_score(self) -> None:
        tmp = self._tmp_root("research-top")
        try:
            self._copy_scripts(
                tmp,
                [
                    "reference-intake.py",
                    "validate-reference-candidates.py",
                    "create-reference-proposal.py",
                    "validate-reference-proposals.py",
                    "review-queue.py",
                ],
            )
            self._fake_reference_named(tmp, "gamma", ("README.md", "scripts"))
            self._fake_reference_named(tmp, "beta", ("README.md", "LICENSE", "scripts"))
            self._fake_reference_named(tmp, "alpha", ("README.md", "LICENSE", "pyproject.toml", "scripts", "tests"))
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "research",
                    "--auto",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            candidates = payload["reference_candidates"]
            self.assertEqual(len(candidates), 3)
            self.assertEqual(payload["selected_reference"], candidates[0]["path"])
            self.assertEqual(candidates[0]["path"], "runtime/external-repos/local/alpha")
            scores = [item["score"] for item in candidates]
            self.assertEqual(scores, sorted(scores, reverse=True))
            self.assertTrue(all("selection_reason" in item for item in candidates))
            self.assertTrue(all("selection_signals" in item for item in candidates))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_research_auto_goal_prioritizes_named_reference_over_uncarded_repo(self) -> None:
        tmp = self._tmp_root("research-goal-aware")
        try:
            self._copy_scripts(
                tmp,
                [
                    "reference-intake.py",
                    "validate-reference-candidates.py",
                    "create-reference-proposal.py",
                    "validate-reference-proposals.py",
                    "review-queue.py",
                ],
            )
            self._fake_reference_named(tmp, "paperclip", ("README.md", "LICENSE", "scripts", "tests"))
            self._fake_reference_named(tmp, "opencode", ("README.md", "LICENSE", "pyproject.toml", "scripts", "tests"))
            self._fake_reference_named(tmp, "everything-claude-code", ("README.md", "LICENSE", "pyproject.toml", "scripts", "tests"))
            cards = tmp / "research" / "reference-candidates"
            cards.mkdir(parents=True)
            (cards / "2026-05-02-opencode.md").write_text(
                "# opencode\n\n- `name`: opencode\n- `url`: runtime/external-repos/local/opencode\n- `reviewed_at`: 2026-05-02\n",
                encoding="utf-8",
            )
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "research",
                    "--auto",
                    "--goal",
                    "ECC opencode 참고해서 개선해줘",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn(payload["selected_reference"], {"runtime/external-repos/local/opencode", "runtime/external-repos/local/everything-claude-code"})
            self.assertNotEqual(payload["selected_reference"], "runtime/external-repos/local/paperclip")
            self.assertIn("opencode", payload["matched_goal_terms"])
            self.assertIn("goal_reference_match", payload["selection_signals"])
            if payload["selected_reference"].endswith("opencode"):
                self.assertTrue(payload["reuse_existing_card_suggested"])
                self.assertEqual(payload["reference_memory"]["recommended_action"], "reuse_existing_card")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_research_auto_prefer_and_exclude_control_candidates(self) -> None:
        tmp = self._tmp_root("research-prefer-exclude")
        try:
            self._copy_scripts(tmp, ["reference-intake.py"])
            self._fake_reference_named(tmp, "paperclip", ("README.md", "LICENSE", "scripts", "tests"))
            self._fake_reference_named(tmp, "opencode", ("README.md", "LICENSE", "scripts", "tests"))
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "research",
                    "--auto",
                    "--prefer",
                    "opencode",
                    "--exclude",
                    "paperclip",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["selected_reference"], "runtime/external-repos/local/opencode")
            self.assertTrue(any(item.endswith("paperclip") for item in payload["excluded_references"]))
            self.assertNotIn("paperclip", "\n".join(item["path"] for item in payload["reference_candidates"]))
            self.assertIn("prefer_match", payload["selection_signals"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_decide_updates_proposal_review_queue_and_activity_log(self) -> None:
        tmp = self._prepare_research_root()
        try:
            research = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "research",
                    "--local-path",
                    "runtime/external-repos/local/fake",
                    "--url",
                    "https://example.com/fake.git",
                    "--write-card",
                    "--proposal",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(research.returncode, 0, research.stdout + research.stderr)
            proposal_path = json.loads(research.stdout)["proposal_path"]
            decide = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "decide",
                    "--proposal",
                    proposal_path,
                    "--decision",
                    "accepted",
                    "--by",
                    "test",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(decide.returncode, 0, decide.stdout + decide.stderr)
            proposal_text = (tmp / proposal_path).read_text(encoding="utf-8")
            self.assertIn("- `decision`: accepted", proposal_text)
            self.assertIn("- `decided_by`: test", proposal_text)
            queue = _run([str(tmp / "scripts" / "review-queue.py"), "--root", str(tmp), "list", "--all", "--json"])
            self.assertEqual(queue.returncode, 0, queue.stdout + queue.stderr)
            items = json.loads(queue.stdout)
            self.assertEqual(items[0]["status"], "resolved")
            self.assertEqual(items[0]["decision"], "accepted")
            activity = (tmp / "runtime" / "activity-log.jsonl").read_text(encoding="utf-8")
            self.assertIn("reference_decision", activity)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_decide_defer_alias_marks_review_item_deferred(self) -> None:
        tmp = self._prepare_research_root()
        try:
            research = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "research",
                    "--local-path",
                    "runtime/external-repos/local/fake",
                    "--write-card",
                    "--proposal",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(research.returncode, 0, research.stdout + research.stderr)
            proposal_path = json.loads(research.stdout)["proposal_path"]
            decide = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "decide",
                    "--proposal",
                    proposal_path,
                    "--decision",
                    "defer",
                    "--by",
                    "test",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(decide.returncode, 0, decide.stdout + decide.stderr)
            payload = json.loads(decide.stdout)
            self.assertEqual(payload["decision"], "deferred")
            self.assertEqual(payload["review_queue_action"], "deferred")
            queue = _run([str(tmp / "scripts" / "review-queue.py"), "--root", str(tmp), "list", "--all", "--json"])
            self.assertEqual(json.loads(queue.stdout)[0]["status"], "deferred")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_closeout_failure_does_not_record_completion_evidence(self) -> None:
        tmp = self._tmp_root("closeout")
        try:
            scripts = tmp / "scripts"
            scripts.mkdir()
            (scripts / "verify.py").write_text(
                "import sys\nprint('forced failure')\nsys.exit(1)\n",
                encoding="utf-8",
            )
            (scripts / "quality-gate.py").write_text(
                "import sys\nprint('{\"checks\": []}')\nsys.exit(0 if '--strict' in sys.argv else 2)\n",
                encoding="utf-8",
            )
            (scripts / "task-closeout.py").write_text(
                "from pathlib import Path\nPath('called-task-closeout').write_text('called', encoding='utf-8')\n",
                encoding="utf-8",
            )
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "closeout",
                    "--goal",
                    "forced failure",
                    "--changed-path",
                    "docs/example.md",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["recorded"])
            self.assertEqual(payload["skipped_record_reason"], "verify_or_quality_gate_failed")
            self.assertFalse((tmp / "called-task-closeout").exists())
            self.assertFalse((tmp / "runtime" / "completion-evidence.jsonl").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_closeout_invokes_quality_gate_strict(self) -> None:
        tmp = self._tmp_root("closeout-strict")
        try:
            scripts = tmp / "scripts"
            scripts.mkdir()
            (scripts / "verify.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
            (scripts / "quality-gate.py").write_text(
                "from pathlib import Path\nimport sys\nPath('strict-seen').write_text(str('--strict' in sys.argv), encoding='utf-8')\nprint('{\"checks\": []}')\nsys.exit(0)\n",
                encoding="utf-8",
            )
            (scripts / "task-closeout.py").write_text("import sys\nprint('{\"recorded\": true}')\nsys.exit(0)\n", encoding="utf-8")
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "closeout",
                    "--goal",
                    "strict closeout",
                    "--changed-path",
                    "docs/example.md",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((tmp / "strict-seen").read_text(encoding="utf-8"), "True")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_script_catalog_marks_agent_flow_as_only_public_command(self) -> None:
        catalog = REPO_ROOT / "scripts" / "catalog.yaml"
        self.assertTrue(catalog.is_file())
        text = catalog.read_text(encoding="utf-8")
        public_block = text.split("internal:", 1)[0]
        self.assertIn("path: scripts/agent-flow.py", public_block)
        self.assertNotIn("path: scripts/quality-gate.py", public_block)
        paths = re.findall(r"path:\s+(scripts/[A-Za-z0-9_./-]+)", text)
        missing = [path for path in paths if not (REPO_ROOT / path).exists()]
        self.assertEqual(missing, [])

    def test_start_marks_catalog_write_command_as_confirmation_required(self) -> None:
        tmp = self._tmp_root("catalog-write")
        try:
            self._copy_scripts(tmp, ["review-queue.py"])
            (tmp / "scripts" / "catalog.yaml").write_text(
                "version: 1\n"
                "public:\n"
                "  - path: scripts/agent-flow.py\n"
                "routing:\n"
                "  modes:\n"
                "    research:\n"
                "      goal_pattern: (오픈소스|reference)\n"
                "      reason: writes for test\n"
                "      confidence: high\n"
                "      requires_confirmation: false\n"
                "      signal: goal_mentions_reference\n"
                "      next_command: python scripts/agent-flow.py research --auto --write-card --proposal --format json\n"
                "      suggested_questions:\n"
                "        - q\n",
                encoding="utf-8",
            )
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "start",
                    "--goal",
                    "오픈소스 먼저 봐줘",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["requires_confirmation"])
            self.assertEqual(payload["next_action_type"], "confirmation_required")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
