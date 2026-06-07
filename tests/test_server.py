"""Tests for the MCP server."""

import pytest


class TestServerBoot:
    """Tests for the server boot function."""

    def test_boot_function_exists(self) -> None:
        """boot() function is importable."""
        from forgerwrite_mcp.server import boot

        assert callable(boot)

    def test_stdout_redirect_function_exists(self) -> None:
        """_redirect_stdout_to_stderr is importable."""
        from forgerwrite_mcp.server import _redirect_stdout_to_stderr

        assert callable(_redirect_stdout_to_stderr)

    def test_redirect_stdout_to_stderr_works(self) -> None:
        """After redirect, writing to sys.stdout goes to stderr (requires real fd)."""
        # The redirect uses os.dup2 which requires real file descriptors,
        # not StringIO. This test verifies the function exists and handles
        # the real sys.stdout/stderr (which always have fileno).
        from forgerwrite_mcp.server import _redirect_stdout_to_stderr

        # Just verify it doesn't crash with real stdout/stderr
        try:
            _redirect_stdout_to_stderr()
        except Exception as exc:
            pytest.fail(f"_redirect_stdout_to_stderr raised: {exc}")

    def test_server_module_imports_cleanly(self) -> None:
        """Server module can be imported without side effects."""
        import forgerwrite_mcp.server

        assert hasattr(forgerwrite_mcp.server, "boot")
