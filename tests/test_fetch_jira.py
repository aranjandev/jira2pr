"""Tests for fetch_jira.py — ADF parsing, ticket key validation, HTTP layer."""
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import urllib.error

SCRIPT = Path(__file__).parent.parent / "canonical/skills/read-jira-ticket/scripts/fetch_jira.py"


def _load():
    spec = importlib.util.spec_from_file_location("fetch_jira", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


# ─── ADF node parsing ────────────────────────────────────────────────────────

class TestParseAdfNode(unittest.TestCase):

    def test_paragraph_extracts_text(self):
        node = {"type": "paragraph", "content": [{"type": "text", "text": "Hello world"}]}
        self.assertEqual(mod.parse_adf_node(node), "Hello world")

    def test_paragraph_concatenates_multiple_text_nodes(self):
        node = {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "Part 1 "},
                {"type": "text", "text": "Part 2"},
            ],
        }
        self.assertEqual(mod.parse_adf_node(node), "Part 1 Part 2")

    def test_heading_adds_markdown_prefix(self):
        node = {"type": "heading", "content": [{"type": "text", "text": "My Section"}]}
        self.assertEqual(mod.parse_adf_node(node), "\n## My Section")

    def test_bullet_list_one_item(self):
        node = {
            "type": "bulletList",
            "content": [
                {
                    "type": "listItem",
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "Item A"}]}
                    ],
                }
            ],
        }
        self.assertEqual(mod.parse_adf_node(node), "- Item A")

    def test_bullet_list_multiple_items(self):
        node = {
            "type": "bulletList",
            "content": [
                {
                    "type": "listItem",
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Alpha"}]}],
                },
                {
                    "type": "listItem",
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Beta"}]}],
                },
            ],
        }
        result = mod.parse_adf_node(node)
        self.assertIn("- Alpha", result)
        self.assertIn("- Beta", result)

    def test_ordered_list_numbered(self):
        node = {
            "type": "orderedList",
            "content": [
                {
                    "type": "listItem",
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Step one"}]}],
                },
                {
                    "type": "listItem",
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Step two"}]}],
                },
            ],
        }
        result = mod.parse_adf_node(node)
        self.assertIn("1. Step one", result)
        self.assertIn("2. Step two", result)

    def test_code_block_wrapped_in_backticks(self):
        node = {
            "type": "codeBlock",
            "content": [{"type": "text", "text": "print('hello')"}],
        }
        result = mod.parse_adf_node(node)
        self.assertIn("```", result)
        self.assertIn("print('hello')", result)

    def test_unknown_node_type_falls_back_to_text(self):
        node = {"type": "someNewType", "content": [{"type": "text", "text": "fallback"}]}
        self.assertEqual(mod.parse_adf_node(node), "fallback")

    def test_non_dict_returns_empty(self):
        self.assertEqual(mod.parse_adf_node("not a dict"), "")
        self.assertEqual(mod.parse_adf_node(None), "")
        self.assertEqual(mod.parse_adf_node(42), "")

    def test_empty_dict_returns_empty(self):
        self.assertEqual(mod.parse_adf_node({}), "")


# ─── Full description parsing ─────────────────────────────────────────────────

class TestParseAdfDescription(unittest.TestCase):

    def test_combines_multiple_blocks(self):
        description = {
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Intro."}]},
                {"type": "heading", "content": [{"type": "text", "text": "Details"}]},
                {"type": "paragraph", "content": [{"type": "text", "text": "More info."}]},
            ]
        }
        result = mod.parse_adf_description(description)
        self.assertIn("Intro.", result)
        self.assertIn("## Details", result)
        self.assertIn("More info.", result)

    def test_none_input_returns_empty(self):
        self.assertEqual(mod.parse_adf_description(None), "")

    def test_empty_dict_returns_empty(self):
        self.assertEqual(mod.parse_adf_description({}), "")

    def test_non_dict_returns_empty(self):
        self.assertEqual(mod.parse_adf_description("string"), "")

    def test_empty_content_array(self):
        self.assertEqual(mod.parse_adf_description({"content": []}), "")

    def test_filters_blank_blocks(self):
        # A block that produces empty string should not add blank lines
        description = {
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Real content"}]},
                {"type": "paragraph", "content": []},  # Empty paragraph
            ]
        }
        result = mod.parse_adf_description(description)
        # Should not end with dangling newline from empty block
        self.assertIn("Real content", result)


# ─── Acceptance criteria extraction ──────────────────────────────────────────

class TestExtractAcceptanceCriteria(unittest.TestCase):

    def test_custom_field_string(self):
        fields = {"customfield_10035": "- Must log in\n- Must see dashboard"}
        result = mod.extract_acceptance_criteria(fields)
        self.assertIn("Must log in", result)

    def test_custom_field_missing_returns_empty_or_description_based(self):
        fields = {"summary": "Some ticket"}
        result = mod.extract_acceptance_criteria(fields)
        self.assertEqual(result, "")

    def test_criteria_from_heading_in_description(self):
        fields = {
            "description": {
                "content": [
                    {
                        "type": "heading",
                        "content": [{"type": "text", "text": "Acceptance Criteria"}],
                    },
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Given the user is logged in"}],
                    },
                ]
            }
        }
        result = mod.extract_acceptance_criteria(fields)
        self.assertGreater(len(result), 0)

    def test_criteria_from_given_when_then_paragraph(self):
        fields = {
            "description": {
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": "Given a user, when they click login, then they see the dashboard"}
                        ],
                    }
                ]
            }
        }
        result = mod.extract_acceptance_criteria(fields)
        self.assertGreater(len(result), 0)

    def test_no_description_field(self):
        result = mod.extract_acceptance_criteria({})
        self.assertEqual(result, "")


# ─── Ticket key parsing ───────────────────────────────────────────────────────

class TestTicketKeyParsing(unittest.TestCase):
    """Test the same regex patterns used inside main()."""

    import re as _re

    _URL_PATTERN = __import__("re").compile(r"[A-Z][A-Z0-9]+-[0-9]+")
    _KEY_PATTERN = __import__("re").compile(r"^[A-Z][A-Z0-9]+-[0-9]+$")

    def test_extracts_key_from_atlassian_url(self):
        url = "https://example.atlassian.net/browse/PROJ-123"
        m = self._URL_PATTERN.search(url)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(0), "PROJ-123")

    def test_extracts_key_from_url_with_query_params(self):
        url = "https://example.atlassian.net/browse/KAN-7?focusedCommentId=123"
        m = self._URL_PATTERN.search(url)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(0), "KAN-7")

    def test_valid_keys_pass_validation(self):
        for key in ("PROJ-1", "PROJ-123", "KAN-7", "ABC123-456", "AB-1"):
            with self.subTest(key=key):
                self.assertIsNotNone(self._KEY_PATTERN.match(key))

    def test_invalid_keys_fail_validation(self):
        for key in ("proj-123", "123-ABC", "PROJ", "PROJ-", "-123", "", "PROJ-abc"):
            with self.subTest(key=key):
                self.assertIsNone(self._KEY_PATTERN.match(key))


# ─── HTTP layer ───────────────────────────────────────────────────────────────

class TestHttpsGet(unittest.TestCase):

    def _make_response(self, status, body_bytes):
        resp = MagicMock()
        resp.status = status
        resp.read.return_value = body_bytes
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    def test_successful_200_response(self):
        payload = {"key": "PROJ-123", "fields": {}}
        fake_resp = self._make_response(200, json.dumps(payload).encode())
        with patch("urllib.request.urlopen", return_value=fake_resp):
            status, body = mod.https_get("https://example.com/api", {"Authorization": "Basic abc"})
        self.assertEqual(status, 200)
        self.assertIn('"key": "PROJ-123"', body)

    def test_401_http_error_returned_as_tuple(self):
        err = urllib.error.HTTPError(
            url="https://jira.example.com",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"errorMessages":["auth required"]}'),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            status, body = mod.https_get("https://jira.example.com/rest/api/3/issue/X-1", {})
        self.assertEqual(status, 401)
        self.assertIn("auth required", body)

    def test_404_http_error_returned_as_tuple(self):
        err = urllib.error.HTTPError(
            url="https://jira.example.com",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=io.BytesIO(b'{"errorMessages":["Issue does not exist"]}'),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            status, body = mod.https_get("https://jira.example.com/rest/api/3/issue/NOPE-1", {})
        self.assertEqual(status, 404)


# ─── JSON output structure ────────────────────────────────────────────────────

class TestMainOutputStructure(unittest.TestCase):
    """Test that main() produces the expected JSON fields given a mocked API response."""

    def _make_jira_response(self, key="TEST-42"):
        return {
            "key": key,
            "fields": {
                "summary": "Test ticket summary",
                "status": {"name": "In Progress"},
                "priority": {"name": "High"},
                "issuetype": {"name": "Story"},
                "assignee": {"displayName": "Jane Doe"},
                "reporter": {"displayName": "John Smith"},
                "labels": ["backend", "api"],
                "components": [{"name": "Core"}],
                "customfield_10016": 5,
                "sprint": None,
                "description": {
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": "This fixes the login flow."}],
                        }
                    ]
                },
                "customfield_10035": None,
                "subtasks": [],
                "issuelinks": [],
                "created": "2026-01-01T00:00:00Z",
                "updated": "2026-04-17T12:00:00Z",
            },
        }

    def test_output_contains_required_keys(self):
        api_response = self._make_jira_response("TEST-42")
        fake_resp_obj = MagicMock()
        fake_resp_obj.status = 200
        fake_resp_obj.read.return_value = json.dumps(api_response).encode()
        fake_resp_obj.__enter__ = lambda s: s
        fake_resp_obj.__exit__ = MagicMock(return_value=False)

        os_env = {
            "JIRA_BASE_URL": "https://example.atlassian.net",
            "JIRA_API_TOKEN": "fake-token",
            "JIRA_EMAIL": "user@example.com",
        }

        captured = io.StringIO()
        with patch("urllib.request.urlopen", return_value=fake_resp_obj), \
             patch.dict("os.environ", os_env, clear=False), \
             patch.object(sys, "argv", ["fetch_jira.py", "TEST-42"]), \
             patch("sys.stdout", captured):
            mod.main()

        output = json.loads(captured.getvalue())
        required_keys = [
            "key", "summary", "status", "priority", "issue_type",
            "assignee", "reporter", "labels", "components",
            "description", "acceptance_criteria", "subtasks",
            "linked_issues", "created", "updated", "url",
        ]
        for k in required_keys:
            self.assertIn(k, output, f"Missing key in output: {k}")

        self.assertEqual(output["key"], "TEST-42")
        self.assertEqual(output["summary"], "Test ticket summary")
        self.assertEqual(output["status"], "In Progress")
        self.assertIn("login flow", output["description"])
        self.assertEqual(output["url"], "https://example.atlassian.net/browse/TEST-42")


if __name__ == "__main__":
    unittest.main()
