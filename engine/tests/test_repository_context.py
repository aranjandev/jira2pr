"""Tests for repository map generation (runtime.workflow.repository_context)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from runtime.workflow.repository_context import (
    RepositoryContextRequest,
    TreeSitterRepositoryContextProvider,
    _is_mapped_path,
)


def _git_repo(root: Path, files: dict[str, str]) -> Path:
    """Create a git repo at root tracking the given relative files."""

    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)

    for relative, content in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    return root


def _generate(root: Path, **kwargs) -> str:
    provider = TreeSitterRepositoryContextProvider(**kwargs)
    return provider.generate(
        RepositoryContextRequest(repo_root=root)
    ).content


@pytest.mark.parametrize(
    ("path", "mapped"),
    [
        ("src/app.py", True),
        (".env.example", True),
        (".github/agents/coder.agent.md", True),
        (".vscode/settings.json", False),
        ("src/.cache/data.json", False),
    ],
)
def test_is_mapped_path_hides_dot_folders_except_github(path, mapped):
    assert _is_mapped_path(Path(path)) is mapped


def test_hidden_folders_excluded_from_inventory_but_github_kept(tmp_path):
    root = _git_repo(
        tmp_path / "repo",
        {
            "README.md": "# hi\n",
            ".env.example": "KEY=value\n",
            ".vscode/settings.json": '{"editor.tabSize": 2}\n',
            ".github/model-tiers.json": '{"tier0": "fast"}\n',
        },
    )

    content = _generate(root)

    assert "README.md" in content
    assert ".env.example" in content
    assert ".github/model-tiers.json" in content
    assert ".vscode/settings.json" not in content
    assert "tracked_files: 3" in content
    # Files stay on disk and in git; only the map is affected.
    assert (root / ".vscode/settings.json").exists()


def test_yaml_json_and_toml_top_level_keys_are_summarized(tmp_path):
    root = _git_repo(
        tmp_path / "repo",
        {
            "config/app.yaml": "server:\n  port: 8080\ndatabase:\n  url: x\n",
            "config/multi.yml": "first: 1\n---\nsecond: 2\n",
            "package.json": '{"name": "demo", "scripts": {}}',
            "pyproject.toml": '[project]\nname = "demo"\n',
        },
    )

    content = _generate(root)

    assert "## Config Structure" in content
    assert "### config/app.yaml\nkeys: server, database" in content
    assert "### config/multi.yml\nkeys: first" in content
    assert "### package.json\nkeys: name, scripts" in content
    assert "### pyproject.toml\nkeys: project" in content


def test_malformed_config_file_is_listed_without_summary(tmp_path):
    root = _git_repo(
        tmp_path / "repo",
        {
            "broken.yaml": "key: [unclosed\n",
            "broken.json": "{not json",
            "ok.json": '{"ok": true}',
        },
    )

    content = _generate(root)

    assert "broken.yaml" in content
    assert "broken.json" in content
    assert "### broken.json" not in content
    assert "### ok.json\nkeys: ok" in content


def test_python_docstrings_signatures_and_constants_via_ast(tmp_path):
    source = (
        '"""Module summary line.\n\nMore detail.\n"""\n'
        "MAX_RETRIES = 3\n"
        "_private = 1\n\n"
        "class Worker:\n"
        '    """Runs jobs."""\n\n'
        "    def run(self, job: str, *, retries: int = 1) -> bool:\n"
        '        """Execute one job.\n\n        Long details.\n        """\n'
        "        return True\n\n\n"
        "def helper(x):\n"
        "    def nested():\n"
        "        pass\n"
        "    return x\n"
    )
    root = _git_repo(tmp_path / "repo", {"worker.py": source})

    content = _generate(root)

    assert "docstring: Module summary line." in content
    assert "constants:\n  - MAX_RETRIES" in content
    assert "_private" not in content
    assert "  - Worker: Runs jobs." in content
    assert (
        "  - run(self, job: str, *, retries: int=1) -> bool: "
        "Execute one job."
    ) in content
    assert "  - helper(x): " not in content  # no docstring, no suffix
    assert "  - helper(x)" in content
    assert "nested" not in content


def test_python_syntax_error_falls_back_to_tree_sitter_names(tmp_path):
    root = _git_repo(
        tmp_path / "repo",
        {"legacy.py": "def still_found(:\n    pass\n\nclass Kept:\n    pass\n"},
    )

    content = _generate(root)

    assert "### legacy.py" in content
    assert "  - Kept" in content


def test_structure_budget_omits_extra_blocks(tmp_path):
    files = {
        f"mod{i}.py": f'"""{"x" * 100} {i}"""\ndef f{i}(): pass\n'
        for i in range(20)
    }
    root = _git_repo(tmp_path / "repo", files)

    content = _generate(root, max_structure_chars=600)

    assert content.count("### mod") < 20
    assert "omitted to stay within the 600 character structure budget" in content
    # The inventory is never truncated by the budget.
    assert content.count("mod") >= 20
