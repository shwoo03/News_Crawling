from tests.test_support import *


class InstallStateTests(unittest.TestCase):
    SCRIPT = SCRIPTS / "install-state.py"

    def test_empty_ledger_is_ok(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"install-state-{uuid.uuid4().hex}"
        try:
            (tmp / "runtime").mkdir(parents=True)
            (tmp / "runtime" / "install-state.jsonl").touch()
            result = _run([str(self.SCRIPT), "--root", str(tmp), "check"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_bad_json_is_rejected(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"install-state-bad-{uuid.uuid4().hex}"
        try:
            (tmp / "runtime").mkdir(parents=True)
            (tmp / "runtime" / "install-state.jsonl").write_text("{bad\n", encoding="utf-8")
            result = _run([str(self.SCRIPT), "--root", str(tmp), "check"])
            self.assertEqual(result.returncode, 1)
            self.assertIn("invalid JSON", result.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_validation_status_enum_is_enforced(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"install-state-status-{uuid.uuid4().hex}"
        try:
            (tmp / "runtime").mkdir(parents=True)
            result = _run([str(self.SCRIPT), "--root", str(tmp), "add", "--event", "convert_completed", "--validation-status", "mystery"])
            self.assertEqual(result.returncode, 1)
            self.assertIn("validation_status", result.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_strict_check_fails_on_latest_unverified_event(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"install-state-strict-{uuid.uuid4().hex}"
        try:
            (tmp / "runtime").mkdir(parents=True)
            add = _run([str(self.SCRIPT), "--root", str(tmp), "add", "--event", "convert_completed", "--validation-status", "unverified"])
            self.assertEqual(add.returncode, 0, add.stdout + add.stderr)
            non_strict = _run([str(self.SCRIPT), "--root", str(tmp), "--format", "json", "check"])
            self.assertEqual(non_strict.returncode, 0, non_strict.stdout + non_strict.stderr)
            self.assertIn("unverified", "\n".join(json.loads(non_strict.stdout)["warnings"]))
            strict = _run([str(self.SCRIPT), "--root", str(tmp), "check", "--strict"])
            self.assertEqual(strict.returncode, 1)
            verified = _run([str(self.SCRIPT), "--root", str(tmp), "add", "--event", "convert_verified", "--validation-status", "verified"])
            self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
            strict = _run([str(self.SCRIPT), "--root", str(tmp), "check", "--strict"])
            self.assertEqual(strict.returncode, 0, strict.stdout + strict.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class SkillLifecycleTests(unittest.TestCase):
    SCRIPT = SCRIPTS / "skill-lifecycle.py"

    def _root_with_skill(self, status: str = "candidate") -> Path:
        tmp = REPO_ROOT / "runtime" / f"skill-life-{uuid.uuid4().hex}"
        base = "skills/_candidates" if status == "candidate" else "skills/active"
        skill = tmp / base / "demo"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: demo\ndescription: demo\nstatus: demo\n---\n", encoding="utf-8")
        (tmp / "config").mkdir(parents=True)
        (tmp / "config" / "policy.yaml").write_text(
            "skill_lifecycle:\n"
            "  promote_min_uses: 2\n"
            "  promote_min_success_rate: 0.85\n"
            "  demote_threshold: 0.70\n",
            encoding="utf-8",
        )
        return tmp

    def test_report_recommends_promotion(self) -> None:
        tmp = self._root_with_skill("candidate")
        try:
            for run_id in ("r1", "r2"):
                result = _run([str(self.SCRIPT), "--root", str(tmp), "record-use", "--skill", "demo", "--run-id", run_id, "--outcome", "success"])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--format", "json", "report"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            demo = next(item for item in payload["skills"] if item["skill"] == "demo")
            self.assertEqual(demo["recommendation"], "promote")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_report_recommends_demotion(self) -> None:
        tmp = self._root_with_skill("active")
        try:
            result = _run([str(self.SCRIPT), "--root", str(tmp), "record-use", "--skill", "demo", "--run-id", "r1", "--outcome", "failure"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--format", "json", "report"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            demo = next(item for item in json.loads(result.stdout)["skills"] if item["skill"] == "demo")
            self.assertEqual(demo["recommendation"], "demote")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_duplicate_skill_names_make_report_fail(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"skill-life-duplicate-{uuid.uuid4().hex}"
        try:
            for base in ("skills/active/a", "skills/_meta/b"):
                path = tmp / base
                path.mkdir(parents=True)
                (path / "SKILL.md").write_text("---\nname: same\ndescription: demo\n---\n", encoding="utf-8")
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--format", "json", "report"])
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertIn("duplicate skill name `same`", "\n".join(payload["findings"]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_health_reports_golden_gap_and_recent_trend(self) -> None:
        tmp = self._root_with_skill("active")
        try:
            for run_id in ("r1", "r2"):
                result = _run([str(self.SCRIPT), "--root", str(tmp), "record-use", "--skill", "demo", "--run-id", run_id, "--outcome", "failure"])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--format", "json", "health"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            demo = next(item for item in json.loads(result.stdout)["skills"] if item["skill"] == "demo")
            self.assertEqual(demo["run_count_7d"], 2)
            self.assertEqual(demo["goldens"], 0)
            self.assertIn("add_golden_case", demo["health_recommendations"])
            self.assertIn("demote", demo["health_recommendations"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class EvalAllTests(unittest.TestCase):
    SCRIPT = SCRIPTS / "eval-all.py"

    def test_warn_ok_and_fail_are_reported(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"eval-all-{uuid.uuid4().hex}"
        try:
            for name in ("nogolden", "good", "bad"):
                skill = tmp / "skills" / "active" / name
                skill.mkdir(parents=True)
                (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {name}\nstatus: active\n---\n", encoding="utf-8")
            good_golden = tmp / "skills" / "active" / "good" / "goldens"
            bad_golden = tmp / "skills" / "active" / "bad" / "goldens"
            good_golden.mkdir()
            bad_golden.mkdir()
            (good_golden / "case-001.yaml").write_text(
                "id: good\nactual_output: |\n  alpha beta\nexpected_properties:\n  - alpha\nevaluation:\n  judge_method: schema-check\n",
                encoding="utf-8",
            )
            (bad_golden / "case-001.yaml").write_text(
                "id: bad\nactual_output: |\n  gamma\nexpected_properties:\n  - alpha\nevaluation:\n  judge_method: schema-check\n",
                encoding="utf-8",
            )
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--format", "json"])
            self.assertEqual(result.returncode, 1)
            statuses = {item["skill"]: item["status"] for item in json.loads(result.stdout)["results"]}
            self.assertEqual(statuses["nogolden"], "WARN")
            self.assertEqual(statuses["good"], "OK")
            self.assertEqual(statuses["bad"], "FAIL")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class CostLogTests(unittest.TestCase):
    SCRIPT = SCRIPTS / "cost-log.py"

    def test_negative_cost_is_rejected(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"cost-log-{uuid.uuid4().hex}"
        try:
            (tmp / "state").mkdir(parents=True)
            (tmp / "state" / "cost-log.jsonl").write_text(
                json.dumps({
                    "ts": "2026-05-02T00:00:00Z",
                    "run_id": "r1",
                    "agent": "a",
                    "skill": "",
                    "provider": "p",
                    "model": "m",
                    "input_tokens": 1,
                    "cached_input_tokens": 0,
                    "output_tokens": 1,
                    "cost_usd": -1,
                    "cost_status": "estimated",
                    "cost_source": "test",
                }) + "\n",
                encoding="utf-8",
            )
            result = _run([str(self.SCRIPT), "--root", str(tmp), "check"])
            self.assertEqual(result.returncode, 1)
            self.assertIn("cost_usd", result.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class SessionSnapshotTests(unittest.TestCase):
    SCRIPT = SCRIPTS / "session-snapshot.py"

    def test_write_then_check(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"session-snapshot-{uuid.uuid4().hex}"
        try:
            (tmp / "runtime" / "state").mkdir(parents=True)
            (tmp / "runtime" / "state" / "session-handoff.md").write_text("# Handoff\n", encoding="utf-8")
            (tmp / "runtime" / "activity-log.jsonl").write_text(
                json.dumps({"ts": "2026-05-02T00:00:00Z", "phase": "test", "action": "ok"}) + "\n",
                encoding="utf-8",
            )
            result = _run([str(self.SCRIPT), "--root", str(tmp), "write"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = _run([str(self.SCRIPT), "--root", str(tmp), "check"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_check_rejects_stale_and_foreign_snapshot(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"session-snapshot-stale-{uuid.uuid4().hex}"
        try:
            (tmp / "runtime" / "state").mkdir(parents=True)
            (tmp / "runtime" / "state" / "session-handoff.md").write_text("# Handoff\n", encoding="utf-8")
            (tmp / "runtime" / "activity-log.jsonl").write_text(
                json.dumps({"ts": "2026-05-02T00:00:00Z", "tool_call": {"tool": "old"}}) + "\n",
                encoding="utf-8",
            )
            write = _run([str(self.SCRIPT), "--root", str(tmp), "write"])
            self.assertEqual(write.returncode, 0, write.stdout + write.stderr)
            payload = json.loads((tmp / "runtime" / "session-snapshot.json").read_text(encoding="utf-8"))
            payload["activity_log_last"] = {"ts": "old"}
            payload["completion_evidence_last"] = {"command": "/tmp/other/repo/check"}
            (tmp / "runtime" / "session-snapshot.json").write_text(json.dumps(payload), encoding="utf-8")
            check = _run([str(self.SCRIPT), "--root", str(tmp), "check"])
            self.assertEqual(check.returncode, 1)
            self.assertIn("activity_log_last is stale", check.stdout)
            self.assertIn("outside repo", check.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
