"""Tests for the context packet builder."""

from pathlib import Path

import pytest


def _write_file(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


class TestBuildContextPacket:
    """Tests for build_context_packet()."""

    def test_rejects_forbidden_file_in_allowed_files(self, tmp_path: Path) -> None:
        """Slice with a forbidden file in allowed_files raises."""
        from forgerwrite_mcp.config import LimitsConfig
        from forgerwrite_mcp.context import ContextError, build_context_packet

        _write_file(tmp_path, "src/main.rs", "fn main() {}")
        handoff = {"project": "test", "language": "rust"}
        slice_contract = {
            "allowed_files": ["src/main.rs", "Cargo.lock"],
            "forbidden_files": ["Cargo.lock"],
        }
        with pytest.raises(ContextError, match="Forbidden"):
            build_context_packet(tmp_path, handoff, slice_contract, LimitsConfig())

    def test_rejects_file_over_per_file_limit(self, tmp_path: Path) -> None:
        """A file exceeding per-file limit raises ContextError."""
        from forgerwrite_mcp.config import LimitsConfig
        from forgerwrite_mcp.context import ContextError, build_context_packet

        _write_file(tmp_path, "src/big.rs", "x" * 2000)
        handoff = {"project": "test", "language": "rust"}
        slice_contract = {"allowed_files": ["src/big.rs"]}
        limits = LimitsConfig(context_file_max_bytes=1024)
        with pytest.raises(ContextError, match="exceeds per-file limit"):
            build_context_packet(tmp_path, handoff, slice_contract, limits)

    def test_rejects_total_context_over_limit(self, tmp_path: Path) -> None:
        """Total context exceeding the limit raises ContextError."""
        from forgerwrite_mcp.config import LimitsConfig
        from forgerwrite_mcp.context import ContextError, build_context_packet

        _write_file(tmp_path, "a.rs", "a" * 5000)
        _write_file(tmp_path, "b.rs", "b" * 5000)
        _write_file(tmp_path, "c.rs", "c" * 5000)
        handoff = {"project": "test", "language": "rust"}
        slice_contract = {"allowed_files": ["a.rs", "b.rs", "c.rs"]}
        limits = LimitsConfig(context_total_max_bytes=10000)
        with pytest.raises(ContextError, match="would exceed limit"):
            build_context_packet(tmp_path, handoff, slice_contract, limits)

    def test_computes_sha256_of_each_file(self, tmp_path: Path) -> None:
        """Each file in the context packet has a SHA256 hash."""
        from forgerwrite_mcp.config import LimitsConfig
        from forgerwrite_mcp.context import build_context_packet

        content = "fn main() {}\n"
        _write_file(tmp_path, "src/main.rs", content)
        handoff = {"project": "test", "language": "rust"}
        slice_contract = {"allowed_files": ["src/main.rs"]}
        packet = build_context_packet(tmp_path, handoff, slice_contract, LimitsConfig())
        assert "files" in packet
        assert "src/main.rs" in packet["files"]
        file_entry = packet["files"]["src/main.rs"]
        assert "sha256" in file_entry
        assert len(file_entry["sha256"]) == 64
        assert "content" in file_entry

    def test_preserves_slice_constraints_in_output(self, tmp_path: Path) -> None:
        """Context packet includes the slice contract and handoff."""
        from forgerwrite_mcp.config import LimitsConfig
        from forgerwrite_mcp.context import build_context_packet

        _write_file(tmp_path, "lib.rs", "// lib")
        handoff = {"project": "my-crate", "language": "rust"}
        slice_contract = {"allowed_files": ["lib.rs"], "slice_id": "s1"}
        packet = build_context_packet(tmp_path, handoff, slice_contract, LimitsConfig())
        assert packet["handoff"]["project"] == "my-crate"
        assert packet["slice"]["slice_id"] == "s1"

    def test_excludes_generated_and_vendor_globs(self, tmp_path: Path) -> None:
        """Files matching hygiene globs from config are excluded even if allowed."""
        from forgerwrite_mcp.config import HygieneConfig, LimitsConfig
        from forgerwrite_mcp.context import build_context_packet

        _write_file(tmp_path, "src/main.rs", "fn main() {}")
        _write_file(tmp_path, "target/debug/output", "generated")
        handoff = {"project": "test", "language": "rust"}
        slice_contract = {
            "allowed_files": ["src/main.rs", "target/debug/output"],
        }
        hygiene = HygieneConfig(generated_globs=["target/**"])
        limits = LimitsConfig()
        packet = build_context_packet(tmp_path, handoff, slice_contract, limits, hygiene=hygiene)
        # target/ files should be excluded
        assert "src/main.rs" in packet["files"]
        assert "target/debug/output" not in packet["files"]
