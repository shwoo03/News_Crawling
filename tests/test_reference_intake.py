from tests.test_support import *


class ReferenceIntakeTests(unittest.TestCase):
    SCRIPT = SCRIPTS / "reference-intake.py"

    def _fake_repo(self) -> Path:
        tmp = REPO_ROOT / "runtime" / f"reference-intake-{uuid.uuid4().hex}"
        repo = tmp / "runtime" / "external-repos" / "local" / "fake"
        (repo / "scripts").mkdir(parents=True)
        (repo / "tests").mkdir()
        (repo / "README.md").write_text("# Fake\n", encoding="utf-8")
        (repo / "LICENSE").write_text("MIT License\n", encoding="utf-8")
        (repo / "pyproject.toml").write_text("[project]\nname='fake'\n", encoding="utf-8")
        (repo / "scripts" / "helper.py").write_text("print('ok')\n", encoding="utf-8")
        (repo / "tests" / "test_helper.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        return tmp

    def test_analyze_local_path_reports_structure(self) -> None:
        tmp = self._fake_repo()
        try:
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "analyze",
                    "--local-path",
                    "runtime/external-repos/local/fake",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["license"], "MIT")
            self.assertTrue(payload["has_readme"])
            self.assertTrue(payload["has_tests"])
            self.assertIn("scripts", payload["reusable_units"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_analyze_cache_is_explicit_and_reused(self) -> None:
        tmp = self._fake_repo()
        try:
            preview = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "analyze",
                    "--local-path",
                    "runtime/external-repos/local/fake",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
            self.assertEqual(json.loads(preview.stdout)["cache_status"], "miss")
            self.assertFalse((tmp / "runtime" / "reference-intake-cache.jsonl").exists())

            cached = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "analyze",
                    "--local-path",
                    "runtime/external-repos/local/fake",
                    "--format",
                    "json",
                    "--cache",
                ]
            )
            self.assertEqual(cached.returncode, 0, cached.stdout + cached.stderr)
            self.assertTrue((tmp / "runtime" / "reference-intake-cache.jsonl").exists())

            hit = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "analyze",
                    "--local-path",
                    "runtime/external-repos/local/fake",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(hit.returncode, 0, hit.stdout + hit.stderr)
            self.assertEqual(json.loads(hit.stdout)["cache_status"], "hit")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_card_draft_write_creates_valid_candidate(self) -> None:
        tmp = self._fake_repo()
        try:
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "card-draft",
                    "--local-path",
                    "runtime/external-repos/local/fake",
                    "--url",
                    "https://example.com/fake.git",
                    "--searched-for",
                    "fake repo",
                    "--write",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            validator = _run([str(SCRIPTS / "validate-reference-candidates.py"), "--root", str(tmp)])
            self.assertEqual(validator.returncode, 0, validator.stdout + validator.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_clone_refuses_destination_outside_external_repos(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"reference-intake-clone-{uuid.uuid4().hex}"
        try:
            tmp.mkdir(parents=True)
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "clone",
                    "--url",
                    "https://github.com/example/project.git",
                    "--destination",
                    "outside/project",
                    "--format",
                    "json",
                ]
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("runtime/external-repos", result.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class ReferenceGovernanceTighteningTests(unittest.TestCase):
    def test_direct_implementation_candidate_requires_reason(self) -> None:
        scratch = REPO_ROOT / "research" / "reference-candidates" / "_tmp_direct_impl_missing_reason.md"
        scratch.write_text(
            """# Direct implementation smoke

## 기본 정보

- `name`: direct smoke
- `url`: https://example.com
- `source_type`: repository
- `status`: reviewing
- `searched_for`: smoke
- `created_at`: 2026-05-02
- `reviewed_at`: 2026-05-02
- `reviewer`: test

## 왜 보는가

- `problem_statement`: smoke
- `why_it_matters`: smoke
- `expected_value`: smoke

## 유용한 패턴

- `useful_patterns`:
  - smoke
- `what_to_copy_conceptually`:
  - smoke
- `what_to_copy_directly`:
  - none
- `what_not_to_copy`:
  - whole repo

## 증거

- `evidence_summary`: smoke
- `local_clone_path`: not cloned
- `checked_revision`: not checked
- `freshness_signal`: smoke
- `maintenance_signal`: smoke
- `documentation_signal`: smoke
- `validation_signal`: smoke

## 리스크

- `license`: MIT
- `security_or_privacy_risk`: low
- `maintenance_risk`: low
- `complexity_risk`: low
- `dependency_risk`: low
- `fit_risk`: low

## 적용 후보

- `applies_to`: scripts
- `target_files_or_areas`:
  - scripts/example.py
- `adoption_decision`: direct_implementation
- `absorption_mode`: direct_implementation
- `direct_implementation_reason`: not applicable
- `decision_reason`: smoke
- `next_action`: smoke

## 점수

| 기준 | 배점 | 점수 | 근거 |
| --- | ---: | ---: | --- |
| 문제 적합성 | 20 | 10 | smoke |
| 구조 명확성 | 15 | 10 | smoke |
| 검증 가능성 | 15 | 10 | smoke |
| 유지보수 신호 | 15 | 10 | smoke |
| 흡수 비용 | 15 | 10 | smoke |
| 보안/라이선스 리스크 | 10 | 10 | smoke |
| 설명 가치 | 10 | 10 | smoke |
| 합계 | 100 | 70 | smoke |

## Dry-Run 제안

- `proposal_needed`: yes
- `files_to_change`:
  - scripts/example.py
- `behavior_change`: smoke
- `validation_plan`: smoke
- `rollback_or_stop_condition`: smoke
- `approval_required`: yes
- `copy_boundary`: not applicable

## 최종 기록

- `final_status`: reviewing
- `validation_result`: not run
- `activity_log_entry`: none
- `notes`: smoke
""",
            encoding="utf-8",
        )
        try:
            result = _run([str(SCRIPTS / "validate-reference-candidates.py"), "--root", str(REPO_ROOT)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("direct_implementation decision requires", result.stdout)
        finally:
            scratch.unlink(missing_ok=True)

    def test_create_reference_proposal_write_queues_review_when_available(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"reference-proposal-queue-{uuid.uuid4().hex}"
        try:
            candidate_dir = tmp / "research" / "reference-candidates"
            candidate_dir.mkdir(parents=True)
            shutil.copyfile(REPO_ROOT / "research" / "reference-candidates" / "2026-04-27-langgraph.md", candidate_dir / "candidate.md")
            (tmp / "scripts").mkdir()
            shutil.copyfile(SCRIPTS / "review-queue.py", tmp / "scripts" / "review-queue.py")
            output = tmp / "runtime" / "proposals" / "reference-adoption" / "proposal.md"
            result = _run(
                [
                    str(SCRIPTS / "create-reference-proposal.py"),
                    "--root",
                    str(tmp),
                    "--candidate",
                    "research/reference-candidates/candidate.md",
                    "--output",
                    "runtime/proposals/reference-adoption/proposal.md",
                    "--write",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(output.exists())
            queue = (tmp / "runtime" / "review-queue.jsonl").read_text(encoding="utf-8")
            self.assertIn("reference-adoption", queue)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
