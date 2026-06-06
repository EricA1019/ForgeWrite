"""Tests for the path safety module — the single source of truth for path validation."""

from pathlib import Path

import pytest


class TestSafeResolvePath:
    """Tests for safe_resolve_path()."""

    def test_rejects_leading_slash(self, tmp_path: Path) -> None:
        """Absolute paths (leading /) are rejected."""
        from forgerwrite_mcp.paths import PathSafetyError, safe_resolve_path

        with pytest.raises(PathSafetyError, match="Absolute path"):
            safe_resolve_path(tmp_path, "/etc/passwd")

    def test_rejects_dotdot_segment(self, tmp_path: Path) -> None:
        """Paths with .. traversal are rejected."""
        from forgerwrite_mcp.paths import PathSafetyError, safe_resolve_path

        with pytest.raises(PathSafetyError, match="Traversal"):
            safe_resolve_path(tmp_path, "sub/../../etc")

    def test_rejects_null_byte(self, tmp_path: Path) -> None:
        """Paths containing null bytes are rejected."""
        from forgerwrite_mcp.paths import PathSafetyError, safe_resolve_path

        with pytest.raises(PathSafetyError, match="Null byte"):
            safe_resolve_path(tmp_path, "hello\x00world.txt")

    def test_rejects_symlink_escape(self, tmp_path: Path) -> None:
        """Symlink pointing outside repo root is rejected."""
        from forgerwrite_mcp.paths import PathSafetyError, safe_resolve_path

        # Create a symlink inside tmp_path that points outside
        outside = tmp_path / ".." / "outside_target"
        outside.mkdir(parents=True, exist_ok=True)
        link = tmp_path / "escape_link"
        link.symlink_to(outside.resolve())

        with pytest.raises(PathSafetyError, match="escapes repo"):
            safe_resolve_path(tmp_path, "escape_link")

    def test_allows_nested_relative(self, tmp_path: Path) -> None:
        """Normal nested relative paths are allowed."""
        from forgerwrite_mcp.paths import safe_resolve_path

        nested = tmp_path / "src" / "lib.rs"
        nested.parent.mkdir(parents=True, exist_ok=True)
        nested.touch()

        result = safe_resolve_path(tmp_path, "src/lib.rs")
        assert result == nested.resolve()

    def test_allows_file_at_root(self, tmp_path: Path) -> None:
        """A file at the repo root is allowed."""
        from forgerwrite_mcp.paths import safe_resolve_path

        root_file = tmp_path / "Cargo.toml"
        root_file.touch()

        result = safe_resolve_path(tmp_path, "Cargo.toml")
        assert result == root_file.resolve()

    def test_returns_resolved_absolute(self, tmp_path: Path) -> None:
        """Returned path is resolved and absolute."""
        from forgerwrite_mcp.paths import safe_resolve_path

        sub = tmp_path / "src" / "lib.rs"
        sub.parent.mkdir(parents=True, exist_ok=True)
        sub.touch()

        result = safe_resolve_path(tmp_path, "src/lib.rs")
        assert result.is_absolute()
        assert str(result) == str(sub.resolve())


class TestAssertInsideRepo:
    """Tests for assert_inside_repo()."""

    def test_allows_path_inside_repo(self, tmp_path: Path) -> None:
        """A file inside the repo passes."""
        from forgerwrite_mcp.paths import assert_inside_repo

        f = tmp_path / "Cargo.toml"
        f.touch()
        result = assert_inside_repo(tmp_path, f)
        assert result == f.resolve()

    def test_rejects_repo_root_itself(self, tmp_path: Path) -> None:
        """The repo root directory itself is rejected."""
        from forgerwrite_mcp.paths import PathSafetyError, assert_inside_repo

        with pytest.raises(PathSafetyError, match="repo root"):
            assert_inside_repo(tmp_path, tmp_path)

    def test_rejects_path_outside_repo(self, tmp_path: Path) -> None:
        """A path outside the repo is rejected."""
        from forgerwrite_mcp.paths import PathSafetyError, assert_inside_repo

        outside = tmp_path / ".." / "outside.txt"
        outside = outside.resolve()
        with pytest.raises(PathSafetyError, match="escapes repo"):
            assert_inside_repo(tmp_path, outside)
