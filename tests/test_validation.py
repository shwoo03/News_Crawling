from tests.test_support import *


class ScriptsCompileTests(unittest.TestCase):
    """Every script must byte-compile. Catches typos at PR time, not runtime."""

    def test_all_scripts_compile(self) -> None:
        import tokenize

        failures: list[str] = []
        for path in sorted(SCRIPTS.rglob("*.py")):
            try:
                with tokenize.open(path) as handle:
                    source = handle.read()
                compile(source, str(path), "exec")
            except (OSError, SyntaxError, UnicodeDecodeError) as exc:
                failures.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {exc}")
        self.assertEqual(failures, [], "scripts failed to compile:\n" + "\n".join(failures))

class ScriptHelpTests(unittest.TestCase):
    """Each primary script must produce `--help` output without errors.

    Guards against argparse misconfiguration (e.g. a `required=True` arg that
    breaks `--help` flow, or a malformed format string in a help= kwarg).
    """

    MAIN_SCRIPTS = (
        "agent-flow.py",
        "verify-skeleton.py",
        "rotate-activity-log.py",
        "wiki-lint.py",
        "bootstrap/new-project.py",
        "search-activity-log.py",
        "list-open-questions.py",
        "validate-reference-candidates.py",
        "validate-reference-proposals.py",
        "create-reference-proposal.py",
        "quality-gate.py",
        "review-queue.py",
        "upgrade-from-skeleton.py",
        "skeleton-doctor.py",
        "security-scan.py",
        "reference-copy-ledger.py",
        "generate-codemaps.py",
        "agent-autonomy-check.py",
        "completion-evidence.py",
        "resume-readiness.py",
        "skill-surface-check.py",
        "task-closeout.py",
        "convert.py",
        "verify-parity.py",
        "eval.py",
        "eval-all.py",
        "install-state.py",
        "skill-lifecycle.py",
        "cost-log.py",
        "session-snapshot.py",
        "refresh-references.py",
        "reference-intake.py",
        "verify.py",
        "portability-scan.py",
        "knowledge-search.py",
        "agent-brief.py",
        "checkpoint.py",
        "change-drift-check.py",
        "redact.py",
        "subdir-hints.py",
    )

    def test_each_main_script_prints_help(self) -> None:
        for rel in self.MAIN_SCRIPTS:
            with self.subTest(script=rel):
                result = _run([str(SCRIPTS / rel), "--help"])
                self.assertEqual(
                    result.returncode,
                    0,
                    f"--help failed for {rel}\nstdout={result.stdout}\nstderr={result.stderr}",
                )
                self.assertIn("usage:", result.stdout.lower())

class VerifySkeletonTests(unittest.TestCase):
    """`verify-skeleton.py --skip-wiki-lint` against the skeleton itself must
    exit 0. If this breaks, the structural invariants have drifted."""

    def test_skeleton_is_healthy(self) -> None:
        result = _run(
            [str(SCRIPTS / "verify-skeleton.py"), "--skip-wiki-lint"],
            cwd=REPO_ROOT,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"verify-skeleton failed:\nstdout={result.stdout}\nstderr={result.stderr}",
        )


class ScriptCatalogValidationTests(unittest.TestCase):
    def _load_verify_module(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("verify_skeleton_module", SCRIPTS / "verify-skeleton.py")
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def _catalog_root(self, catalog_text: str, extra_scripts=None) -> Path:
        tmp = REPO_ROOT / "runtime" / f"script-catalog-{uuid.uuid4().hex}"
        scripts = tmp / "scripts"
        scripts.mkdir(parents=True)
        for rel in ["agent-flow.py", *(extra_scripts or [])]:
            path = scripts / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        (scripts / "catalog.yaml").write_text(catalog_text, encoding="utf-8")
        return tmp

    def test_script_catalog_current_root_is_valid(self) -> None:
        result = _run([str(SCRIPTS / "verify-skeleton.py"), "--skip-wiki-lint"], cwd=REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_script_catalog_rejects_extra_public_command(self) -> None:
        module = self._load_verify_module()
        tmp = self._catalog_root(
            "version: 1\n"
            "public:\n"
            "  - path: scripts/agent-flow.py\n"
            "  - path: scripts/quality-gate.py\n"
            "internal:\n",
            ["quality-gate.py"],
        )
        try:
            findings: list[object] = []
            module.check_script_catalog(tmp, findings)
            self.assertIn("script_catalog_invalid", {finding.check for finding in findings})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_script_catalog_rejects_missing_internal_path(self) -> None:
        module = self._load_verify_module()
        tmp = self._catalog_root(
            "version: 1\n"
            "public:\n"
            "  - path: scripts/agent-flow.py\n"
            "internal:\n"
            "  validation:\n"
            "    - path: scripts/missing-tool.py\n",
        )
        try:
            findings: list[object] = []
            module.check_script_catalog(tmp, findings)
            details = "\n".join(finding.detail for finding in findings)
            self.assertIn("script_catalog_invalid", {finding.check for finding in findings})
            self.assertIn("scripts/missing-tool.py", details)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_command_docs_metadata_mismatch_is_reported(self) -> None:
        module = self._load_verify_module()
        tmp = self._catalog_root(
            "version: 1\n"
            "public:\n"
            "  - path: scripts/agent-flow.py\n"
            "routing:\n"
            "  modes:\n"
            "    research:\n"
            "      goal_pattern: (reference)\n"
            "      reason: ok\n"
            "      confidence: high\n"
            "      requires_confirmation: false\n"
            "      write_policy: read_only\n"
            "      signal: goal_mentions_reference\n"
            "      next_command: python3 scripts/agent-flow.py research --auto --goal \"{goal}\" --format json\n"
            "      suggested_questions:\n"
            "        - q\n"
            "    decide:\n"
            "      reason: ok\n"
            "      confidence: high\n"
            "      requires_confirmation: true\n"
            "      write_policy: read_only\n"
            "      signal: open_review_queue\n"
            "      next_command: python3 scripts/agent-flow.py decide --proposal <proposal-path> --decision accepted|rejected|deferred --by <name> --format json\n"
            "      suggested_questions:\n"
            "        - q\n"
            "    closeout:\n"
            "      goal_pattern: (verify)\n"
            "      reason: ok\n"
            "      confidence: high\n"
            "      requires_confirmation: true\n"
            "      write_policy: write_with_confirmation\n"
            "      signal: goal_mentions_closeout\n"
            "      next_command: python3 scripts/agent-flow.py closeout --goal \"{goal}\" --changed-path . --format json\n"
            "      suggested_questions:\n"
            "        - q\n"
            "    maintain:\n"
            "      goal_pattern: (system)\n"
            "      reason: ok\n"
            "      confidence: medium\n"
            "      requires_confirmation: false\n"
            "      write_policy: manual_work_required\n"
            "      signal: goal_mentions_maintain\n"
            "      next_command: manual: clarify\n"
            "      suggested_questions:\n"
            "        - q\n"
            "    build:\n"
            "      reason: ok\n"
            "      confidence: medium\n"
            "      requires_confirmation: false\n"
            "      write_policy: manual_work_required\n"
            "      signal: goal_mentions_build\n"
            "      next_command: manual: clarify\n"
            "      suggested_questions:\n"
            "        - q\n",
        )
        try:
            (tmp / "docs" / "commands").mkdir(parents=True)
            (tmp / "docs" / "commands" / "research.md").write_text(
                "---\n"
                "name: research\n"
                "intent: test\n"
                "public: true\n"
                "maps_to: python3 scripts/agent-flow.py research --auto --format json\n"
                "write_policy: write_with_confirmation\n"
                "requires_confirmation: false\n"
                "---\n"
                "# /research\n",
                encoding="utf-8",
            )
            findings: list[object] = []
            module.check_script_catalog(tmp, findings)
            self.assertIn("command_metadata_invalid", {finding.check for finding in findings})
            self.assertIn("write_policy differs", "\n".join(finding.detail for finding in findings))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class PermissionPolicyValidationTests(unittest.TestCase):
    def _load_verify_module(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("verify_skeleton_module_permissions", SCRIPTS / "verify-skeleton.py")
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_permission_policy_rejects_wildcard_shell_allow(self) -> None:
        module = self._load_verify_module()
        tmp = REPO_ROOT / "runtime" / f"permission-policy-{uuid.uuid4().hex}"
        try:
            (tmp / "config").mkdir(parents=True)
            (tmp / "config" / "policy.yaml").write_text(
                "permissions:\n"
                "  default_action: ask\n"
                "  timeout_action: deny\n"
                "  decision_values: [allow_once, allow_session, deny]\n"
                "  rules:\n"
                "    - id: unsafe\n"
                "      match: shell:*\n"
                "      action: allow\n",
                encoding="utf-8",
            )
            findings: list[object] = []
            module.check_permission_policy(tmp, findings)
            details = "\n".join(finding.detail for finding in findings)
            self.assertIn("permission_policy_invalid", {finding.check for finding in findings})
            self.assertIn("wildcard shell", details)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

class QualityGateTests(unittest.TestCase):
    """`quality-gate.py` runs the detected local validation surface."""

    SCRIPT = SCRIPTS / "quality-gate.py"

    def test_quality_gate_json_is_parseable_without_recursive_tests(self) -> None:
        result = _run(
            [str(self.SCRIPT), "--root", str(REPO_ROOT), "--skip-tests", "--format", "json"],
            cwd=REPO_ROOT,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"quality gate failed:\nstdout={result.stdout}\nstderr={result.stderr}",
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["root"], str(REPO_ROOT.resolve()))
        names = {item["name"] for item in payload["checks"]}
        self.assertIn("verify-skeleton", names)
        self.assertIn("resume-readiness", names)
        self.assertIn("skill-surface", names)
        self.assertIn("codemap-freshness", names)
        self.assertIn("python-syntax", names)

    def test_quality_gate_bad_root_exits_two(self) -> None:
        result = _run(
            [str(self.SCRIPT), "--root", str(REPO_ROOT / "does-not-exist")],
            cwd=REPO_ROOT,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("root not a directory", result.stderr)

    def test_quality_gate_treats_eval_all_fail_payload_as_failure(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"quality-gate-eval-fail-{uuid.uuid4().hex}"
        try:
            scripts = tmp / "scripts"
            scripts.mkdir(parents=True)
            shutil.copyfile(SCRIPTS / "quality-gate.py", scripts / "quality-gate.py")
            shutil.copyfile(SCRIPTS / "failure-classify.py", scripts / "failure-classify.py")
            (scripts / "eval-all.py").write_text(
                "import json\nprint(json.dumps({'results': [{'status': 'FAIL'}]}))\n",
                encoding="utf-8",
            )
            result = _run([
                str(scripts / "quality-gate.py"),
                "--root",
                str(tmp),
                "--skip-skeleton",
                "--skip-tests",
                "--skip-node",
                "--format",
                "json",
            ])
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            checks = {item["name"]: item for item in json.loads(result.stdout)["checks"]}
            self.assertEqual(checks["eval-all"]["status"], "FAIL")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class NewInternalToolTests(unittest.TestCase):
    def test_portability_scan_reports_machine_path(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"portability-{uuid.uuid4().hex}"
        try:
            tmp.mkdir(parents=True)
            (tmp / "README.md").write_text("local path: /Users/shwoo/example/project\n", encoding="utf-8")
            result = _run([str(SCRIPTS / "portability-scan.py"), "--root", str(tmp), "--format", "json", "--strict"])
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["count"], 1)
            self.assertEqual(payload["findings"][0]["check"], "home_path")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_knowledge_search_finds_index_hit(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"knowledge-search-{uuid.uuid4().hex}"
        try:
            (tmp / "knowledge").mkdir(parents=True)
            (tmp / "knowledge" / "index.md").write_text("# Index\n\ncheckout reference workflow\n", encoding="utf-8")
            result = _run([str(SCRIPTS / "knowledge-search.py"), "--root", str(tmp), "search", "checkout", "--format", "json"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertGreaterEqual(len(payload["hits"]), 1)
            self.assertIn("rrf_score", payload["hits"][0])
            self.assertIn("rank_sources", payload["hits"][0])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_knowledge_search_rank_fusion_prefers_multi_signal_hit(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"knowledge-search-fusion-{uuid.uuid4().hex}"
        try:
            (tmp / "knowledge").mkdir(parents=True)
            (tmp / "docs" / "wiki-ops").mkdir(parents=True)
            (tmp / "knowledge" / "checkout.md").write_text("# Checkout\n\ncheckout appears in title and body\n", encoding="utf-8")
            (tmp / "docs" / "wiki-ops" / "other.md").write_text("# Other\n\ncheckout appears in body only\n", encoding="utf-8")
            result = _run([str(SCRIPTS / "knowledge-search.py"), "--root", str(tmp), "search", "checkout", "--format", "json"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            hits = json.loads(result.stdout)["hits"]
            self.assertEqual(hits[0]["path"], "knowledge/checkout.md")
            self.assertGreaterEqual(len(hits[0]["rank_sources"]), 2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_agent_brief_reports_scope_and_policy(self) -> None:
        result = _run([
            str(SCRIPTS / "agent-brief.py"),
            "--root",
            str(REPO_ROOT),
            "--role",
            "security-reviewer",
            "--goal",
            "review copied code",
            "--scope",
            "scripts",
            "--write-policy",
            "read_only",
            "--format",
            "json",
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["role"], "security-reviewer")
        self.assertEqual(payload["allowed_files"], ["scripts"])
        self.assertIn("Do not modify files", "\n".join(payload["forbidden_actions"]))


class CodemapTests(unittest.TestCase):
    SCRIPT = SCRIPTS / "generate-codemaps.py"

    def test_generate_codemaps_preview_reports_areas(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"codemap-{uuid.uuid4().hex}"
        try:
            (tmp / "scripts").mkdir(parents=True)
            (tmp / "skills" / "active" / "demo").mkdir(parents=True)
            (tmp / "tests").mkdir()
            (tmp / "scripts" / "tool.py").write_text("print('ok')\n", encoding="utf-8")
            (tmp / "skills" / "active" / "demo" / "SKILL.md").write_text("---\nname: demo\n---\n", encoding="utf-8")
            (tmp / "tests" / "test_demo.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--format", "json"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("scripts", payload["areas"])
            self.assertIn("skills", payload["areas"])
            self.assertEqual(payload["written"], [])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class WikiGraphReportTests(unittest.TestCase):
    SCRIPT = SCRIPTS / "wiki-lint.py"

    def test_graph_gap_is_reported_for_related_entries(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"wiki-graph-{uuid.uuid4().hex}"
        try:
            knowledge = tmp / "knowledge"
            knowledge.mkdir(parents=True)
            (knowledge / "index.md").write_text(
                "| id | topic | status | pointer |\n"
                "| --- | --- | --- | --- |\n"
                "| K001 | checkout flow | active | `a.md:1` |\n"
                "| K002 | checkout validation | active | `b.md:1` |\n"
                "| K003 | payment shared | active | `c.md:1` |\n",
                encoding="utf-8",
            )
            (knowledge / "a.md").write_text("# A\n[[K003]]\n", encoding="utf-8")
            (knowledge / "b.md").write_text("# B\n[[K003]]\n", encoding="utf-8")
            (knowledge / "c.md").write_text("# C\n", encoding="utf-8")
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--format", "json", "--stale-days", "99999"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            graph_gap = json.loads(result.stdout)["findings"]["graph_gap"]
            self.assertTrue(any("K001 <-> K002" in item for item in graph_gap))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_knowledge_frontmatter_source_contract_warns(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"wiki-source-contract-{uuid.uuid4().hex}"
        try:
            knowledge = tmp / "knowledge"
            knowledge.mkdir(parents=True)
            (knowledge / "index.md").write_text(
                "| id | topic | status | pointer |\n"
                "| --- | --- | --- | --- |\n"
                "| K001 | source contract | active | `entry.md:1` |\n",
                encoding="utf-8",
            )
            (knowledge / "entry.md").write_text(
                "---\n"
                "id: K001\n"
                "status: active\n"
                "updated_at: 2026-05-02\n"
                "sources:\n"
                "  - missing.md:1\n"
                "---\n"
                "# Entry\n",
                encoding="utf-8",
            )
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--format", "json", "--stale-days", "99999"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            findings = json.loads(result.stdout)["findings"]["source_contract"]
            self.assertTrue(any("source reference not found" in item for item in findings))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_generate_codemaps_write_creates_index(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"codemap-write-{uuid.uuid4().hex}"
        try:
            (tmp / "scripts").mkdir(parents=True)
            (tmp / "scripts" / "tool.py").write_text("print('ok')\n", encoding="utf-8")
            result = _run([str(SCRIPTS / "generate-codemaps.py"), "--root", str(tmp), "--write", "--format", "json"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((tmp / "docs" / "CODEMAPS" / "INDEX.md").exists())
            self.assertIn("docs/CODEMAPS/INDEX.md", json.loads(result.stdout)["written"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class SkillSurfaceTests(unittest.TestCase):
    """`skill-surface-check.py` keeps skills/active canonical and artifacts synced."""

    SCRIPT = SCRIPTS / "skill-surface-check.py"

    def test_current_skill_surface_is_canonicalized(self) -> None:
        result = _run([str(self.SCRIPT), "--root", str(REPO_ROOT), "--strict", "--format", "json"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertGreaterEqual(payload["active_skills"], 1)
        self.assertTrue(payload["parity_ok"])

    def test_generated_parity_mismatch_is_rejected(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"skill-surface-{uuid.uuid4().hex}"
        try:
            active = tmp / "skills" / "active" / "demo"
            codex = tmp / ".codex" / "skills"
            claude = tmp / ".claude" / "skills" / "demo"
            active.mkdir(parents=True)
            codex.mkdir(parents=True)
            claude.mkdir(parents=True)
            (active / "SKILL.md").write_text("---\nname: demo\ndescription: demo\nstatus: active\n---\n", encoding="utf-8")
            (claude / "SKILL.md").write_text("---\nname: demo\ndescription: demo\nstatus: active\n---\n", encoding="utf-8")
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--strict", "--format", "json"])
            self.assertEqual(result.returncode, 1)
            rules = {finding["check"] for finding in json.loads(result.stdout)["findings"]}
            self.assertIn("codex_skill_parity", rules)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_missing_generated_skill_dirs_are_errors(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"skill-surface-missing-{uuid.uuid4().hex}"
        try:
            active = tmp / "skills" / "active" / "demo"
            active.mkdir(parents=True)
            (active / "SKILL.md").write_text("---\nname: demo\ndescription: demo\nstatus: active\n---\n", encoding="utf-8")
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--strict", "--format", "json"])
            self.assertEqual(result.returncode, 1)
            rules = {finding["check"] for finding in json.loads(result.stdout)["findings"]}
            self.assertIn("codex_skill_surface_missing", rules)
            self.assertIn("claude_skill_surface_missing", rules)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_duplicate_skill_name_is_rejected(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"skill-surface-duplicate-{uuid.uuid4().hex}"
        try:
            for base in ("skills/active/a", "skills/_meta/b"):
                path = tmp / base
                path.mkdir(parents=True)
                (path / "SKILL.md").write_text("---\nname: same\ndescription: demo\nstatus: active\n---\n", encoding="utf-8")
            (tmp / ".codex" / "skills").mkdir(parents=True)
            (tmp / ".claude" / "skills").mkdir(parents=True)
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--strict", "--format", "json"])
            self.assertEqual(result.returncode, 1)
            rules = {finding["check"] for finding in json.loads(result.stdout)["findings"]}
            self.assertIn("skill_name_duplicate", rules)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class ConvertSafetyTests(unittest.TestCase):
    SCRIPT = SCRIPTS / "convert.py"

    def _minimal_root(self) -> Path:
        tmp = REPO_ROOT / "runtime" / f"convert-safety-{uuid.uuid4().hex}"
        for rel in ("skills/active/demo", "agents", "rules", "mcp", ".codex/skills"):
            (tmp / rel).mkdir(parents=True)
        (tmp / "skills" / "active" / "demo" / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\n", encoding="utf-8")
        (tmp / "mcp" / "servers.yaml").write_text("servers:\n", encoding="utf-8")
        (tmp / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
        (tmp / ".codex" / "skills" / "keep.txt").write_text("keep\n", encoding="utf-8")
        return tmp

    def test_unsafe_manifest_target_does_not_delete_existing_files(self) -> None:
        tmp = self._minimal_root()
        try:
            (tmp / "manifest.yaml").write_text(
                "mappings:\n"
                "  skills:\n"
                "    source: skills/active/\n"
                "    targets:\n"
                "      codex: .\n",
                encoding="utf-8",
            )
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--format", "json"])
            self.assertEqual(result.returncode, 1)
            self.assertTrue((tmp / ".codex" / "skills" / "keep.txt").exists())
            self.assertIn("target not allowlisted", result.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_missing_source_does_not_wipe_target(self) -> None:
        tmp = self._minimal_root()
        try:
            shutil.rmtree(tmp / "skills" / "active")
            result = _run([str(self.SCRIPT), "--root", str(tmp), "--format", "json"])
            self.assertEqual(result.returncode, 1)
            self.assertTrue((tmp / ".codex" / "skills" / "keep.txt").exists())
            self.assertIn("source missing", result.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class VerifyParityTests(unittest.TestCase):
    CONVERT = SCRIPTS / "convert.py"
    SCRIPT = SCRIPTS / "verify-parity.py"

    def _root(self) -> Path:
        tmp = REPO_ROOT / "runtime" / f"verify-parity-{uuid.uuid4().hex}"
        for rel in ("skills/active/demo/nested", "agents", "rules", "mcp"):
            (tmp / rel).mkdir(parents=True)
        (tmp / "skills" / "active" / "demo" / "SKILL.md").write_text("---\nname: demo\ndescription: demo\n---\n", encoding="utf-8")
        (tmp / "skills" / "active" / "demo" / "nested" / "note.txt").write_text("canonical\n", encoding="utf-8")
        (tmp / "mcp" / "servers.yaml").write_text("servers:\n", encoding="utf-8")
        (tmp / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
        return tmp

    def test_recursive_content_drift_is_rejected(self) -> None:
        tmp = self._root()
        try:
            convert = _run([str(self.CONVERT), "--root", str(tmp)])
            self.assertEqual(convert.returncode, 0, convert.stdout + convert.stderr)
            (tmp / ".codex" / "skills" / "demo" / "SKILL.md").write_text("changed\n", encoding="utf-8")
            result = _run([str(self.SCRIPT), "--root", str(tmp)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("changed_files", result.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_nested_content_drift_is_rejected(self) -> None:
        tmp = self._root()
        try:
            convert = _run([str(self.CONVERT), "--root", str(tmp)])
            self.assertEqual(convert.returncode, 0, convert.stdout + convert.stderr)
            (tmp / ".claude" / "skills" / "demo" / "nested" / "note.txt").write_text("drift\n", encoding="utf-8")
            result = _run([str(self.SCRIPT), "--root", str(tmp)])
            self.assertEqual(result.returncode, 1)
            self.assertIn("nested/note.txt", result.stdout)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

class ListOpenQuestionsTests(unittest.TestCase):
    """`scripts/list-open-questions.py` must exit 0 on a clean skeleton and
    must detect a real [NEEDS CLARIFICATION: ...] marker when one is injected
    outside any code fence. Guards the marker aggregator behavior documented
    in rules/common/README.md."""

    SCRIPT = SCRIPTS / "list-open-questions.py"

    def test_clean_skeleton_reports_zero(self) -> None:
        result = _run([str(self.SCRIPT), "--count"], cwd=REPO_ROOT)
        self.assertEqual(
            result.returncode, 0, f"failed:\nstdout={result.stdout}\nstderr={result.stderr}"
        )
        self.assertEqual(result.stdout.strip(), "0")

    def test_real_marker_is_detected_and_strict_exits_nonzero(self) -> None:
        # Create a temp doc inside docs/ (not runtime/tmp-, which is skipped
        # by SKIP_DIR_PREFIXES). Always clean up.
        scratch = REPO_ROOT / "docs" / "_tmp_open_q_smoke.md"
        scratch.write_text(
            "# tmp\n- [NEEDS CLARIFICATION: smoke-test real question?]\n",
            encoding="utf-8",
        )
        try:
            result = _run([str(self.SCRIPT), "--strict"], cwd=REPO_ROOT)
            self.assertNotEqual(result.returncode, 0, "strict mode did not flag a real marker")
            self.assertIn("smoke-test real question?", result.stdout)
        finally:
            scratch.unlink(missing_ok=True)

class RotateActivityLogArgParseTests(unittest.TestCase):
    """Surface-level argparse contract for rotate-activity-log: unknown flags
    must fail fast with a non-zero exit. Guards against a future refactor that
    silently drops an unknown option on the floor."""

    def test_unknown_flag_is_rejected(self) -> None:
        result = _run(
            [str(SCRIPTS / "rotate-activity-log.py"), "--definitely-not-a-flag"],
            cwd=REPO_ROOT,
        )
        self.assertNotEqual(
            result.returncode,
            0,
            f"unknown flag was accepted:\nstdout={result.stdout}\nstderr={result.stderr}",
        )
