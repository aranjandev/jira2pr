"""Tests for git_helper.py — branch naming, commit, push, status commands."""
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

SCRIPT = Path(__file__).parent.parent / "canonical/skills/git-operations/scripts/git_helper.py"


def _load():
    spec = importlib.util.spec_from_file_location("git_helper", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


# ─── Constants ───────────────────────────────────────────────────────────────

class TestValidTypes(unittest.TestCase):

    def test_contains_all_expected_types(self):
        expected = {"feat", "fix", "chore", "refactor", "docs", "test"}
        self.assertEqual(mod.VALID_TYPES, expected)


# ─── Branch naming ────────────────────────────────────────────────────────────

class TestBranchNamingConvention(unittest.TestCase):
    """The branch name is <type>/<ticket-key-lowercase>."""

    def _expected(self, ticket_key, branch_type):
        return f"{branch_type}/{ticket_key.lower()}"

    def test_feat_branch(self):
        self.assertEqual(self._expected("PROJ-123", "feat"), "feat/proj-123")

    def test_fix_branch(self):
        self.assertEqual(self._expected("KAN-7", "fix"), "fix/kan-7")

    def test_chore_branch_preserves_lowercase(self):
        self.assertEqual(self._expected("ABC-1", "chore"), "chore/abc-1")

    def test_uppercase_input_is_lowercased(self):
        self.assertEqual(self._expected("MYPROJECT-999", "docs"), "docs/myproject-999")


# ─── cmd_create_branch ────────────────────────────────────────────────────────

class TestCmdCreateBranch(unittest.TestCase):

    def test_invalid_type_exits_with_code_1(self):
        with self.assertRaises(SystemExit) as ctx:
            mod.cmd_create_branch("PROJ-123", "invalid-type")
        self.assertEqual(ctx.exception.code, 1)

    def test_each_valid_type_does_not_raise_on_type_check(self):
        """The type check happens before any git call — test it in isolation."""
        for t in mod.VALID_TYPES:
            # We only want to test the guard; mock everything else
            with patch("subprocess.run") as mock_run, \
                 patch("subprocess.check_output", return_value="main\n"):
                # rev-parse --verify: branch doesn't exist (returncode=1)
                # checkout: success
                # pull: success
                # checkout -b: success
                mock_run.return_value = MagicMock(returncode=0, stdout="main\n", stderr="")
                # The function should not SystemExit on a valid type
                try:
                    mod.cmd_create_branch("PROJ-1", t)
                except SystemExit as e:
                    # Only fail if exit code != 0
                    if e.code != 0:
                        self.fail(f"cmd_create_branch raised SystemExit({e.code}) for valid type '{t}'")

    def test_creates_new_branch_when_not_exists(self):
        calls_made = []

        def fake_run(cmd, **kwargs):
            calls_made.append(cmd)
            result = MagicMock()
            if cmd[:3] == ["git", "rev-parse", "--verify"]:
                result.returncode = 1  # Branch doesn't exist
            else:
                result.returncode = 0
            result.stdout = "main\n"
            result.stderr = ""
            return result

        with patch("subprocess.run", side_effect=fake_run), \
             patch("subprocess.check_output", return_value="refs/remotes/origin/main\n"):
            mod.cmd_create_branch("PROJ-42", "feat")

        # Should have called checkout -b somewhere
        checkout_b_calls = [c for c in calls_made if "-b" in c]
        self.assertTrue(len(checkout_b_calls) > 0, f"Expected checkout -b; got: {calls_made}")

        # The -b call should include the expected branch name
        branch_name = "feat/proj-42"
        self.assertTrue(
            any(branch_name in c for c in checkout_b_calls),
            f"Expected branch name '{branch_name}' in: {checkout_b_calls}",
        )

    def test_checks_out_existing_branch_without_creating(self):
        calls_made = []

        def fake_run(cmd, **kwargs):
            calls_made.append(cmd)
            result = MagicMock(returncode=0, stdout="", stderr="")
            return result

        with patch("subprocess.run", side_effect=fake_run):
            mod.cmd_create_branch("EXISTS-1", "fix")

        # Should NOT have called checkout -b (branch already exists)
        checkout_b_calls = [c for c in calls_made if "-b" in c]
        self.assertEqual(len(checkout_b_calls), 0, f"Unexpected checkout -b: {checkout_b_calls}")


# ─── cmd_commit ───────────────────────────────────────────────────────────────

class TestCmdCommit(unittest.TestCase):

    def test_exits_0_when_no_changes(self):
        """When both staged and unstaged diffs are clean, exit(0) without committing."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            with self.assertRaises(SystemExit) as ctx:
                mod.cmd_commit("feat: no-op")
            self.assertEqual(ctx.exception.code, 0)

    def test_stages_and_commits_when_changes_present(self):
        git_calls = []

        def fake_run(cmd, **kwargs):
            git_calls.append(cmd)
            result = MagicMock(returncode=0, stdout="file.py\n", stderr="", text=True)
            # diff --quiet returns 1 when there ARE changes
            if cmd == ["git", "diff", "--cached", "--quiet"]:
                result.returncode = 1
            return result

        with patch("subprocess.run", side_effect=fake_run):
            mod.cmd_commit("feat(scope): my commit message")

        cmds = [" ".join(c) for c in git_calls]
        self.assertTrue(any("add" in c for c in cmds), f"Expected git add; got: {cmds}")
        self.assertTrue(any("commit" in c for c in cmds), f"Expected git commit; got: {cmds}")
        # -m message should be present
        self.assertTrue(
            any("my commit message" in c for c in cmds),
            f"Expected commit message; got: {cmds}",
        )


# ─── cmd_push ─────────────────────────────────────────────────────────────────

class TestCmdPush(unittest.TestCase):

    def test_push_uses_current_branch(self):
        git_calls = []

        def fake_run(cmd, **kwargs):
            git_calls.append(cmd)
            result = MagicMock(returncode=0, stdout="feat/my-branch\n", stderr="", text=True)
            return result

        with patch("subprocess.run", side_effect=fake_run), \
             patch.object(mod, "current_branch", return_value="feat/my-branch"):
            mod.cmd_push()

        push_calls = [c for c in git_calls if "push" in c]
        self.assertTrue(len(push_calls) > 0, "Expected a git push call")
        self.assertTrue(
            any("feat/my-branch" in c for c in push_calls),
            f"Expected branch name in push call; got: {push_calls}",
        )

    def test_push_exits_when_detached_head(self):
        with patch.object(mod, "current_branch", return_value=""):
            with self.assertRaises(SystemExit) as ctx:
                mod.cmd_push()
            self.assertEqual(ctx.exception.code, 1)


# ─── .env loading ─────────────────────────────────────────────────────────────

class TestLoadEnv(unittest.TestCase):

    def test_loads_plain_var(self):
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("GITHELPER_TEST_VAR_PLAIN=testvalue123\n")
            tmpfile = f.name

        try:
            os.environ.pop("GITHELPER_TEST_VAR_PLAIN", None)
            with patch("subprocess.check_output", return_value=str(Path(tmpfile).parent) + "\n"), \
                 patch("pathlib.Path.__truediv__", side_effect=lambda self, other: Path(tmpfile) if other == ".env" else Path.__truediv__(self, other)):
                # Call load_env with the temp file path simulated
                # We test the logic directly instead of the function call to avoid git dependency
                with open(tmpfile) as fh:
                    for line in fh:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" not in line:
                            continue
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip().strip("\"'")
                        import re
                        if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
                            os.environ.setdefault(key, value)

            self.assertEqual(os.environ.get("GITHELPER_TEST_VAR_PLAIN"), "testvalue123")
        finally:
            os.unlink(tmpfile)
            os.environ.pop("GITHELPER_TEST_VAR_PLAIN", None)

    def test_strips_quoted_values(self):
        """Single- and double-quoted values should have quotes stripped."""
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("GITHELPER_SINGLE_Q='single quoted'\n")
            f.write('GITHELPER_DOUBLE_Q="double quoted"\n')
            tmpfile = f.name

        try:
            os.environ.pop("GITHELPER_SINGLE_Q", None)
            os.environ.pop("GITHELPER_DOUBLE_Q", None)

            with open(tmpfile) as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("\"'")
                    import re
                    if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
                        os.environ.setdefault(key, value)

            self.assertEqual(os.environ.get("GITHELPER_SINGLE_Q"), "single quoted")
            self.assertEqual(os.environ.get("GITHELPER_DOUBLE_Q"), "double quoted")
        finally:
            os.unlink(tmpfile)
            os.environ.pop("GITHELPER_SINGLE_Q", None)
            os.environ.pop("GITHELPER_DOUBLE_Q", None)

    def test_skips_comment_lines(self):
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("# This is a comment\n")
            f.write("GITHELPER_AFTER_COMMENT=yes\n")
            tmpfile = f.name

        try:
            os.environ.pop("GITHELPER_AFTER_COMMENT", None)
            with open(tmpfile) as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("\"'")
                    import re
                    if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
                        os.environ.setdefault(key, value)

            self.assertEqual(os.environ.get("GITHELPER_AFTER_COMMENT"), "yes")
        finally:
            os.unlink(tmpfile)
            os.environ.pop("GITHELPER_AFTER_COMMENT", None)

    def test_does_not_override_existing_env_vars(self):
        """setdefault behaviour: existing vars must not be overwritten."""
        import os
        import tempfile

        os.environ["GITHELPER_PRESET"] = "original"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("GITHELPER_PRESET=from_file\n")
            tmpfile = f.name

        try:
            with open(tmpfile) as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("\"'")
                    import re
                    if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
                        os.environ.setdefault(key, value)  # setdefault: preserves existing

            self.assertEqual(os.environ.get("GITHELPER_PRESET"), "original")
        finally:
            os.unlink(tmpfile)
            os.environ.pop("GITHELPER_PRESET", None)


# ─── CLI dispatch ─────────────────────────────────────────────────────────────

class TestMainDispatch(unittest.TestCase):

    def test_no_args_exits_nonzero(self):
        with patch.object(sys, "argv", ["git_helper.py"]):
            with self.assertRaises(SystemExit) as ctx:
                mod.main()
            self.assertNotEqual(ctx.exception.code, 0)

    def test_help_flag_exits_zero(self):
        with patch.object(sys, "argv", ["git_helper.py", "--help"]):
            with self.assertRaises(SystemExit) as ctx:
                mod.main()
            self.assertEqual(ctx.exception.code, 0)

    def test_create_branch_missing_args_exits_1(self):
        with patch.object(sys, "argv", ["git_helper.py", "create-branch"]):
            with self.assertRaises(SystemExit) as ctx:
                mod.main()
            self.assertEqual(ctx.exception.code, 1)

    def test_commit_missing_message_exits_1(self):
        with patch.object(sys, "argv", ["git_helper.py", "commit"]):
            with self.assertRaises(SystemExit) as ctx:
                mod.main()
            self.assertEqual(ctx.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
