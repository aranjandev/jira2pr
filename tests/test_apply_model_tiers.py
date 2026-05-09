"""Tests for apply_model_tiers.py — patch_model_in_frontmatter logic."""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "canonical/platform-extras/copilot/apply_model_tiers.py"


def _load():
    spec = importlib.util.spec_from_file_location("apply_model_tiers", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


class TestPatchModelInFrontmatter(unittest.TestCase):

    def test_inserts_model_when_field_absent(self):
        content = "---\nname: my-agent\ndescription: does stuff\n---\n# Body\n"
        result = mod.patch_model_in_frontmatter(content, "Claude Sonnet 4")
        self.assertIn('model: "Claude Sonnet 4"', result)
        # Existing fields preserved
        self.assertIn("name: my-agent", result)
        self.assertIn("# Body", result)

    def test_replaces_existing_model_field(self):
        content = '---\nname: agent\nmodel: "old-model-name"\n---\n# Body\n'
        result = mod.patch_model_in_frontmatter(content, "Claude Haiku 3.5")
        self.assertIn('model: "Claude Haiku 3.5"', result)
        self.assertNotIn("old-model-name", result)
        # Field only appears once
        self.assertEqual(result.count("model:"), 1)

    def test_preserves_all_other_frontmatter_fields(self):
        content = (
            "---\n"
            "description: the description\n"
            "tools: [read, edit]\n"
            "user-invocable: true\n"
            "---\n"
            "\n# Agent Title\nContent here.\n"
        )
        result = mod.patch_model_in_frontmatter(content, "gpt-4o")
        self.assertIn("description: the description", result)
        self.assertIn("tools: [read, edit]", result)
        self.assertIn("user-invocable: true", result)
        self.assertIn("# Agent Title", result)

    def test_inserts_whole_frontmatter_when_none_present(self):
        content = "# Just a title\nNo frontmatter here.\n"
        result = mod.patch_model_in_frontmatter(content, "Claude Sonnet 4")
        self.assertIn("---", result)
        self.assertIn('model: "Claude Sonnet 4"', result)
        # Original content still there
        self.assertIn("# Just a title", result)

    def test_model_line_is_inside_frontmatter_block(self):
        content = "---\nname: test\n---\n# Title\n"
        result = mod.patch_model_in_frontmatter(content, "Claude Sonnet 4")
        lines = result.splitlines()
        dashes = [i for i, ln in enumerate(lines) if ln.strip() == "---"]
        self.assertGreaterEqual(len(dashes), 2)
        frontmatter_lines = lines[dashes[0] + 1 : dashes[1]]
        self.assertTrue(
            any("model:" in ln for ln in frontmatter_lines),
            f"Expected model: inside frontmatter, got: {frontmatter_lines}",
        )

    def test_model_value_is_quoted(self):
        content = "---\nname: a\n---\n"
        result = mod.patch_model_in_frontmatter(content, "My Model Name")
        self.assertIn('model: "My Model Name"', result)

    def test_idempotent_replacement(self):
        content = "---\nname: a\n---\n"
        first = mod.patch_model_in_frontmatter(content, "TargetModel")
        second = mod.patch_model_in_frontmatter(first, "TargetModel")
        self.assertEqual(first, second)


class TestMainIntegration(unittest.TestCase):
    """Integration test: run main() against a temp directory of agent files."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.agents_dir = Path(self.tmpdir.name) / "agents"
        self.agents_dir.mkdir()
        self.scripts_dir = Path(self.tmpdir.name) / "scripts"
        self.scripts_dir.mkdir()

        # Write a model-tiers.json
        tiers = {
            "tiers": {
                "0": {"model": "Claude Haiku 3.5 (cheap)", "description": "cheap"},
                "1": {"model": "Claude Sonnet 4", "description": "mid"},
                "2": {"model": "Claude Sonnet 4 (expensive)", "description": "expensive"},
                "3": {"model": "Claude Opus 4", "description": "top"},
            }
        }
        tiers_file = Path(self.tmpdir.name) / "model-tiers.json"
        tiers_file.write_text(json.dumps(tiers))

        # Monkeypatch __file__ so script_dir.parent resolves to tmpdir
        self._orig_file = SCRIPT
        mod.__file__ = str(self.scripts_dir / "apply_model_tiers.py")

    def tearDown(self):
        mod.__file__ = str(self._orig_file)
        self.tmpdir.cleanup()

    def _write_agent(self, name, tier, has_existing_model=False):
        extra = 'model: "old-model"\n' if has_existing_model else ""
        content = (
            f"---\n"
            f"description: test agent\n"
            f"{extra}"
            f"---\n\n"
            f"<!-- tier: {tier} -->\n\n"
            f"# {name}\n"
        )
        (self.agents_dir / f"{name}.agent.md").write_text(content)

    def test_patches_tier_to_model(self):
        self._write_agent("my-agent", tier=1)
        mod.main()
        result = (self.agents_dir / "my-agent.agent.md").read_text()
        self.assertIn('model: "Claude Sonnet 4"', result)

    def test_replaces_existing_model(self):
        self._write_agent("existing-agent", tier=0, has_existing_model=True)
        mod.main()
        result = (self.agents_dir / "existing-agent.agent.md").read_text()
        self.assertIn('model: "Claude Haiku 3.5 (cheap)"', result)
        self.assertNotIn("old-model", result)

    def test_skips_agent_without_tier_comment(self):
        content = "---\nname: no-tier\n---\n# No tier here\n"
        agent_file = self.agents_dir / "no-tier.agent.md"
        agent_file.write_text(content)
        mod.main()
        # File should be unchanged
        self.assertEqual(agent_file.read_text(), content)

    def test_handles_multiple_agents(self):
        self._write_agent("agent-a", tier=0)
        self._write_agent("agent-b", tier=2)
        self._write_agent("agent-c", tier=3)
        mod.main()
        self.assertIn("Claude Haiku 3.5 (cheap)", (self.agents_dir / "agent-a.agent.md").read_text())
        self.assertIn("Claude Sonnet 4 (expensive)", (self.agents_dir / "agent-b.agent.md").read_text())
        self.assertIn("Claude Opus 4", (self.agents_dir / "agent-c.agent.md").read_text())


if __name__ == "__main__":
    unittest.main()
