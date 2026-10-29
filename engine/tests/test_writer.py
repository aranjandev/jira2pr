"""Tests for assembler.writer.FileWriter — write/check duality and manifest pruning."""

from assembler.writer import FileWriter


def test_write_mode_writes_file(tmp_path):
    writer = FileWriter(tmp_path)
    writer.put("a.txt", "hello")
    assert (tmp_path / "a.txt").read_text() == "hello"


def test_check_mode_detects_diff(tmp_path):
    (tmp_path / "a.txt").write_text("old")
    writer = FileWriter(tmp_path, check=True)
    writer.put("a.txt", "new")
    assert not writer.all_ok


def test_check_mode_all_ok(tmp_path):
    (tmp_path / "a.txt").write_text("same")
    writer = FileWriter(tmp_path, check=True)
    writer.put("a.txt", "same")
    assert writer.all_ok


def test_check_mode_detects_missing(tmp_path):
    writer = FileWriter(tmp_path, check=True)
    writer.put("missing.txt", "content")
    assert not writer.all_ok


def test_finalize_prunes_stale_files(tmp_path):
    writer = FileWriter(tmp_path)
    writer.put("keep.txt", "a")
    writer.put("stale.txt", "b")
    writer.finalize()
    assert (tmp_path / "stale.txt").exists()

    writer2 = FileWriter(tmp_path)
    writer2.put("keep.txt", "a")
    writer2.finalize()
    assert (tmp_path / "keep.txt").exists()
    assert not (tmp_path / "stale.txt").exists()


def test_finalize_prunes_empty_parent_dirs(tmp_path):
    writer = FileWriter(tmp_path)
    writer.put("sub/dir/stale.txt", "b")
    writer.finalize()

    writer2 = FileWriter(tmp_path)
    writer2.finalize()
    assert not (tmp_path / "sub").exists()


def test_check_mode_reports_stale_without_deleting(tmp_path):
    writer = FileWriter(tmp_path)
    writer.put("stale.txt", "b")
    writer.finalize()

    writer2 = FileWriter(tmp_path, check=True)
    writer2.finalize()
    assert not writer2.all_ok
    assert (tmp_path / "stale.txt").exists()


def test_idempotent_second_run_no_changes(tmp_path):
    for _ in range(2):
        writer = FileWriter(tmp_path)
        writer.put("a.txt", "content")
        writer.finalize()
    check_writer = FileWriter(tmp_path, check=True)
    check_writer.put("a.txt", "content")
    check_writer.finalize()
    assert check_writer.all_ok


def test_untracked_files_never_pruned(tmp_path):
    """Files never written via the writer (e.g. agent-managed runtime data) are never touched."""
    protected = tmp_path / "state" / "PROJ-1.yaml"
    protected.parent.mkdir(parents=True)
    protected.write_text("workflow: feature\n")

    writer = FileWriter(tmp_path)
    writer.put("state/workflow-state.template.yaml", "template")
    writer.finalize()

    assert protected.exists()
