from tests.test_support import *


class ReferenceCandidateTests(unittest.TestCase):
    """Candidate cards must be structured enough to compare and promote."""

    SCRIPT = SCRIPTS / "validate-reference-candidates.py"

    def test_current_reference_candidates_are_valid(self) -> None:
        result = _run([str(self.SCRIPT)], cwd=REPO_ROOT)
        self.assertEqual(
            result.returncode,
            0,
            f"candidate validation failed:\nstdout={result.stdout}\nstderr={result.stderr}",
        )
        self.assertIn("reference candidates OK", result.stdout)

    def test_invalid_candidate_is_rejected(self) -> None:
        scratch = REPO_ROOT / "research" / "reference-candidates" / "_tmp_invalid_candidate_smoke.md"
        scratch.write_text(
            "# Broken\n\n- `name`:\n- `source_type`: website\n",
            encoding="utf-8",
        )
        try:
            result = _run([str(self.SCRIPT), "--root", str(REPO_ROOT)])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing field `url`", result.stdout)
        finally:
            scratch.unlink(missing_ok=True)

class ReferenceProposalTests(unittest.TestCase):
    """Reference-adoption dry-run proposals must be reviewable before apply."""

    SCRIPT = SCRIPTS / "validate-reference-proposals.py"

    def test_current_reference_proposals_are_valid(self) -> None:
        result = _run([str(self.SCRIPT)], cwd=REPO_ROOT)
        self.assertEqual(
            result.returncode,
            0,
            f"proposal validation failed:\nstdout={result.stdout}\nstderr={result.stderr}",
        )
        self.assertIn("reference proposals OK", result.stdout)

    def test_invalid_reference_proposal_is_rejected(self) -> None:
        scratch = (
            REPO_ROOT
            / "runtime"
            / "proposals"
            / "reference-adoption"
            / "_tmp_invalid_proposal_smoke.md"
        )
        scratch.write_text(
            "# Broken\n\n## 상태\n\n- `status`: maybe\n",
            encoding="utf-8",
        )
        try:
            result = _run([str(self.SCRIPT), "--root", str(REPO_ROOT)])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing field `candidate_card`", result.stdout)
        finally:
            scratch.unlink(missing_ok=True)

    def test_partial_copy_requires_copy_boundary(self) -> None:
        scratch = (
            REPO_ROOT
            / "runtime"
            / "proposals"
            / "reference-adoption"
            / "_tmp_partial_copy_missing_boundary.md"
        )
        scratch.write_text(
            """# Partial copy smoke

## 상태

- `status`: proposed
- `created_at`: 2026-04-30
- `candidate_card`: `research/reference-candidates/2026-04-27-langgraph.md`
- `proposal_type`: reference_adoption_dry_run
- `approval_required`: yes
- `decision_source`:

## 한 문장 정의

Partial copy smoke proposal.

## 근거

Smoke test.

## 적용하지 않을 것

- Whole repository copy.

## 모듈형 흡수 판단

- `absorption_mode`: partial_copy
- `recommended_mode`: copy selected code.
- `reuse_boundary`: private local only.
- `direct_implementation_reason`: not applicable.

- The selected code is small.

## 제안 변경

### 1. Smoke

대상: `scripts/example.py`

추가할 내용:

- Copy one helper.

## 기대 효과

- Better reuse.

## 위험

- Attribution drift.

완화:

- Record source.

## 검증 계획

```powershell
python scripts/verify-skeleton.py
python scripts/validate-reference-candidates.py
python scripts/validate-reference-proposals.py
```

## 롤백 또는 중단 조건

- Redistribution planned.

## 승인 후 실제 변경 범위

- `scripts/example.py`

## 최종 결정 기록

- `decision`: pending
- `decided_at`:
- `decided_by`:
- `decision_source`:
- `applied_in`:
- `validation_result`:
""",
            encoding="utf-8",
        )
        try:
            result = _run([str(self.SCRIPT), "--root", str(REPO_ROOT)])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("partial_copy proposal requires non-blank field `copy_boundary`", result.stdout)
        finally:
            scratch.unlink(missing_ok=True)

    def test_reference_refresh_proposal_is_valid(self) -> None:
        scratch = (
            REPO_ROOT
            / "runtime"
            / "proposals"
            / "reference-adoption"
            / "_tmp_reference_refresh_valid.md"
        )
        scratch.write_text(
            """# Reference Refresh Smoke

## 상태

- `status`: proposed
- `created_at`: 2026-05-02T00:00:00Z
- `candidate_card`: `references.yaml`
- `proposal_type`: reference_refresh
- `approval_required`: yes
- `decision_source`:
- `decision`: pending
- `decided_at`:
- `decided_by`:
- `applied_in`:
- `validation_result`:

## 한 문장 정의

Refresh tracked reference commit.

## 근거

- Latest commit changed.

## 제안 변경

- Review before applying.

## 검증 계획

```powershell
python scripts/verify-skeleton.py
python scripts/validate-reference-proposals.py
```

## 최종 결정 기록

- Pending user approval.
""",
            encoding="utf-8",
        )
        try:
            result = _run([str(self.SCRIPT), "--root", str(REPO_ROOT)])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        finally:
            scratch.unlink(missing_ok=True)

    def test_reference_refresh_missing_required_field_is_rejected(self) -> None:
        scratch = (
            REPO_ROOT
            / "runtime"
            / "proposals"
            / "reference-adoption"
            / "_tmp_reference_refresh_missing.md"
        )
        scratch.write_text(
            """# Reference Refresh Smoke

## 상태

- `status`: proposed
- `created_at`: 2026-05-02T00:00:00Z
- `candidate_card`: `references.yaml`
- `proposal_type`: reference_refresh
- `approval_required`: yes
- `decision`: pending
- `decided_at`:
- `decided_by`:
- `applied_in`:
- `validation_result`:

## 한 문장 정의

Refresh tracked reference commit.

## 근거

- Latest commit changed.

## 제안 변경

- Review before applying.

## 검증 계획

```powershell
python scripts/verify-skeleton.py
python scripts/validate-reference-proposals.py
```

## 최종 결정 기록

- Pending user approval.
""",
            encoding="utf-8",
        )
        try:
            result = _run([str(self.SCRIPT), "--root", str(REPO_ROOT)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("missing field `decision_source`", result.stdout)
        finally:
            scratch.unlink(missing_ok=True)

class SecurityScanTests(unittest.TestCase):
    """`security-scan.py` is a read-only local hygiene scanner."""

    SCRIPT = SCRIPTS / "security-scan.py"

    def test_clean_skeleton_security_scan_json_is_parseable(self) -> None:
        result = _run(
            [str(self.SCRIPT), "--root", str(REPO_ROOT), "--format", "json"],
            cwd=REPO_ROOT,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"security scan failed:\nstdout={result.stdout}\nstderr={result.stderr}",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["root"], str(REPO_ROOT.resolve()))
        self.assertIn("summary", payload)
        self.assertGreater(payload["scanned_files"], 0)

    def test_current_allowlist_suppresses_known_medium_findings(self) -> None:
        result = _run(
            [str(self.SCRIPT), "--root", str(REPO_ROOT), "--format", "json"],
            cwd=REPO_ROOT,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["summary"]["MEDIUM"], 0)
        self.assertGreater(payload["suppressed_findings"], 0)

    def test_allowlist_requires_line_or_fingerprint(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"security-allowlist-{uuid.uuid4().hex}"
        try:
            (tmp / "rules").mkdir(parents=True)
            (tmp / "scripts").mkdir()
            (tmp / "scripts" / "probe.sh").write_text("echo ok 2>" + "/dev/null\n", encoding="utf-8")
            (tmp / "rules" / "security-scan-allowlist.json").write_text(
                json.dumps([
                    {
                        "rule": "silent_error_suppression",
                        "path": "scripts/probe.sh",
                        "reason": "too broad",
                    }
                ]),
                encoding="utf-8",
            )
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--strict"])
            self.assertEqual(result.returncode, 1)
            self.assertIn("allowlist_invalid", result.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_allowlist_line_does_not_suppress_other_lines(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"security-allowlist-line-{uuid.uuid4().hex}"
        try:
            (tmp / "rules").mkdir(parents=True)
            (tmp / "scripts").mkdir()
            (tmp / "scripts" / "probe.sh").write_text("echo one 2>" + "/dev/null\necho two 2>" + "/dev/null\n", encoding="utf-8")
            (tmp / "rules" / "security-scan-allowlist.json").write_text(
                json.dumps([
                    {
                        "rule": "silent_error_suppression",
                        "path": "scripts/probe.sh",
                        "line": 1,
                        "reason": "line-specific suppression",
                    }
                ]),
                encoding="utf-8",
            )
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--format", "json"])
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["suppressed_findings"], 1)
            active_lines = [finding["line"] for finding in payload["findings"] if finding["rule"] == "silent_error_suppression"]
            self.assertEqual(active_lines, [2])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_security_scan_bad_root_exits_two(self) -> None:
        result = _run(
            [str(self.SCRIPT), "--root", str(REPO_ROOT / "does-not-exist")],
            cwd=REPO_ROOT,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("root not a directory", result.stderr)

    def test_synthetic_token_is_critical_and_strict_fails(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"security-scan-smoke-{uuid.uuid4().hex}"
        try:
            tmp.mkdir(parents=True)
            (tmp / "leak.py").write_text(
                "OPENAI_API_KEY = '" + "sk-" + "abcdefghijklmnopqrstuvwxyz1234567890'\n",
                encoding="utf-8",
            )
            result = _run([str(SecurityScanTests.SCRIPT), "--root", str(tmp), "--format", "json"])
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["summary"]["CRITICAL"], 1)

            strict = _run([str(self.SCRIPT), "--root", str(tmp), "--strict"])
            self.assertEqual(strict.returncode, 1)
            self.assertIn("openai_token", strict.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_modern_and_commented_secrets_are_detected(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"security-scan-modern-{uuid.uuid4().hex}"
        try:
            tmp.mkdir(parents=True)
            (tmp / "leak.env").write_text(
                "# OPENAI_API_KEY=" + "sk-proj-" + "abcdefghijklmnopqrstuvwxyz1234567890\n"
                "ANTHROPIC_API_KEY=" + "sk-ant-" + "abcdefghijklmnopqrstuvwxyz1234567890\n",
                encoding="utf-8",
            )
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--format", "json"])
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            rules = {finding["rule"] for finding in payload["findings"]}
            self.assertIn("openai_token", rules)
            self.assertIn("anthropic_token", rules)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

class ReferenceCopyLedgerTests(unittest.TestCase):
    """Copied-source ledger records direct OSS code copying provenance."""

    SCRIPT = SCRIPTS / "reference-copy-ledger.py"

    def test_empty_project_check_passes(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"copy-ledger-empty-{uuid.uuid4().hex}"
        try:
            tmp.mkdir(parents=True)
            result = _run([str(self.SCRIPT), "--root", str(tmp), "check"])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("no copied-source records", result.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_add_list_check_round_trip(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"copy-ledger-roundtrip-{uuid.uuid4().hex}"
        try:
            candidate = tmp / "research" / "reference-candidates" / "copy.md"
            proposal = tmp / "runtime" / "proposals" / "reference-adoption" / "copy.md"
            candidate.parent.mkdir(parents=True)
            proposal.parent.mkdir(parents=True)
            candidate.write_text("# candidate\n", encoding="utf-8")
            proposal.write_text("# proposal\n", encoding="utf-8")

            add = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "add",
                    "--source-url",
                    "https://github.com/example/project",
                    "--license",
                    "MIT",
                    "--revision",
                    "abc123",
                    "--source-path",
                    "src/helper.py",
                    "--copied-symbol",
                    "helper",
                    "--local-path",
                    "scripts/copied.py",
                    "--copy-boundary",
                    "single helper only",
                    "--candidate-card",
                    "research/reference-candidates/copy.md",
                    "--proposal",
                    "runtime/proposals/reference-adoption/copy.md",
                    "--json",
                ]
            )
            self.assertEqual(add.returncode, 0, add.stderr)
            payload = json.loads(add.stdout)
            self.assertEqual(payload["local_path"], "scripts/copied.py")
            self.assertTrue(payload["redistribution_review_required"])

            listing = _run([str(self.SCRIPT), "--root", str(tmp), "list", "--json"])
            self.assertEqual(listing.returncode, 0, listing.stderr)
            records = json.loads(listing.stdout)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["revision"], "abc123")

            check = _run([str(self.SCRIPT), "--root", str(tmp), "check"])
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            self.assertIn("1 record", check.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_missing_required_argument_is_rejected(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"copy-ledger-missing-{uuid.uuid4().hex}"
        try:
            tmp.mkdir(parents=True)
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "add",
                    "--source-url",
                    "https://github.com/example/project",
                ]
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("required", result.stderr.lower())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_local_path_outside_root_is_rejected(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"copy-ledger-outside-{uuid.uuid4().hex}"
        try:
            tmp.mkdir(parents=True)
            result = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "add",
                    "--source-url",
                    "https://github.com/example/project",
                    "--license",
                    "MIT",
                    "--revision",
                    "abc123",
                    "--source-path",
                    "src/helper.py",
                    "--local-path",
                    "../escape.py",
                    "--copy-boundary",
                    "single helper only",
                ]
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("inside project root", result.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_security_scan_ledger_finding_clears_when_record_matches(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"copy-ledger-security-{uuid.uuid4().hex}"
        try:
            proposal = tmp / "runtime" / "proposals" / "reference-adoption" / "copy.md"
            proposal.parent.mkdir(parents=True)
            proposal.write_text(
                "\n".join(
                    [
                        "- `absorption_mode`: partial_copy",
                        "- `license`: MIT",
                        "- `revision`: abc123",
                        "- `copy_boundary`: single helper only",
                        "- local target: `scripts/copied.py`",
                    ]
                ),
                encoding="utf-8",
            )

            before = _run([str(SecurityScanTests.SCRIPT), "--root", str(tmp), "--format", "json"])
            self.assertEqual(before.returncode, 0, before.stderr)
            before_rules = {finding["rule"] for finding in json.loads(before.stdout)["findings"]}
            self.assertIn("copy_ledger_missing_entry", before_rules)

            add = _run(
                [
                    str(self.SCRIPT),
                    "--root",
                    str(tmp),
                    "add",
                    "--source-url",
                    "https://github.com/example/project",
                    "--license",
                    "MIT",
                    "--revision",
                    "abc123",
                    "--source-path",
                    "src/helper.py",
                    "--local-path",
                    "scripts/copied.py",
                    "--copy-boundary",
                    "single helper only",
                    "--proposal",
                    "runtime/proposals/reference-adoption/copy.md",
                ]
            )
            self.assertEqual(add.returncode, 0, add.stderr)

            after = _run([str(SecurityScanTests.SCRIPT), "--root", str(tmp), "--format", "json"])
            self.assertEqual(after.returncode, 0, after.stderr)
            after_rules = {finding["rule"] for finding in json.loads(after.stdout)["findings"]}
            self.assertNotIn("copy_ledger_missing_entry", after_rules)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_partial_copy_artifact_missing_terms_is_flagged(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"security-scan-governance-{uuid.uuid4().hex}"
        try:
            (tmp / "runtime" / "proposals" / "reference-adoption").mkdir(parents=True)
            proposal = tmp / "runtime" / "proposals" / "reference-adoption" / "copy.md"
            proposal.write_text(
                "- `absorption_mode`: partial_copy\n- `recommended_mode`: copy helper\n",
                encoding="utf-8",
            )
            result = _run([str(SecurityScanTests.SCRIPT), "--root", str(tmp), "--format", "json"])
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            rules = {finding["rule"] for finding in payload["findings"]}
            self.assertIn("copy_governance_missing_terms", rules)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

class CreateReferenceProposalTests(unittest.TestCase):
    """The proposal draft helper is agent-facing and dry-run by default."""

    SCRIPT = SCRIPTS / "create-reference-proposal.py"

    def test_candidate_generates_proposal_dry_run(self) -> None:
        result = _run(
            [
                str(self.SCRIPT),
                "--candidate",
                "research/reference-candidates/2026-04-27-langgraph.md",
                "--topic",
                "example",
            ],
            cwd=REPO_ROOT,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"proposal draft failed:\nstdout={result.stdout}\nstderr={result.stderr}",
        )
        self.assertIn("# suggested_output:", result.stdout)
        self.assertIn("## 최종 결정 기록", result.stdout)

    def test_write_refuses_overwrite(self) -> None:
        output = (
            REPO_ROOT
            / "runtime"
            / "proposals"
            / "reference-adoption"
            / "_tmp_create_reference_proposal_smoke.md"
        )
        output.write_text("# existing\n", encoding="utf-8")
        try:
            result = _run(
                [
                    str(self.SCRIPT),
                    "--candidate",
                    "research/reference-candidates/2026-04-27-langgraph.md",
                    "--output",
                    str(output.relative_to(REPO_ROOT)),
                    "--write",
                ],
                cwd=REPO_ROOT,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to overwrite", result.stderr)
        finally:
            output.unlink(missing_ok=True)
