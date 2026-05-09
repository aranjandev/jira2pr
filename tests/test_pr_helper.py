"""Tests for pr_helper.py — platform detection, arg parsing, validation, HTTP layer."""
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import urllib.error

SCRIPT = Path(__file__).parent.parent / "canonical/skills/create-pull-request/scripts/pr_helper.py"


def _load():
    spec = importlib.util.spec_from_file_location("pr_helper", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


# ─── Platform & repo detection ───────────────────────────────────────────────

class TestDetectPlatform(unittest.TestCase):

    def _with_remote(self, url):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=url, stderr="")
            return mod.detect_platform()

    def test_github_https(self):
        self.assertEqual(self._with_remote("https://github.com/org/repo.git"), "github")

    def test_github_ssh(self):
        self.assertEqual(self._with_remote("git@github.com:org/repo.git"), "github")

    def test_bitbucket_https(self):
        self.assertEqual(self._with_remote("https://bitbucket.org/org/repo.git"), "bitbucket")

    def test_bitbucket_ssh(self):
        self.assertEqual(self._with_remote("git@bitbucket.org:org/repo.git"), "bitbucket")

    def test_unknown_host_exits(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="https://gitlab.com/org/repo.git", stderr="")
            with self.assertRaises(SystemExit) as ctx:
                mod.detect_platform()
            self.assertEqual(ctx.exception.code, 1)


class TestExtractOwnerRepo(unittest.TestCase):

    def _with_remote(self, url):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=url, stderr="")
            return mod.extract_owner_repo()

    def test_github_https_with_dot_git(self):
        self.assertEqual(self._with_remote("https://github.com/myorg/myrepo.git"), "myorg/myrepo")

    def test_github_https_without_dot_git(self):
        self.assertEqual(self._with_remote("https://github.com/myorg/myrepo"), "myorg/myrepo")

    def test_github_ssh(self):
        self.assertEqual(self._with_remote("git@github.com:myorg/myrepo.git"), "myorg/myrepo")

    def test_bitbucket_https(self):
        self.assertEqual(self._with_remote("https://bitbucket.org/myorg/myrepo.git"), "myorg/myrepo")

    def test_bitbucket_ssh(self):
        self.assertEqual(self._with_remote("git@bitbucket.org:myorg/myrepo.git"), "myorg/myrepo")

    def test_invalid_url_exits(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="not-a-url", stderr="")
            with self.assertRaises(SystemExit) as ctx:
                mod.extract_owner_repo()
            self.assertEqual(ctx.exception.code, 1)


# ─── Argument parsing ─────────────────────────────────────────────────────────

class TestParseArgs(unittest.TestCase):

    def _parse(self, argv):
        with patch.object(sys, "argv", ["pr_helper.py"] + argv):
            return mod.parse_args()

    # create command
    def test_create_basic(self):
        opts = self._parse(["create", "--title", "My PR", "--body", "Some body"])
        self.assertEqual(opts["command"], "create")
        self.assertEqual(opts["title"], "My PR")
        self.assertEqual(opts["body"], "Some body")
        self.assertFalse(opts["draft"])

    def test_create_with_draft_flag(self):
        opts = self._parse(["create", "--title", "T", "--body", "B", "--draft"])
        self.assertTrue(opts["draft"])

    def test_create_with_labels(self):
        opts = self._parse(["create", "--title", "T", "--body", "B", "--labels", "bug,feature"])
        self.assertEqual(opts["labels"], "bug,feature")

    def test_create_with_base_branch(self):
        opts = self._parse(["create", "--title", "T", "--body", "B", "--base", "develop"])
        self.assertEqual(opts["base"], "develop")

    def test_create_with_body_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Title\n\nContent with **markdown** and `code`.\n")
            tmpfile = f.name
        try:
            opts = self._parse(["create", "--title", "T", "--body-file", tmpfile])
            self.assertIn("Title", opts["body"])
            self.assertIn("markdown", opts["body"])
        finally:
            Path(tmpfile).unlink()

    def test_body_file_reads_special_characters(self):
        """Files with <!--, >, backticks, ! must be read correctly."""
        content = "<!-- PR_BLOCK:STATUS:BEGIN -->\n| Phase | `Planning` |\n<!-- PR_BLOCK:STATUS:END -->\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            tmpfile = f.name
        try:
            opts = self._parse(["create", "--title", "T", "--body-file", tmpfile])
            self.assertEqual(opts["body"], content)
        finally:
            Path(tmpfile).unlink()

    def test_body_file_not_found_exits(self):
        with patch.object(sys, "argv", ["pr_helper.py", "create", "--title", "T",
                                         "--body-file", "/nonexistent/path/pr_body.md"]):
            with self.assertRaises(SystemExit) as ctx:
                mod.parse_args()
            self.assertEqual(ctx.exception.code, 1)

    # update command
    def test_update_basic(self):
        opts = self._parse(["update", "--pr-number", "42", "--body", "Updated body"])
        self.assertEqual(opts["command"], "update")
        self.assertEqual(opts["pr_number"], "42")
        self.assertEqual(opts["body"], "Updated body")

    def test_update_with_undraft(self):
        opts = self._parse(["update", "--pr-number", "42", "--undraft"])
        self.assertTrue(opts["undraft"])
        self.assertEqual(opts["pr_number"], "42")

    def test_update_with_title(self):
        opts = self._parse(["update", "--pr-number", "42", "--title", "New Title", "--body", "B"])
        self.assertEqual(opts["title"], "New Title")

    # fetch-body command
    def test_fetch_body(self):
        opts = self._parse(["fetch-body", "--pr-number", "7"])
        self.assertEqual(opts["command"], "fetch-body")
        self.assertEqual(opts["pr_number"], "7")

    # flags
    def test_dry_run_flag(self):
        opts = self._parse(["create", "--title", "T", "--body", "B", "--dry-run"])
        self.assertTrue(opts["dry_run"])

    # error cases
    def test_unknown_command_exits_1(self):
        with patch.object(sys, "argv", ["pr_helper.py", "badcmd"]):
            with self.assertRaises(SystemExit) as ctx:
                mod.parse_args()
            self.assertEqual(ctx.exception.code, 1)

    def test_unknown_option_exits_1(self):
        with patch.object(sys, "argv", ["pr_helper.py", "create", "--unknown-flag"]):
            with self.assertRaises(SystemExit) as ctx:
                mod.parse_args()
            self.assertEqual(ctx.exception.code, 1)

    def test_no_args_prints_usage_and_exits_0(self):
        with patch.object(sys, "argv", ["pr_helper.py"]):
            with self.assertRaises(SystemExit) as ctx:
                mod.parse_args()
            self.assertEqual(ctx.exception.code, 0)

    def test_help_flag_exits_0(self):
        with patch.object(sys, "argv", ["pr_helper.py", "--help"]):
            with self.assertRaises(SystemExit) as ctx:
                mod.parse_args()
            self.assertEqual(ctx.exception.code, 0)


# ─── Validation ───────────────────────────────────────────────────────────────

class TestValidate(unittest.TestCase):

    def _opts(self, **overrides):
        base = {
            "command": "create",
            "title": "",
            "body": "",
            "base": "",
            "labels": "",
            "draft": False,
            "undraft": False,
            "pr_number": "",
            "dry_run": False,
        }
        base.update(overrides)
        return base

    # create
    def test_create_valid(self):
        mod.validate(self._opts(title="T", body="B"))  # no exception

    def test_create_missing_title_exits(self):
        with self.assertRaises(SystemExit):
            mod.validate(self._opts(title="", body="B"))

    def test_create_missing_body_exits(self):
        with self.assertRaises(SystemExit):
            mod.validate(self._opts(title="T", body=""))

    # update
    def test_update_valid_with_body(self):
        mod.validate(self._opts(command="update", pr_number="42", body="B"))

    def test_update_valid_with_title_only(self):
        mod.validate(self._opts(command="update", pr_number="42", title="New Title"))

    def test_update_valid_with_undraft_only(self):
        mod.validate(self._opts(command="update", pr_number="42", undraft=True))

    def test_update_missing_pr_number_exits(self):
        with self.assertRaises(SystemExit):
            mod.validate(self._opts(command="update", pr_number="", body="B"))

    def test_update_missing_body_and_no_undraft_exits(self):
        with self.assertRaises(SystemExit):
            mod.validate(self._opts(command="update", pr_number="42", body="", title="", undraft=False))

    # fetch-body
    def test_fetch_body_valid(self):
        mod.validate(self._opts(command="fetch-body", pr_number="42"))

    def test_fetch_body_missing_pr_number_exits(self):
        with self.assertRaises(SystemExit):
            mod.validate(self._opts(command="fetch-body", pr_number=""))


# ─── Headers ──────────────────────────────────────────────────────────────────

class TestGithubHeaders(unittest.TestCase):

    def test_authorization_uses_token_scheme(self):
        headers = mod.github_headers("my-secret-token")
        self.assertEqual(headers["Authorization"], "token my-secret-token")

    def test_accept_header_is_v3(self):
        headers = mod.github_headers("tok")
        self.assertIn("application/vnd.github.v3+json", headers["Accept"])

    def test_content_type_is_json(self):
        headers = mod.github_headers("tok")
        self.assertEqual(headers["Content-Type"], "application/json")


# ─── HTTP request helper ─────────────────────────────────────────────────────

class TestHttpRequest(unittest.TestCase):

    def _make_response(self, status, body_dict):
        resp = MagicMock()
        resp.status = status
        resp.read.return_value = json.dumps(body_dict).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    def test_successful_get_returns_parsed_json(self):
        fake = self._make_response(200, {"number": 42, "html_url": "https://github.com/org/repo/pull/42"})
        with patch("urllib.request.urlopen", return_value=fake):
            status, body = mod.http_request("GET", "https://api.github.com/repos/org/repo/pulls/42", {})
        self.assertEqual(status, 200)
        self.assertEqual(body["number"], 42)

    def test_successful_post_returns_201(self):
        fake = self._make_response(201, {"number": 1, "html_url": "https://github.com/org/repo/pull/1"})
        with patch("urllib.request.urlopen", return_value=fake):
            status, body = mod.http_request(
                "POST",
                "https://api.github.com/repos/org/repo/pulls",
                {"Content-Type": "application/json"},
                {"title": "Test PR", "body": "body", "head": "feat/branch", "draft": True},
            )
        self.assertEqual(status, 201)
        self.assertEqual(body["number"], 1)

    def test_http_error_returns_parsed_json_body(self):
        err = urllib.error.HTTPError(
            url="https://api.github.com",
            code=422,
            msg="Unprocessable Entity",
            hdrs=None,
            fp=io.BytesIO(json.dumps({"message": "Validation Failed"}).encode()),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            status, body = mod.http_request("POST", "https://api.github.com/test", {}, {})
        self.assertEqual(status, 422)
        self.assertEqual(body.get("message"), "Validation Failed")

    def test_http_error_non_json_returns_raw_key(self):
        err = urllib.error.HTTPError(
            url="https://api.github.com",
            code=500,
            msg="Server Error",
            hdrs=None,
            fp=io.BytesIO(b"Internal Server Error"),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            status, body = mod.http_request("GET", "https://api.github.com/test", {})
        self.assertEqual(status, 500)
        self.assertIn("_raw", body)
        self.assertEqual(body["_raw"], "Internal Server Error")

    def test_no_payload_sends_no_body(self):
        captured_request = []

        def fake_urlopen(req, **kwargs):
            captured_request.append(req)
            resp = MagicMock()
            resp.status = 200
            resp.read.return_value = b"{}"
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            mod.http_request("GET", "https://api.github.com/repos/org/repo/pulls/1", {})

        self.assertEqual(len(captured_request), 1)
        self.assertIsNone(captured_request[0].data)


# ─── GitHub-specific operations ───────────────────────────────────────────────

class TestCreateGithubPr(unittest.TestCase):

    def _run(self, status, resp_body, **kwargs):
        fake = MagicMock()
        fake.status = status
        fake.read.return_value = json.dumps(resp_body).encode()
        fake.__enter__ = lambda s: s
        fake.__exit__ = MagicMock(return_value=False)

        captured = io.StringIO()
        with patch("urllib.request.urlopen", return_value=fake), \
             patch("sys.stdout", captured):
            mod.create_github_pr(
                owner_repo="org/repo",
                token="tok",
                title=kwargs.get("title", "Test PR"),
                body=kwargs.get("body", "PR body"),
                base=kwargs.get("base", ""),
                draft=kwargs.get("draft", False),
                labels=kwargs.get("labels", ""),
                branch="feat/test",
            )
        return captured.getvalue()

    def test_outputs_pr_url_and_number(self):
        output = self._run(
            201,
            {"html_url": "https://github.com/org/repo/pull/5", "number": 5},
        )
        self.assertIn("PR_URL=https://github.com/org/repo/pull/5", output)
        self.assertIn("PR_NUMBER=5", output)

    def test_api_error_exits(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            resp = MagicMock()
            resp.status = 422
            resp.read.return_value = json.dumps({"message": "Validation Failed"}).encode()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = resp  # status=422 triggers failure condition

            # http_request returns (status, body) and create_github_pr checks status != 201
            with self.assertRaises(SystemExit) as ctx:
                mod.create_github_pr("org/repo", "tok", "T", "B", "", False, "", "feat/x")
            self.assertEqual(ctx.exception.code, 1)


class TestFetchGithubPrBody(unittest.TestCase):

    def test_prints_pr_body(self):
        resp_body = {"body": "# My PR\n\nSome content here.", "number": 10}
        fake = MagicMock()
        fake.status = 200
        fake.read.return_value = json.dumps(resp_body).encode()
        fake.__enter__ = lambda s: s
        fake.__exit__ = MagicMock(return_value=False)

        captured = io.StringIO()
        with patch("urllib.request.urlopen", return_value=fake), \
             patch("sys.stdout", captured):
            mod.fetch_github_pr_body("org/repo", "tok", "10")

        self.assertIn("# My PR", captured.getvalue())
        self.assertIn("Some content here.", captured.getvalue())

    def test_empty_body_prints_empty(self):
        resp_body = {"body": None, "number": 11}
        fake = MagicMock()
        fake.status = 200
        fake.read.return_value = json.dumps(resp_body).encode()
        fake.__enter__ = lambda s: s
        fake.__exit__ = MagicMock(return_value=False)

        captured = io.StringIO()
        with patch("urllib.request.urlopen", return_value=fake), \
             patch("sys.stdout", captured):
            mod.fetch_github_pr_body("org/repo", "tok", "11")

        self.assertEqual(captured.getvalue().strip(), "")


class TestUndraftGithubPr(unittest.TestCase):

    def _make_responses(self, get_body, gql_body):
        """Return two fake responses: first for GET (node_id), second for GraphQL."""
        responses = []

        def make_resp(status, body_dict):
            resp = MagicMock()
            resp.status = status
            resp.read.return_value = json.dumps(body_dict).encode()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            return resp

        responses.append(make_resp(200, get_body))
        responses.append(make_resp(200, gql_body))
        return iter(responses)

    def test_successful_undraft_prints_ok(self):
        get_resp = {"node_id": "PR_kwABCDEF", "number": 42}
        gql_resp = {
            "data": {
                "markPullRequestReadyForReview": {
                    "pullRequest": {"isDraft": False}
                }
            }
        }
        resp_iter = self._make_responses(get_resp, gql_resp)

        captured = io.StringIO()
        with patch("urllib.request.urlopen", side_effect=lambda req, **kw: next(resp_iter)), \
             patch("sys.stdout", captured):
            mod.undraft_github_pr("org/repo", "tok", "42")

        self.assertIn("ready for review", captured.getvalue())

    def test_missing_node_id_exits(self):
        get_resp = {"number": 42}  # no node_id
        fake = MagicMock()
        fake.status = 200
        fake.read.return_value = json.dumps(get_resp).encode()
        fake.__enter__ = lambda s: s
        fake.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=fake):
            with self.assertRaises(SystemExit) as ctx:
                mod.undraft_github_pr("org/repo", "tok", "42")
            self.assertEqual(ctx.exception.code, 1)


# ─── Token auth ───────────────────────────────────────────────────────────────

class TestGetAuthToken(unittest.TestCase):

    def test_github_token_from_env(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_test123"}):
            token = mod.get_auth_token("github")
        self.assertEqual(token, "ghp_test123")

    def test_github_missing_token_exits(self):
        env = {k: v for k, v in __import__("os").environ.items() if k != "GITHUB_TOKEN"}
        with patch.dict("os.environ", env, clear=True):
            with self.assertRaises(SystemExit) as ctx:
                mod.get_auth_token("github")
            self.assertEqual(ctx.exception.code, 1)

    def test_bitbucket_token_from_env(self):
        with patch.dict("os.environ", {"BITBUCKET_TOKEN": "bb_test456"}):
            token = mod.get_auth_token("bitbucket")
        self.assertEqual(token, "bb_test456")


if __name__ == "__main__":
    unittest.main()
