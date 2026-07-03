"""Tests for the assembler package — end-to-end assembly from canonical definitions."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure scripts/ is importable.
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

CANONICAL_DIR = Path(__file__).resolve().parent.parent / "canonical"

from assembler.registry import CanonicalRegistry
from assembler.writer import FileWriter
from assembler.templates import substitute_vars
from assembler.platforms.copilot import CopilotAssembler
from assembler.platforms.claude import ClaudeAssembler


class TestSubstituteVars(unittest.TestCase):

    def test_replaces_known_vars(self):
        result = substitute_vars("Read {{FOO}} first", {"FOO": "bar"})
        self.assertEqual(result, "Read bar first")

    def test_raises_on_unresolved_vars(self):
        with self.assertRaises(ValueError) as ctx:
            substitute_vars("{{UNKNOWN}} here", {})
        self.assertIn("UNKNOWN", str(ctx.exception))

    def test_no_placeholders_passthrough(self):
        result = substitute_vars("no vars here", {"A": "b"})
        self.assertEqual(result, "no vars here")


class TestCanonicalRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.registry = CanonicalRegistry.load(CANONICAL_DIR)

    def test_loads_agents(self):
        self.assertGreater(len(self.registry.agents), 0)
        slugs = [a["slug"] for a in self.registry.agents]
        self.assertIn("orchestrator", slugs)

    def test_loads_skills(self):
        self.assertGreater(len(self.registry.skills), 0)
        slugs = [s["slug"] for s in self.registry.skills]
        self.assertIn("read-jira-ticket", slugs)
        self.assertIn("resume-workflow", slugs)

    def test_loads_instructions(self):
        self.assertGreater(len(self.registry.instructions), 0)

    def test_loads_prompts(self):
        self.assertGreater(len(self.registry.prompts), 0)

    def test_agent_body(self):
        body = self.registry.agent_body("orchestrator")
        self.assertIn("Orchestrator", body)

    def test_skill_body(self):
        body = self.registry.skill_body("read-jira-ticket")
        self.assertIn("JIRA", body)

    def test_model_for_tier(self):
        model = self.registry.model_for_tier(2, "copilot")
        self.assertIn("Sonnet", model)

    def test_env_example(self):
        path = self.registry.env_example_path()
        self.assertIsNotNone(path)

    def test_no_workflow_files_method(self):
        self.assertFalse(hasattr(self.registry, 'workflow_files'),
                         "workflow_files() should have been removed")


class TestFileWriter(unittest.TestCase):

    def test_write_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = FileWriter(Path(tmpdir))
            writer.put("a/b.txt", "hello")
            self.assertEqual((Path(tmpdir) / "a" / "b.txt").read_text(), "hello")
            self.assertIn("Wrote 1 file(s)", writer.summary())

    def test_check_mode_all_ok(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "test.txt").write_text("content")
            writer = FileWriter(Path(tmpdir), check=True)
            writer.put("test.txt", "content")
            self.assertTrue(writer.all_ok)

    def test_check_mode_detects_diff(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "test.txt").write_text("old")
            writer = FileWriter(Path(tmpdir), check=True)
            writer.put("test.txt", "new")
            self.assertFalse(writer.all_ok)

    def test_check_mode_detects_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = FileWriter(Path(tmpdir), check=True)
            writer.put("missing.txt", "content")
            self.assertFalse(writer.all_ok)


class TestCopilotAssembly(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.registry = CanonicalRegistry.load(CANONICAL_DIR)
        cls.tmpdir = tempfile.mkdtemp()
        writer = FileWriter(Path(cls.tmpdir))
        assembler = CopilotAssembler()
        assembler.assemble(cls.registry, writer)
        cls.out = Path(cls.tmpdir)

    def test_agents_have_frontmatter(self):
        agent = (self.out / ".github/agents/orchestrator.agent.md").read_text()
        self.assertTrue(agent.startswith("---"))
        self.assertIn("model:", agent)
        self.assertIn("tools:", agent)

    def test_skills_have_frontmatter(self):
        skill = (self.out / ".github/skills/read-jira-ticket/SKILL.md").read_text()
        self.assertTrue(skill.startswith("---"))
        self.assertIn("name: read-jira-ticket", skill)
        self.assertIn("description:", skill)

    def test_skill_scripts_copied(self):
        self.assertTrue((self.out / ".github/skills/read-jira-ticket/scripts/fetch_jira.py").exists())
        self.assertTrue((self.out / ".github/skills/git-operations/scripts/git_helper.py").exists())

    def test_instructions_have_frontmatter(self):
        instr = (self.out / ".github/instructions/commit-conventions.instructions.md").read_text()
        self.assertTrue(instr.startswith("---"))
        self.assertIn("description:", instr)

    def test_prompts_have_frontmatter(self):
        prompt = (self.out / ".github/prompts/feature.prompt.md").read_text()
        self.assertTrue(prompt.startswith("---"))
        self.assertIn("agent:", prompt)

    def test_resume_workflow_skill_generated(self):
        skill = (self.out / ".github/skills/resume-workflow/SKILL.md").read_text()
        self.assertTrue(skill.startswith("---"))
        self.assertIn("resume-workflow", skill)

    def test_no_agent_workflows_dir(self):
        self.assertFalse((self.out / ".github/agent-workflows").exists(),
                         "agent-workflows/ dir should not be generated")

    def test_model_tiers_json(self):
        data = json.loads((self.out / ".github/model-tiers.json").read_text())
        self.assertIn("tiers", data)
        self.assertIn("0", data["tiers"])
        self.assertIn("model", data["tiers"]["0"])

    def test_copilot_instructions_has_agents_section(self):
        content = (self.out / ".github/copilot-instructions.md").read_text()
        self.assertIn("Agent Roster", content)
        self.assertIn("Skills", content)
        self.assertNotIn("agent-workflows", content,
                         "copilot-instructions.md should not reference agent-workflows/")

    def test_env_example_copied(self):
        self.assertTrue((self.out / ".env.example").exists())

    def test_platform_extras_copied(self):
        self.assertTrue((self.out / ".github/scripts/apply_model_tiers.py").exists())

    def test_idempotent(self):
        writer = FileWriter(Path(self.tmpdir), check=True)
        assembler = CopilotAssembler()
        assembler.assemble(self.registry, writer)
        self.assertTrue(writer.all_ok, writer.summary())

    def test_state_schema_generated(self):
        self.assertTrue(
            (self.out / ".github/state/SCHEMA.md").exists(),
            "Missing .github/state/SCHEMA.md",
        )
        content = (self.out / ".github/state/SCHEMA.md").read_text()
        self.assertIn("STATE_BLOCK", content)
        self.assertIn("manage-state", content)

    def test_state_template_generated(self):
        self.assertTrue(
            (self.out / ".github/state/workflow-state.tpl.md").exists(),
            "Missing .github/state/workflow-state.tpl.md",
        )
        content = (self.out / ".github/state/workflow-state.tpl.md").read_text()
        self.assertIn("STATE_BLOCK:META:BEGIN", content)
        self.assertIn("STATE_BLOCK:PHASE_LOG:BEGIN", content)
        # All 8 blocks from the schema must be present
        for block in ["META", "PHASE", "UNDERSTANDING", "RESEARCH", "PLAN", "IMPLEMENTATION", "REVIEW", "PHASE_LOG"]:
            self.assertIn(f"STATE_BLOCK:{block}:BEGIN", content, f"Missing block {block}")
        # No unresolved compile-time {{VAR}} placeholders (state files use <PLACEHOLDER> syntax)
        self.assertNotIn("{{", content, "Unresolved {{VAR}} in workflow-state.tpl.md")

    def test_artifacts_schema_generated(self):
        self.assertTrue(
            (self.out / ".github/artifacts/SCHEMA.md").exists(),
            "Missing .github/artifacts/SCHEMA.md",
        )
        content = (self.out / ".github/artifacts/SCHEMA.md").read_text()
        self.assertIn("REGISTRY.md", content)
        self.assertIn("register-artifact", content)

    def test_artifacts_registry_not_generated(self):
        # The assembler must NOT generate REGISTRY.md — it is agent-managed.
        self.assertFalse(
            (self.out / ".github/artifacts/REGISTRY.md").exists(),
            "Assembler must not generate REGISTRY.md",
        )

    def test_new_skills_assembled(self):
        self.assertTrue(
            (self.out / ".github/skills/manage-state/SKILL.md").exists(),
            "Missing manage-state skill",
        )
        self.assertTrue(
            (self.out / ".github/skills/register-artifact/SKILL.md").exists(),
            "Missing register-artifact skill",
        )


class TestClaudeAssembly(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.registry = CanonicalRegistry.load(CANONICAL_DIR)
        cls.tmpdir = tempfile.mkdtemp()
        writer = FileWriter(Path(cls.tmpdir))
        assembler = ClaudeAssembler()
        assembler.assemble(cls.registry, writer)
        cls.out = Path(cls.tmpdir)

    def test_generates_command_files(self):
        for agent in self.registry.agents:
            slug = agent["slug"]
            self.assertTrue(
                (self.out / f".claude/commands/{slug}.md").exists(),
                f"Missing {slug}.md",
            )

    def test_command_has_preamble(self):
        content = (self.out / ".claude/commands/orchestrator.md").read_text()
        self.assertIn("CLAUDE.md", content)
        self.assertIn("Orchestrator", content)


class TestProtectionMechanisms(unittest.TestCase):
    """Tests for safeguards against trampling agent-managed files."""

    @classmethod
    def setUpClass(cls):
        cls.registry = CanonicalRegistry.load(CANONICAL_DIR)

    def test_state_archive_protection(self):
        """When state/archive/ exists and is not empty, skip state assembly and warn."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Create a state/archive/ directory with a file (simulating archived state)
            archive_dir = tmppath / ".github" / "state" / "archive"
            archive_dir.mkdir(parents=True)
            (archive_dir / "PROJ-123.md").write_text("archived state")
            
            # Assemble — should skip state and warn
            writer = FileWriter(tmppath)
            assembler = CopilotAssembler()
            assembler.assemble(self.registry, writer)
            
            # Check that warning was issued
            summary = writer.summary()
            self.assertIn("state/archive/", summary)
            self.assertIn("Skipping state assembly", summary)
            
            # Check that state template files were NOT written (protection worked)
            self.assertFalse(
                (tmppath / ".github" / "state" / "workflow-state.tpl.md").exists(),
                "State template should not be written when archive exists"
            )

    def test_artifacts_protection(self):
        """When artifacts/ directory exists and is not empty, skip artifacts assembly and warn."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Create an artifacts/ directory with REGISTRY.md (simulating accumulated registry)
            artifacts_dir = tmppath / ".github" / "artifacts"
            artifacts_dir.mkdir(parents=True)
            (artifacts_dir / "REGISTRY.md").write_text("accumulated workflows")
            
            # Assemble — should skip artifacts and warn
            writer = FileWriter(tmppath)
            assembler = CopilotAssembler()
            assembler.assemble(self.registry, writer)
            
            # Check that warning was issued
            summary = writer.summary()
            self.assertIn("artifacts/REGISTRY.md", summary)
            self.assertIn("Skipping artifacts assembly", summary)
            
            # Check that REGISTRY.md was NOT overwritten
            existing = (artifacts_dir / "REGISTRY.md").read_text()
            self.assertEqual(existing, "accumulated workflows", "REGISTRY.md should not be overwritten")
            
            # Check that schema file was NOT written (protection worked)
            self.assertFalse(
                (tmppath / ".github" / "artifacts" / "SCHEMA.md").exists(),
                "Artifacts schema should not be written when registry exists"
            )

    def test_both_protected_dirs_exist(self):
        """When both state/archive/ and artifacts/ exist, both should be skipped with warnings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Create both protected directories
            archive_dir = tmppath / ".github" / "state" / "archive"
            archive_dir.mkdir(parents=True)
            (archive_dir / "PROJ-456.md").write_text("archived state")
            
            artifacts_dir = tmppath / ".github" / "artifacts"
            artifacts_dir.mkdir(parents=True)
            (artifacts_dir / "REGISTRY.md").write_text("accumulated workflows")
            
            # Assemble
            writer = FileWriter(tmppath)
            assembler = CopilotAssembler()
            assembler.assemble(self.registry, writer)
            
            # Check that BOTH warnings are issued
            summary = writer.summary()
            self.assertIn("state/archive/", summary)
            self.assertIn("artifacts/REGISTRY.md", summary)

    def test_check_protected_dir_empty_dir_not_protected(self):
        """Empty directories should not trigger protection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Create empty state/ directory (should not trigger protection)
            state_dir = tmppath / ".github" / "state"
            state_dir.mkdir(parents=True)
            
            writer = FileWriter(tmppath)
            # check_protected_dir should return False for empty directory
            self.assertFalse(writer.check_protected_dir(".github/state"))

    def test_nonexistent_dir_not_protected(self):
        """Nonexistent directories should not trigger protection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            writer = FileWriter(tmppath)
            # check_protected_dir should return False for nonexistent directory
            self.assertFalse(writer.check_protected_dir(".github/state/archive"))

    def test_file_writer_add_warning(self):
        """FileWriter.add_warning() should add warnings to summary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = FileWriter(Path(tmpdir))
            writer.add_warning("Test warning 1")
            writer.add_warning("Test warning 2")
            
            summary = writer.summary()
            self.assertIn("Test warning 1", summary)
            self.assertIn("Test warning 2", summary)


if __name__ == "__main__":
    unittest.main()
