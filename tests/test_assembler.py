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

    def test_workflow_files(self):
        wfs = self.registry.workflow_files()
        names = [w.name for w in wfs]
        self.assertIn("feature.md", names)

    def test_env_example(self):
        path = self.registry.env_example_path()
        self.assertIsNotNone(path)


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

    def test_workflows_no_template_vars(self):
        for wf_name in ["feature.md", "bugfix.md", "_resume.md"]:
            wf = (self.out / f".github/agent-workflows/{wf_name}").read_text()
            self.assertNotIn("{{", wf, msg=f"Unresolved vars in {wf_name}")

    def test_model_tiers_json(self):
        data = json.loads((self.out / ".github/model-tiers.json").read_text())
        self.assertIn("tiers", data)
        self.assertIn("0", data["tiers"])
        self.assertIn("model", data["tiers"]["0"])

    def test_copilot_instructions_has_agents_section(self):
        content = (self.out / ".github/copilot-instructions.md").read_text()
        self.assertIn("Agent Roster", content)
        self.assertIn("Skills", content)
        self.assertIn("Workflows", content)

    def test_env_example_copied(self):
        self.assertTrue((self.out / ".env.example").exists())

    def test_platform_extras_copied(self):
        self.assertTrue((self.out / ".github/scripts/apply_model_tiers.py").exists())

    def test_idempotent(self):
        writer = FileWriter(Path(self.tmpdir), check=True)
        assembler = CopilotAssembler()
        assembler.assemble(self.registry, writer)
        self.assertTrue(writer.all_ok, writer.summary())


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


if __name__ == "__main__":
    unittest.main()
