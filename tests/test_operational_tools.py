from tests.test_support import *


class OperationalToolTests(unittest.TestCase):
    def test_tool_health_summarizes_normalized_events(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"tool-health-{uuid.uuid4().hex}"
        try:
            (tmp / "runtime" / "tool-output-sidecars").mkdir(parents=True)
            (tmp / "runtime" / "tool-output-sidecars" / "full.txt").write_text("full", encoding="utf-8")
            events = [
                {"tool_call": {"tool": "shell", "status": "completed", "summary": "ok", "normalized_status": "success"}},
                {"tool_call": {"tool": "shell", "status": "failed", "summary": "bad", "normalized_status": "failure"}},
                {"tool_call": {"tool": "browser", "status": "completed", "summary": "", "normalized_status": "empty", "sidecar_path": "runtime/tool-output-sidecars/full.txt"}},
            ]
            (tmp / "runtime" / "activity-log.jsonl").write_text("\n".join(json.dumps(item) for item in events) + "\n", encoding="utf-8")
            result = _run([str(SCRIPTS / "tool-health.py"), "--root", str(tmp), "--format", "json", "summary"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            tools = {item["tool"]: item for item in json.loads(result.stdout)["tools"]}
            self.assertEqual(tools["shell"]["calls"], 2)
            self.assertEqual(tools["shell"]["failure"], 1)
            self.assertEqual(tools["browser"]["empty"], 1)
            check = _run([str(SCRIPTS / "tool-health.py"), "--root", str(tmp), "check"])
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_mcp_audit_reports_npx_metadata_gaps(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"mcp-audit-{uuid.uuid4().hex}"
        try:
            (tmp / "mcp").mkdir(parents=True)
            (tmp / "mcp" / "servers.yaml").write_text(
                "servers:\n"
                "  - name: github\n"
                "    transport: stdio\n"
                "    command: npx\n"
                "    args: ['-y', '@modelcontextprotocol/server-github']\n"
                "    audit_passed: false\n",
                encoding="utf-8",
            )
            result = _run([str(SCRIPTS / "mcp-audit.py"), "--root", str(tmp), "--format", "json", "check"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("npx " + "-y", "\n".join(payload["findings"]))
            strict = _run([str(SCRIPTS / "mcp-audit.py"), "--root", str(tmp), "--strict", "check"])
            self.assertEqual(strict.returncode, 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_permission_evaluator_handles_shell_and_confirmation_required(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"permission-eval-{uuid.uuid4().hex}"
        try:
            (tmp / "config").mkdir(parents=True)
            (tmp / "config" / "policy.yaml").write_text(
                "confirmation_required:\n"
                "  - git_push\n"
                "permissions:\n"
                "  default_action: ask\n"
                "  timeout_action: deny\n"
                "  decision_values: [allow_once, allow_session, deny]\n"
                "  rules:\n"
                "    - id: shell_wildcard\n"
                "      match: shell:*\n"
                "      action: deny\n",
                encoding="utf-8",
            )
            shell = _run([str(SCRIPTS / "permission-evaluate.py"), "--root", str(tmp), "--format", "json", "evaluate", "--action", "shell", "--resource", "*"])
            self.assertEqual(json.loads(shell.stdout)["decision"], "deny")
            push = _run([str(SCRIPTS / "permission-evaluate.py"), "--root", str(tmp), "--format", "json", "evaluate", "--action", "git_push"])
            self.assertEqual(json.loads(push.stdout)["decision"], "ask")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_path_safety_and_permission_evaluator_deny_unsafe_write(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"path-safety-{uuid.uuid4().hex}"
        try:
            (tmp / "config").mkdir(parents=True)
            (tmp / "config" / "policy.yaml").write_text(
                "confirmation_required:\n"
                "  - file_delete\n"
                "permissions:\n"
                "  default_action: ask\n"
                "  timeout_action: deny\n"
                "  decision_values: [allow_once, allow_session, deny]\n"
                "  rules: []\n",
                encoding="utf-8",
            )
            safe = _run([str(SCRIPTS / "path-safety.py"), "--root", str(tmp), "--format", "json", "check", "--path", "docs/file.md", "--operation", "write"])
            self.assertEqual(safe.returncode, 0, safe.stdout + safe.stderr)
            self.assertEqual(json.loads(safe.stdout)["decision"], "ask")
            denied = _run([str(SCRIPTS / "path-safety.py"), "--root", str(tmp), "--format", "json", "check", "--path", ".env", "--operation", "write"])
            self.assertEqual(denied.returncode, 1)
            self.assertEqual(json.loads(denied.stdout)["decision"], "deny")
            perm = _run([str(SCRIPTS / "permission-evaluate.py"), "--root", str(tmp), "--format", "json", "evaluate", "--action", "file_write", "--resource", ".env"])
            payload = json.loads(perm.stdout)
            self.assertEqual(payload["decision"], "deny")
            self.assertEqual(payload["matched_rule"], "path_safety")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_tool_guardrail_reports_repeated_failures(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"tool-guardrail-{uuid.uuid4().hex}"
        try:
            (tmp / "runtime").mkdir(parents=True)
            event = {"tool_call": {"tool": "shell", "status": "failed", "resource": "pytest", "failure_type": "format"}}
            (tmp / "runtime" / "activity-log.jsonl").write_text("\n".join(json.dumps(event) for _ in range(3)) + "\n", encoding="utf-8")
            result = _run([str(SCRIPTS / "tool-guardrail.py"), "--root", str(tmp), "--format", "json", "check"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["repeated_failures"][0]["action"], "block")
            strict = _run([str(SCRIPTS / "tool-guardrail.py"), "--root", str(tmp), "--format", "json", "--strict", "check"])
            self.assertEqual(strict.returncode, 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_install_profiles_plan_reads_canonical_config(self) -> None:
        result = _run([str(SCRIPTS / "install-profiles.py"), "--root", str(REPO_ROOT), "--format", "json", "plan", "--profile", "cli"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["profile"], "cli")
        self.assertIn("cli", payload["components"])

    def test_skill_stocktake_reports_improve_and_merge(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"skill-stocktake-{uuid.uuid4().hex}"
        try:
            for rel in ("skills/active/a", "skills/_candidates/b"):
                (tmp / rel).mkdir(parents=True)
            (tmp / "runtime").mkdir(parents=True)
            skill_a = "---\nname: demo\ntrigger:\n  - same trigger\nstatus: active\n---\n# Demo\n"
            skill_b = "---\nname: other\ntrigger:\n  - same trigger\nstatus: candidate\n---\n# Other\n"
            (tmp / "skills" / "active" / "a" / "SKILL.md").write_text(skill_a, encoding="utf-8")
            (tmp / "skills" / "_candidates" / "b" / "SKILL.md").write_text(skill_b, encoding="utf-8")
            result = _run([str(SCRIPTS / "skill-stocktake.py"), "--root", str(tmp), "--format", "json", "report"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            recs = {item["name"]: item["recommendation"] for item in json.loads(result.stdout)["skills"]}
            self.assertEqual(recs["demo"], "merge")
            self.assertEqual(recs["other"], "merge")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_plugin_manifest_check_validates_marketplace(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"plugin-check-{uuid.uuid4().hex}"
        try:
            (tmp / ".codex-plugin").mkdir(parents=True)
            (tmp / ".claude-plugin").mkdir(parents=True)
            (tmp / ".agents" / "plugins").mkdir(parents=True)
            (tmp / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
            (tmp / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")
            plugin = {"name": "demo", "version": "0.1.0", "description": "demo", "entrypoint": "AGENTS.md"}
            (tmp / ".codex-plugin" / "plugin.json").write_text(json.dumps(plugin), encoding="utf-8")
            claude = dict(plugin)
            claude["entrypoint"] = "CLAUDE.md"
            (tmp / ".claude-plugin" / "plugin.json").write_text(json.dumps(claude), encoding="utf-8")
            (tmp / ".agents" / "plugins" / "marketplace.json").write_text(json.dumps({"plugins": [{"id": "demo", "name": "Demo", "version": "0.1.0", "path": "."}]}), encoding="utf-8")
            ok = _run([str(SCRIPTS / "plugin-manifest-check.py"), "--root", str(tmp), "check"])
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            (tmp / ".agents" / "plugins" / "marketplace.json").write_text(json.dumps({"plugins": [{"id": "other", "name": "Demo", "version": "0.1.0", "path": "."}]}), encoding="utf-8")
            bad = _run([str(SCRIPTS / "plugin-manifest-check.py"), "--root", str(tmp), "check"])
            self.assertEqual(bad.returncode, 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_agent_brief_reads_team_registry(self) -> None:
        result = _run([
            str(SCRIPTS / "agent-brief.py"),
            "--root",
            str(REPO_ROOT),
            "--role",
            "security-reviewer",
            "--goal",
            "audit",
            "--format",
            "json",
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["role"], "security-reviewer")
        self.assertIn("mcp-audit.py", "\n".join(payload["recommended_checks"]))
        self.assertIn("subdirectory_hints", payload)

    def test_subdir_hints_are_included_for_scoped_brief(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"agent-brief-hints-{uuid.uuid4().hex}"
        try:
            (tmp / "config").mkdir(parents=True)
            (tmp / "scripts").mkdir()
            shutil.copyfile(SCRIPTS / "agent-brief.py", tmp / "scripts" / "agent-brief.py")
            shutil.copyfile(SCRIPTS / "subdir-hints.py", tmp / "scripts" / "subdir-hints.py")
            (tmp / "config" / "agent-team.yaml").write_text(
                "specialists:\n"
                "  security-reviewer:\n"
                "    mission: audit\n"
                "    write_policy: read_only\n",
                encoding="utf-8",
            )
            (tmp / "pkg").mkdir()
            (tmp / "pkg" / "AGENTS.md").write_text("# Local Rules\n\nDo not edit generated files.\n", encoding="utf-8")
            result = _run([
                str(tmp / "scripts" / "agent-brief.py"),
                "--root",
                str(tmp),
                "--role",
                "security-reviewer",
                "--goal",
                "audit",
                "--scope",
                "pkg",
                "--format",
                "json",
            ])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            hints = json.loads(result.stdout)["subdirectory_hints"]
            self.assertTrue(any(item["path"] == "pkg/AGENTS.md" for item in hints))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_redaction_masks_secret_like_values(self) -> None:
        result = _run([
            str(SCRIPTS / "redact.py"),
            "--text",
            "token=" + "abcdefghijklmnopqrstuvwxyz123456" + " and sk-" + "abcdefghijklmnopqrstuvwxyz",
            "--format",
            "json",
        ])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        redacted = json.loads(result.stdout)["redacted"]
        self.assertIn("[REDACTED:", redacted)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz123456", redacted)

    def test_reference_task_queue_check_rejects_unknown_action_and_bad_transition(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"reference-task-invalid-{uuid.uuid4().hex}"
        try:
            (tmp / "runtime").mkdir(parents=True)
            events = [
                {"ts": "2026-05-02T00:00:00Z", "action": "add", "id": "t1", "target": "repo", "goal": "g"},
                {"ts": "2026-05-02T00:01:00Z", "action": "complete", "id": "t1"},
                {"ts": "2026-05-02T00:02:00Z", "action": "complete", "id": "t1"},
                {"ts": "2026-05-02T00:03:00Z", "action": "mystery", "id": "t1"},
            ]
            (tmp / "runtime" / "reference-tasks.jsonl").write_text(
                "".join(json.dumps(item) + "\n" for item in events),
                encoding="utf-8",
            )
            result = _run([str(SCRIPTS / "reference-task-queue.py"), "--root", str(tmp), "check", "--format", "json"])
            self.assertEqual(result.returncode, 1)
            findings = "\n".join(json.loads(result.stdout)["findings"])
            self.assertIn("unknown action", findings)
            self.assertIn("after terminal status", findings)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_change_drift_check_warns_for_script_without_supporting_change(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"change-drift-{uuid.uuid4().hex}"
        try:
            (tmp / "scripts").mkdir(parents=True)
            subprocess.run(["git", "init"], cwd=tmp, capture_output=True, text=True, encoding="utf-8", timeout=30)
            (tmp / "scripts" / "tool.py").write_text("print('new')\n", encoding="utf-8")
            result = _run([str(SCRIPTS / "change-drift-check.py"), "--root", str(tmp), "--format", "json"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["findings"])
            self.assertEqual(payload["findings"][0]["check"], "change_set_drift")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_failure_classifier_maps_common_categories(self) -> None:
        examples = {
            "request timed out after 30s": "timeout",
            "401 unauthorized invalid api key": "auth",
            "invalid JSON parse error": "format",
            "blocked by policy outside repo": "policy",
        }
        for text, expected in examples.items():
            with self.subTest(text=text):
                result = _run([str(SCRIPTS / "failure-classify.py"), "--text", text, "--format", "json"])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["category"], expected)

    def test_markdown_sanitize_previews_and_applies_conservative_fixes(self) -> None:
        tmp = REPO_ROOT / "runtime" / f"markdown-sanitize-{uuid.uuid4().hex}"
        try:
            tmp.mkdir(parents=True)
            doc = tmp / "bad.md"
            doc.write_text("```markdown\n# Wrapped\n```", encoding="utf-8")
            preview = _run([str(SCRIPTS / "markdown-sanitize.py"), "--root", str(tmp), "--path", "bad.md", "--format", "json"])
            self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
            payload = json.loads(preview.stdout)
            self.assertEqual(len(payload["findings"]), 1)
            self.assertIn("unwrap_whole_document_fence", payload["findings"][0]["fixes"])
            self.assertEqual(doc.read_text(encoding="utf-8"), "```markdown\n# Wrapped\n```")
            applied = _run([str(SCRIPTS / "markdown-sanitize.py"), "--root", str(tmp), "--path", "bad.md", "--apply", "--format", "json"])
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            self.assertEqual(doc.read_text(encoding="utf-8"), "# Wrapped\n")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_schema_check_passes_and_rejects_missing_required_field(self) -> None:
        ok = _run([str(SCRIPTS / "schema-check.py"), "--root", str(REPO_ROOT), "--format", "json"])
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        tmp = REPO_ROOT / "runtime" / f"schema-check-{uuid.uuid4().hex}"
        try:
            (tmp / "schemas").mkdir(parents=True)
            shutil.copytree(REPO_ROOT / "schemas", tmp / "schemas", dirs_exist_ok=True)
            (tmp / "runtime").mkdir()
            bad = {
                "ts": "2026-05-02T00:00:00Z",
                "event": "convert_completed",
                "project": "demo",
                "skeleton_version": "v1",
                "source_commit": None,
                "requested_profile": "full-canonical",
                "selected_components": ["canonical"],
                "generated_paths": [],
                "preserved_paths": []
            }
            (tmp / "runtime" / "install-state.jsonl").write_text(json.dumps(bad) + "\n", encoding="utf-8")
            (tmp / "scripts").mkdir()
            (tmp / "scripts" / "catalog.yaml").write_text(
                "public:\n  - path: scripts/agent-flow.py\nrouting:\n  modes:\n    decide:\n    research:\n    closeout:\n    maintain:\n    build:\n",
                encoding="utf-8",
            )
            result = _run([str(SCRIPTS / "schema-check.py"), "--root", str(tmp), "--format", "json"])
            self.assertEqual(result.returncode, 1)
            self.assertIn("validation_status", "\n".join(json.loads(result.stdout)["findings"]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
